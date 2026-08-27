import hashlib
import json
import os
import re
from loguru import logger  # noqa: F401  (保留：供调试时打印控制字符用)

# core idea：将所有的控制字符串替换为可理解的文本，并包括在[[]]中。
#
# 说明：EO5 的控制字符格式与 EOU2 基本一致，因此复用了同一套解析逻辑。
#
# 控制字符结构（经 f81b_stats.py 全量统计确认，1005 个控制字符 100% 一致）：
#   [固定头部（位置 1-5）][可变部分……][结束标志 {0000}]
#   固定头部 = {f81b}{565f}{4348}{4152}{5f31}
#     - {f81b}：起始标志
#     - {565f}{4348}{4152}{5f31}：固定签名
#   结束标志 {0000} 的位置不固定（控制字符长度 12~22），故不并入固定头部。

# 固定头部：控制字符前 5 个 token 固定不变，作为已知常量直接写入。
# 该部分已在统计中确认 100% 一致，此后不再作为动态内容处理。
VOICE_HEADER = '{f81b}{565f}{4348}{4152}{5f31}'

# ---------------------------------------------------------------------------
# f81b 声音控制字符：完整匹配 {f81b}...{0000}
# ---------------------------------------------------------------------------
# 控制字符结构（经 f81b_stats.py 全量统计确认，1005 个控制字符 100% 一致）：
#   [固定头部（位置 1-5）][可变部分……][结束标志 {0000}]
# 位置 6（可变部分起始）与说话人强相关：
#   {3031}→洁涅塔 {3032}→梅莉娜 {3033}→埃德加 {3034}→瑟里克
#   {3035}→雷穆斯 {3036}→莉莉   {3037}→索罗尔 {3039}→阿尔空
#   {3038} 同时对应卫兵/城市传令官（22 个样本，18:4），无法仅凭位置 6 判定，
#   必须依靠行内最近 {f859}{xxxx}；行内也没有 {f859} 时显示“角色3038”。
F81B_RE = re.compile(
    r'\{f81b\}'
    r'(?:\{(?!0000\})[0-9a-fA-F]{4}\})*'
    r'\{0000\}'
)
TOKEN_RE = re.compile(r'\{([0-9a-fA-F]{4})\}')
FIXED_HEADER_POS = 5  # 位置 6 = 0-based index 5

# 位置 6 → 角色名（仅放唯一映射；'3038' 冲突故不列入）
POS6_ROLE = {
    '3031': '洁涅塔',
    '3032': '梅莉娜',
    '3033': '埃德加',
    '3034': '瑟里克',
    '3035': '雷穆斯',
    '3036': '莉莉',
    '3037': '索罗尔',
    '3039': '阿尔空',
}

# {f859}{xxxx} 角色 ID → 角色名
F859_ID_RE = re.compile(r'\{f859\}\{([0-9a-fA-F]{4})\}')
F859_NAME = {
    '0100': '洁涅塔',
    '0200': '瑟里克',
    '0300': '梅莉娜',
    '0400': '埃德加',
    '0500': '雷穆斯',
    '0600': '索罗尔',
    '0700': '莉莉',
    '0800': '阿尔空',
    '0900': '卫兵',
    '0a00': '城市传令官',
}
# EO5/MBM 目录（本文件位于 EO5/ 下）
MBM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MBM')

# 持久化 voice hash 表文件。
# MBM 的 <source> 内容已确认不再变更，因此 hash 表（{8位hash: 完整控制字符}）
# 可以事先生成并保存为 JSON，随程序分发，运行时不需再扫描 MBM。
# 生成方式：python -m EO5.build_voice_table（或 EO5/build_voice_table.py）。
VOICE_HASH_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'voice_hash_table.json')


def _voice_hash(ctrl_text: str) -> str:
    """对完整控制字符文本取 MD5 前 8 位作为短 hash。"""
    return hashlib.md5(ctrl_text.encode('utf-8')).hexdigest()[:8]


def build_voice_hash_file(path=VOICE_HASH_FILE):
    """扫描 EO5/MBM 构建 hash 表并写入持久化 JSON 文件。

    供一次性预处理使用（EO5/build_voice_table.py 或手动调用）。
    返回写入的条目数。
    """
    table = _build_voice_hash_table()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, indent=2, sort_keys=True)
    logger.info(f'voice hash 表已写入：{path}（{len(table)} 条）')
    return len(table)


def _load_voice_hash_table(path=VOICE_HASH_FILE):
    """从持久化 JSON 加载 hash 表；文件缺失时回退扫描 MBM。"""
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                table = json.load(f)
            logger.info(f'voice hash 表已加载：{path}（{len(table)} 条）')
            return table
        except (OSError, ValueError) as e:
            logger.warning(f'读取 voice hash 表失败（{e}），回退扫描 MBM')
    return _build_voice_hash_table()


def _build_voice_hash_table():
    """预处理：扫描 EO5/MBM 下所有 XML，构建 {hash8: 完整控制字符} 映射。

    用于 revert 时把 `[[voice: 角色名 hash]]` 还原为完整的
    `{f81b}{...}{0000}`。控制字符统一转为小写后再计算 hash，
    与 parse 阶段保持一致。
    """
    table = {}
    if not os.path.isdir(MBM_DIR):
        logger.warning(f'MBM 目录不存在（{MBM_DIR}），voice 将无法还原')
        return table
    for root, _dirs, names in os.walk(MBM_DIR):
        for name in sorted(names):
            if not name.lower().endswith('.xml'):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
            except OSError:
                continue
            text = None
            for enc in ('utf-8-sig', 'utf-8', 'cp932', 'utf-16'):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                continue
            for m in F81B_RE.finditer(text):
                ctrl = m.group(0).lower()
                h = _voice_hash(ctrl)
                if h in table and table[h] != ctrl:
                    logger.warning(f'voice hash 冲突：{h}（{table[h]} vs {ctrl}）')
                table[h] = ctrl
    return table


# 模块加载时加载一次（优先读持久化 JSON，缺失时回退扫描 MBM；进程生命周期内复用）
VOICE_HASH_TABLE = _load_voice_hash_table()

# revert 用占位符：[[voice: 角色名 8位hash]]
VOICE_PLACEHOLDER_RE = re.compile(
    r'\[\[voice: ([^\]\n]+?) ([0-9a-f]{8})\]\]')


def _resolve_voice_role(ctrl_start: int, tokens, line_text: str) -> str:
    """确定控制字符的角色名。

    优先级：
    1. 行内最近 {f859}{xxxx}（位于控制字符之前且位置最接近）→ 角色名；
       若角色 ID 不在名单中则显示“其他人物-xxxx”。
    2. 位置 6 唯一映射 → 角色名。
    3. 兜底：`角色{位置6值}`（如 {3038} 无法判定时显示“角色3038”）。
    """
    for m in reversed(list(F859_ID_RE.finditer(line_text))):
        if m.end() <= ctrl_start:
            role_id = m.group(1).lower()
            return F859_NAME.get(role_id, f'其他人物-{role_id}')
    pos6 = tokens[FIXED_HEADER_POS]
    return POS6_ROLE.get(pos6, f'角色{pos6}')


def _voice_repl(match, line_text: str) -> str:
    """把单个 f81b 控制字符替换为 `[[voice: 角色名 hash]]\n`。"""
    ctrl = match.group(0).lower()
    tokens = [t.lower() for t in TOKEN_RE.findall(ctrl)]
    role = _resolve_voice_role(match.start(), tokens, line_text)
    return f'[[voice: {role} {_voice_hash(ctrl)}]]\n'


def _voice_revert(match) -> str:
    """把 `[[voice: 角色名 hash]]` 还原为完整控制字符。"""
    h = match.group(2).lower()
    ctrl = VOICE_HASH_TABLE.get(h)
    if ctrl is None:
        logger.warning(f'未找到 voice hash {h} 对应的控制字符，保留占位符：'
                       f'{match.group(0)}')
        return match.group(0)
    return ctrl

person_name = [
(r'{f859}\{0100\}', '洁涅塔'),
(r'{f859}\{0200\}', '瑟里克'),
(r'{f859}\{0300\}', '梅莉娜'),
(r'{f859}\{0400\}', '埃德加'),
(r'{f859}\{0500\}', '雷穆斯'),
(r'{f859}\{0600\}', '索罗尔'),
(r'{f859}\{0700\}', '莉莉'),
(r'{f859}\{0800\}', '阿尔空'),
(r'{f859}\{0900\}', '卫兵'),
(r'{f859}\{0a00\}', '城市传令官'),
]

person_name.append((r'{f859}{([0-9a-f]{4})}', r'其他人物-\g<1>'))


def parse_single_entry(line: str):
    # 声音控制（voice）：把行内所有 {f81b}...{0000} 控制字符替换为
    #   [[voice: 角色名 8位hash]]\n
    # - hash 为完整控制字符文本的 MD5 前 8 位（revert 时经 VOICE_HASH_TABLE 还原）；
    # - 角色名优先取行内最近 {f859} 对应的角色，其次由位置 6 映射推断，
    #   都无法确定时使用“角色XXXX”（XXXX 为位置 6 的 4 位 hex 值）。
    # 必须放在 {f859} 替换之前：需要在原文中定位 {f859}{xxxx} 判定说话人。
    line = F81B_RE.sub(lambda m: _voice_repl(m, line), line)

    # {f859}：说话人信息
    for (patt, name) in person_name:
        line = re.sub(patt, repl='[[speaker: '+name+']]\n', string=line)

    # （经典模式）队员名字
    line = re.sub(r'{f843}{([0-9a-f]{4})}', repl='[[member: \\g<1>]]', string=line)

    # 文字颜色
    line = line.replace('{f804}{0000}', '[[文字白起始]]')
    line = line.replace('{f804}{0500}', '[[文字黄起始]]')
    line = line.replace('{f804}{0300}', '[[文字灰起始]]')
    line = line.replace('{f804}{0800}', '[[颜色8起始]]')
    line = line.replace('{f804}{0900}', '[[颜色9起始]]')
    line = line.replace('{f804}{0200}', '[[颜色2起始]]')
    line = line.replace('{f804}{0600}', '[[颜色6起始]]')

    # 保留{f801}（换行）为[[换行]]，便于回填时精确还原；{f802}（下一页）与{f801}成对出现
    line = line.replace('{f801}{f802}', '[[下一页]]\n')
    line = line.replace('{f801}', '[[换行]]')
    line = line.replace('{f85c}', '[[对话结束]]')

    return line


def parse_single_entry_revert(line: str):
    # 删除展示用的\n
    line = line.replace('\n', '')
    # 放回 f81b 声音控制：[[voice: 角色名 hash]] → 完整 {f81b}...{0000}
    line = VOICE_PLACEHOLDER_RE.sub(_voice_revert, line)
    # 放回{f801}（换行）和{f802}（下一页）
    line = line.replace('[[换行]]', '{f801}')
    line = line.replace('[[下一页]]', '{f801}{f802}')
    line = line.replace('[[对话结束]]', '{f85c}')

    # 放回立绘控制：{f855}{x}{x}语音：{f813}{x}{x}{x}{x}
    line = re.sub(r'\[\[voice: ([0-9a-f]{4}) ([0-9a-f]{4}) ([0-9a-f]{4}) ([0-9a-f]{4})\]\]', repl='{f813}{\\g<1>}{\\g<2>}{\\g<3>}{\\g<4>}', string=line)
    line = re.sub(r'\[\[portrait: ([0-9a-f]{4}) ([0-9a-f]{4})\]\]', repl='{f855}{\\g<1>}{\\g<2>}', string=line)

    # {f859}：说话人信息
    for (patt, name) in person_name:
        if name.startswith("其他人物"):
            line = re.sub(r'\[\[speaker: 其他人物-([0-9a-f]{4})\]\]', repl='{f859}{\\g<1>}', string=line)
        else:
            line = re.sub(rf'\[\[speaker: {name}\]\]', repl=patt.replace('\\', ''), string=line)

    # （经典模式）队员名字
    line = re.sub(r'\[\[member: ([0-9a-f]{4})\]\]', repl='{f843}{\\g<1>}', string=line)

    # 文字颜色
    line = line.replace('[[文字白起始]]', '{f804}{0000}')
    line = line.replace('[[文字黄起始]]', '{f804}{0500}')
    line = line.replace('[[文字灰起始]]', '{f804}{0300}')
    line = line.replace('[[颜色8起始]]', '{f804}{0800}')
    line = line.replace('[[颜色9起始]]', '{f804}{0900}')
    line = line.replace('[[颜色2起始]]', '{f804}{0200}')
    line = line.replace('[[颜色6起始]]', '{f804}{0600}')

    # 补充行尾换行符：仅当末尾是普通文本时才添加 {f801}。
    # 以控制字符/占位符结尾的行（如 {f804}{0000}、voice 的 {0000}、[[对话结束]]）
    # 不再补充 {f801}，以保证 revert 与 parse 互为精确逆运算（source 可无损往返）。
    if not re.search(r'(?:\[\[[^\]]*\]\]|\{[^{}]*\})+\s*$', line):
        line += '{f801}'

    return line
