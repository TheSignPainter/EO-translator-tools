# -*- coding: utf-8 -*-
"""统计 EO5/MBM 目录下所有 XML 文件中 <source> 控制字符的数量与特征。

控制字符定义：
- 只统计 <source> 标签中的内容，<target> 忽略。
- 控制字符以 {f81b} 开头，中间是若干个形如 {[0-9a-f]{4}} 的 4 位 16 进制数，
  以 {0000} 作为结束标志。
- 例如：{f81b}{565f}{4348}{4152}{5f31}{3035}{2f45}{5645}{4e54}{2f43}{4f4d}{505f}{454e}{442f}{3030}{3100}{0000}

统计内容：
- 控制字符总数、token 数（长度）分布。
- 对控制字符中的每一个 16 进制数，按位置统计出现次数，从高到低排列。
- 预留高频组合（n-gram）统计接口，默认输出相邻二元组示例。
- 关联分析：控制字符"位置 6"（可变部分起始）与行内最近 {f859} 角色
  是否一一对应（角色名来自 EO5/EO5对话角色列表-f859.txt）。

输出：markdown 格式，写入 f81b_stats.md
"""

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

# EO5/MBM 目录（相对本脚本所在目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MBM_DIR = os.path.join(BASE_DIR, 'EO5', 'MBM')

# 输出文件
OUTPUT_FILE = os.path.join(BASE_DIR, 'f81b_stats.md')

# <source> 标签提取（内容可能跨行）
SOURCE_RE = re.compile(r'<source>(.*?)</source>', re.DOTALL)

# 控制字符：以 {f81b} 开头，中间为若干个非 0000 的 4 位 hex token，以 {0000} 结束。
# 负向前瞻 (?!0000\}) 确保 {0000} 被识别为结束标志而不是被贪婪吞掉。
CONTROL_RE = re.compile(
    r'\{f81b\}'
    r'(?:\{(?!0000\})[0-9a-fA-F]{4}\})*'
    r'\{0000\}'
)

# 控制字符内的单个 token（不含起止标志也可用，这里提取全部）
TOKEN_RE = re.compile(r'\{([0-9a-fA-F]{4})\}')

# 组合统计的默认参数
COMBO_N_DEFAULT = 2
COMBO_TOP_K_DEFAULT = 20

# 统计发现的控制字符固定头部（位置 1-5，全部控制字符 100% 一致）：
#   {f81b}                  起始标志
FIXED_HEADER = ('f81b', '565f', '4348', '4152', '5f31')
FIXED_HEADER_POS = len(FIXED_HEADER)  # 5，可变部分从位置 6 起

# EO5 对话角色列表（{f859}{xxxx} → 角色名），用于"位置 6 × 角色"关联分析
ROLE_LIST_FILE = os.path.join(BASE_DIR, 'EO5', 'EO5对话角色列表-f859.txt')

# {f859}{xxxx} 角色标识（4 位 hex 角色 ID）
F859_RE = re.compile(r'\{f859\}\{([0-9a-fA-F]{4})\}')

# 角色关联分析：无前置 {f859} 的控制字符样本输出上限
NO_ROLE_SAMPLE_MAX = 15
FIXED_HEADER = ('f81b', '565f', '4348', '4152', '5f31')
FIXED_HEADER_POS = len(FIXED_HEADER)  # 5，可变部分从位置 6 起


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def iter_source_texts(file_path: str):
    """读取一个 XML 文件，yield 其中所有 <source> 的文本内容。

    以 UTF-8（含 BOM）读取；失败时尝试常见编码。解析失败则返回空。
    """
    with open(file_path, 'rb') as f:
        raw = f.read()

    text = None
    for enc in ('utf-8-sig', 'utf-8', 'cp932', 'utf-16'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return

    for m in SOURCE_RE.finditer(text):
        yield m.group(1)


def extract_controls(text: str):
    """从一段 <source> 文本中提取所有控制字符的 token 列表。

    返回 (controls, unmatched_f81b, header_mismatch)：
    - controls: list[list[str]]，每个元素是控制字符的 token 序列
      （含起始标志 f81b 与结束标志 0000）。
    - unmatched_f81b: 以 {f81b} 开头但无法按规则完整匹配的片段数。
    - header_mismatch: 完整匹配但固定头部与 FIXED_HEADER 不一致的数量。
    """
    controls = []
    unmatched = 0
    header_mismatch = 0

    pos = 0
    while True:
        m = CONTROL_RE.search(text, pos)
        if not m:
            break
        # 统计从上一个匹配之后到当前匹配之间，有没有孤立的 {f81b}（无法完整匹配）
        between = text[pos:m.start()]
        unmatched += len(re.findall(r'\{f81b\}', between))
        tokens = [t.lower() for t in TOKEN_RE.findall(m.group(0))]
        if tuple(tokens[:FIXED_HEADER_POS]) != FIXED_HEADER:
            header_mismatch += 1
        controls.append(tokens)
        pos = m.end()

    # 尾部未消费部分中孤立的 {f81b}
    unmatched += len(re.findall(r'\{f81b\}', text[pos:]))
    return controls, unmatched, header_mismatch


def load_f859_roles(role_file: str):
    """解析 EO5 对话角色列表文件。

    每行格式：`{f859}{xxxx}\t日文名\t中文名`。

    返回 dict：{角色 ID 小写: (日文名, 中文名)}。文件不存在或解析失败返回空 dict。
    """
    roles = {}
    if not os.path.isfile(role_file):
        return roles
    with open(role_file, 'rb') as f:
        raw = f.read()

    text = None
    for enc in ('utf-8-sig', 'utf-8', 'cp932'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return roles

    line_re = re.compile(r'^\{f859\}\{([0-9a-fA-F]{4})\}\t([^\t]*)\t?([^\t]*)')
    for line in text.splitlines():
        m = line_re.match(line.strip())
        if m:
            roles[m.group(1).lower()] = (m.group(2).strip(), m.group(3).strip())
    return roles


def extract_controls_with_role(text: str):
    """提取控制字符，并关联行内（<source> 内）最近的前置 {f859} 角色。

    与 extract_controls 的区别：为每个控制字符额外找出它**之前**且
    **位置最接近**的 `{f859}{xxxx}`，作为该控制字符的"行内最近角色"。

    返回 (controls_with_role, unmatched_f81b, header_mismatch)：
    - controls_with_role: list[tuple[list[str], str | None]]，每项为
      (token 列表, 角色 ID 小写)；控制字符之前没有 {f859} 时角色 ID 为 None。
    - unmatched_f81b / header_mismatch: 含义同 extract_controls。
    """
    controls = []
    unmatched = 0
    header_mismatch = 0
    f859_matches = list(F859_RE.finditer(text))

    pos = 0
    while True:
        m = CONTROL_RE.search(text, pos)
        if not m:
            break
        # 统计从上一个匹配之后到当前匹配之间，有没有孤立的 {f81b}（无法完整匹配）
        between = text[pos:m.start()]
        unmatched += len(re.findall(r'\{f81b\}', between))
        tokens = [t.lower() for t in TOKEN_RE.findall(m.group(0))]
        if tuple(tokens[:FIXED_HEADER_POS]) != FIXED_HEADER:
            header_mismatch += 1

        # 找 m.start() 之前最近（end 最大）的 {f859}；f859_matches 已按位置升序，
        # 从后往前第一个 end <= m.start() 的即为"在 f81b 之前且位置最接近"的那个。
        role_id = None
        for f in reversed(f859_matches):
            if f.end() <= m.start():
                role_id = f.group(1).lower()
                break

        controls.append((tokens, role_id))
        pos = m.end()

    # 尾部未消费部分中孤立的 {f81b}
    unmatched += len(re.findall(r'\{f81b\}', text[pos:]))
    return controls, unmatched, header_mismatch


def decode_token(token: str) -> str:
    """把 4 位 hex token 按 ASCII 解码为可读字符；失败时原样返回。"""
    try:
        s = bytes.fromhex(token).decode('ascii')
    except (ValueError, UnicodeDecodeError):
        return token
    return s if s.isprintable() else token


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------
def collect_stats(controls_with_folders):
    """根据（文件夹, token 列表）计算各维度的出现次数。

    返回 (position_counts, length_counter, length_folder, folder_length, total_controls)
    - position_counts: dict[int, Counter[str]]，位置 1 起，但固定头部
      （位置 1..FIXED_HEADER_POS）已剔除，只统计可变部分。
    - length_counter: Counter[int]，控制字符的 token 数分布。
    - length_folder: dict[int, Counter[str]]，每种长度下的文件夹分布。
    - folder_length: dict[str, Counter[int]]，每个文件夹下的长度分布。
    - total_controls: 控制字符总数。
    """
    position_counts = defaultdict(Counter)
    length_counter = Counter()
    length_folder = defaultdict(Counter)
    folder_length = defaultdict(Counter)
    total = 0
    for folder, tokens in controls_with_folders:
        total += 1
        ln = len(tokens)
        length_counter[ln] += 1
        length_folder[ln][folder] += 1
        folder_length[folder][ln] += 1
        # 固定头部不再计入统计：只统计位置 FIXED_HEADER_POS+1 之后的可变部分
        for idx in range(FIXED_HEADER_POS + 1, ln + 1):
            position_counts[idx][tokens[idx - 1]] += 1
    return (position_counts, length_counter, length_folder,
            folder_length, total)


def collect_role_pos6(controls_with_roles):
    """统计"位置 6 × 行内最近角色"的对应关系。

    参数：controls_with_roles: list[tuple[list[str], str | None]]，
    即 extract_controls_with_role 的返回。

    返回 (role_pos6, pos6_role, totals)：
    - role_pos6: dict[角色 ID 小写, Counter[位置 6 token]]。
    - pos6_role: dict[位置 6 token, Counter[角色 ID 小写]]。
    - totals: dict，含 with_role / without_role 两个计数。
    """
    role_pos6 = defaultdict(Counter)
    pos6_role = defaultdict(Counter)
    totals = {'with_role': 0, 'without_role': 0}
    for tokens, role_id in controls_with_roles:
        pos6 = tokens[FIXED_HEADER_POS]  # 0-based index 5，即"位置 6"
        if role_id is None:
            totals['without_role'] += 1
            continue
        totals['with_role'] += 1
        role_pos6[role_id][pos6] += 1
        pos6_role[pos6][role_id] += 1
    return role_pos6, pos6_role, totals


# ---------------------------------------------------------------------------
# 组合统计（预留接口）
# ---------------------------------------------------------------------------
def find_frequent_sequences(tokens_lists, n=COMBO_N_DEFAULT,
                            top_k=COMBO_TOP_K_DEFAULT,
                            exclude_flags=True):
    """统计控制字符中高频出现的相邻 n 元序列。

    参数：
    - tokens_lists: 控制字符 token 列表的集合（每项含 f81b 与 0000）。
    - n: 序列长度（n-gram），默认 2。
    - top_k: 只返回出现次数最多的前 top_k 个，默认 20。
    - exclude_flags: 为 True 时剔除起始标志 {f81b} 与结束标志 {0000}，
      只对中间的“数据 token”做组合统计，避免固定标志位淹没真实特征。

    返回：
    按出现次数降序排列的列表，每项为 (tuple(token1, ..., tokenn), count)。
    之后如需统计其它组合（如任意多个 token 的序列、非相邻组合），
    可基于本函数扩展，接口保持不变。
    """
    counter = Counter()
    for tokens in tokens_lists:
        if exclude_flags:
            # 去掉第一个（f81b）和最后一个（0000）
            body = tokens[1:-1] if len(tokens) > 2 else []
        else:
            body = tokens
        for i in range(len(body) - n + 1):
            counter[tuple(body[i:i + n])] += 1
    return counter.most_common(top_k)


# ---------------------------------------------------------------------------
# Markdown 输出
# ---------------------------------------------------------------------------
def format_table(rows, headers):
    """把 (值, 次数, 占比) 之类的行输出为 markdown 表格。"""
    lines = ['| ' + ' | '.join(headers) + ' |',
             '|' + '|'.join(['---'] * len(headers)) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(c) for c in row) + ' |')
    return '\n'.join(lines)


def build_markdown(stats, files_info, combo_bigrams,
                   unmatched_total, header_mismatch):
    """拼装完整 markdown 报告。

    stats = (position_counts, length_counter, length_folder,
             folder_length, total_controls)
    """
    position_counts, length_counter, length_folder, folder_length, total_controls = stats
    lines = []

    lines.append('# EO5/MBM 控制字符统计报告')
    lines.append('')
    lines.append(f'- 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append('- 扫描目录：`EO5/MBM`')
    lines.append(f'- 扫描 XML 文件数：{files_info["total_files"]}')
    lines.append(f'- 含控制字符的 XML 文件数：{files_info["files_with_controls"]}')
    lines.append(f'- 含控制字符的 `<source>` 标签数：{files_info["sources_with_controls"]}')
    lines.append(f'- 控制字符总数：**{total_controls}**')
    lines.append(f'- 孤立的 `{{f81b}}`（无法完整匹配）数量：{unmatched_total}')
    lines.append(f'- 固定头部不一致的控制字符数：{header_mismatch}')
    lines.append('')
    lines.append('> 固定头部（位置 1-5）：`{f81b}{565f}{4348}{4152}{5f31}`，')
    lines.append('> 全部控制字符 100% 一致，已作为已知常量写入代码与注释，')
    lines.append('> 此后不再计入位置统计。')
    lines.append('')

    # 长度分布
    lines.append('## 1. 控制字符长度分布')
    lines.append('')
    lines.append('> 长度为 token 数量，位置 1 为起始标志 `{f81b}`，最后一个位置为结束标志 `{0000}`。')
    lines.append('')
    lengths = sorted(length_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    min_len = min(length_counter)
    max_len = max(length_counter)
    lines.append(f'- 最小 token 数：{min_len}')
    lines.append(f'- 最大 token 数：{max_len}')
    lines.append('')
    lines.append('| token 数 | 控制字符数 | 占比 |')
    lines.append('|---|---:|---:|')
    for ln, cnt in lengths:
        lines.append(f'| {ln} | {cnt} | {cnt / total_controls:.2%} |')
    lines.append('')

    # 位置统计（固定头部已剔除）
    lines.append('## 2. 按位置统计（从高到低，固定头部已剔除）')
    lines.append('')
    lines.append('> 固定头部位置 1-5 不再统计；位置编号保留原始编号，位置 6 起为可变部分。')
    lines.append('> 最后一个位置固定为结束标志 `{0000}`。')
    lines.append('')
    max_pos = max(position_counts)
    for pos in range(FIXED_HEADER_POS + 1, max_pos + 1):
        counter = position_counts.get(pos)
        if not counter:
            continue
        pos_total = sum(counter.values())
        if pos == max_pos:
            note = '（结束标志 {0000}）'
        elif pos == FIXED_HEADER_POS + 1:
            note = '（可变部分起始）'
        else:
            note = ''
        lines.append(f'### 位置 {pos}{note}')
        lines.append('')
        lines.append(f'该位置共出现 `{pos_total}` 次，涉及 `{len(counter)}` 种值：')
        lines.append('')
        lines.append('| 数值 | 出现次数 | 占比 |')
        lines.append('|---|---:|---:|')
        for token, cnt in counter.most_common():
            lines.append(f'| `{{{token}}}` | {cnt} | {cnt / pos_total:.2%} |')
        lines.append('')

    # 长度 × 文件夹分布
    lines.append('## 3. 控制字符长度 × 文件夹分布')
    lines.append('')
    lines.append('> 文件夹为相对 `EO5/MBM` 的路径。')
    lines.append('')
    all_lengths = sorted(length_folder.keys())
    all_folders = sorted(folder_length.keys())

    lines.append('### 3.1 文件夹 × 长度 汇总矩阵')
    lines.append('')
    header_cells = ['文件夹'] + [f'L{ln}' for ln in all_lengths] + ['合计']
    lines.append('| ' + ' | '.join(header_cells) + ' |')
    lines.append('|' + '|'.join(['---'] * len(header_cells)) + '|')
    for folder in all_folders:
        row = [f'`{folder}`']
        for ln in all_lengths:
            row.append(str(folder_length[folder].get(ln, 0)))
        row.append(str(sum(folder_length[folder].values())))
        lines.append('| ' + ' | '.join(row) + ' |')
    lines.append('')

    lines.append('### 3.2 按长度分组的文件夹分布')
    lines.append('')
    for ln in all_lengths:
        folder_counts = length_folder[ln]
        ln_total = sum(folder_counts.values())
        lines.append(f'#### 长度 {ln}（{ln_total} 个控制字符）')
        lines.append('')
        lines.append('| 文件夹 | 数量 | 占比 |')
        lines.append('|---|---:|---:|')
        for folder, cnt in folder_counts.most_common():
            lines.append(f'| `{folder}` | {cnt} | {cnt / ln_total:.2%} |')
        lines.append('')

    # 组合统计（预留接口示例）
    lines.append('## 4. 组合统计（预留接口演示）')
    lines.append('')
    lines.append('> 本段由接口 `find_frequent_sequences()` 输出，默认统计相邻二元组（排除固定的')
    lines.append('> 起始标志 `{f81b}` 与结束标志 `{0000}`）。后续可按需扩展为三元组、')
    lines.append('> 任意序列或非相邻组合。')
    lines.append('')
    if combo_bigrams:
        lines.append('| 组合（相邻二元组） | 出现次数 |')
        lines.append('|---|---:|')
        for seq, cnt in combo_bigrams:
            seq_str = ' '.join('{%s}' % t for t in seq)
            lines.append(f'| `{seq_str}` | {cnt} |')
    else:
        lines.append('（无数据）')
    lines.append('')

    return '\n'.join(lines)


def token_label(token: str) -> str:
    """位置 6 值的短标签，附 ASCII 解码：`{3035}`→'5'。"""
    dec = decode_token(token)
    if dec != token:
        return f'`{{{token}}}`→{dec!r}'
    return f'`{{{token}}}`'


def role_label(role_id: str, roles: dict) -> str:
    """角色 ID 的显示标签：`{f859}{0100}` 洁涅塔（ジェネッタ）。"""
    ja, zh = roles.get(role_id, ('', ''))
    if zh and ja:
        name = f'{zh}（{ja}）'
    elif zh:
        name = zh
    elif ja:
        name = ja
    else:
        name = '未知角色'
    return f'`{{f859}}{{{role_id}}}` {name}'


def build_role_analysis_md(role_pos6, pos6_role, totals, roles,
                           no_role_samples):
    """生成"位置 6 × 行内最近 {f859} 角色"对应关系分析章节（第 5 章）。

    参数：
    - role_pos6 / pos6_role / totals: collect_role_pos6 的返回。
    - roles: load_f859_roles 的返回（{角色 ID: (日文名, 中文名)}）。
    - no_role_samples: list[(folder, name, src_preview, pos6)]，
      控制字符之前无 {f859} 的样本，供人工排查。
    """
    lines = []
    with_role = totals['with_role']
    without_role = totals['without_role']
    all_controls = with_role + without_role

    lines.append('## 5. 位置 6 × 行内最近 {f859} 角色 对应关系分析')
    lines.append('')
    lines.append('> 关联规则：对每个控制字符，取同一 `<source>`（已核实全部含控制字符的')
    lines.append('> `<source>` 均不跨行，等价于同一行）中位于它**之前**且**位置最接近**的')
    lines.append('> `{f859}{xxxx}` 作为该控制字符的"行内最近角色"；若同一行有多个 `{f859}`，')
    lines.append('> 取在 `{f81b}` 之前且位置最近的那个。角色名来自')
    lines.append('> `EO5/EO5对话角色列表-f859.txt`。')
    lines.append('')
    lines.append(f'- 可关联角色的控制字符数：**{with_role}**'
                 f'（占全部 {all_controls} 的 {with_role / all_controls:.2%}）')
    lines.append(f'- 控制字符之前无 `{{f859}}`（无法关联）：**{without_role}**')
    lines.append(f'- 涉及角色数：{len(role_pos6)}（角色列表共 {len(roles)} 个）')
    lines.append(f'- 涉及位置 6 值数：{len(pos6_role)}')
    lines.append('')

    # 5.1 交叉矩阵
    lines.append('### 5.1 交叉矩阵：角色 × 位置 6 值')
    lines.append('')
    lines.append('> 单元格为控制字符数；`·` 表示未出现。位置 6 值附 ASCII 解码。')
    lines.append('')
    all_pos6 = sorted(pos6_role.keys())
    header_cells = ['角色'] + [token_label(p) for p in all_pos6] + ['合计']
    lines.append('| ' + ' | '.join(header_cells) + ' |')
    lines.append('|' + '|'.join(['---'] * len(header_cells)) + '|')
    for role_id in sorted(role_pos6.keys()):
        row = [role_label(role_id, roles)]
        total = 0
        for p in all_pos6:
            cnt = role_pos6[role_id].get(p, 0)
            total += cnt
            row.append(str(cnt) if cnt else '·')
        row.append(str(total))
        lines.append('| ' + ' | '.join(row) + ' |')
    lines.append('')

    # 5.2 每个角色的位置 6 值
    lines.append('### 5.2 每个角色的位置 6 值')
    lines.append('')
    lines.append('| 角色 | 位置 6 值（出现次数） | 唯一性 |')
    lines.append('|---|---|---|')
    for role_id in sorted(role_pos6.keys()):
        counter = role_pos6[role_id]
        items = '、'.join(
            f'{token_label(p)}×{cnt}'
            for p, cnt in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))
        uniq = '唯一' if len(counter) == 1 else f'**{len(counter)} 种值（冲突）**'
        lines.append(f'| {role_label(role_id, roles)} | {items} | {uniq} |')
    lines.append('')

    # 5.3 每个位置 6 值的角色
    lines.append('### 5.3 每个位置 6 值的角色')
    lines.append('')
    lines.append('| 位置 6 值 | 角色（出现次数） | 唯一性 |')
    lines.append('|---|---|---|')
    for p in all_pos6:
        counter = pos6_role[p]
        items = '、'.join(
            f'{role_label(r, roles)}×{cnt}'
            for r, cnt in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))
        uniq = '唯一' if len(counter) == 1 else f'**{len(counter)} 个角色（冲突）**'
        lines.append(f'| {token_label(p)} | {items} | {uniq} |')
    lines.append('')

    # 5.4 一一对应判定
    lines.append('### 5.4 一一对应判定')
    lines.append('')
    conflicts_role = {r: c for r, c in role_pos6.items() if len(c) > 1}
    conflicts_pos6 = {p: c for p, c in pos6_role.items() if len(c) > 1}

    if not conflicts_role and not conflicts_pos6:
        if without_role == 0:
            lines.append('**结论：存在严格的一一对应关系。**')
            lines.append('')
            lines.append('每个角色只对应一个位置 6 值、每个位置 6 值也只对应一个角色，')
            lines.append('且全部控制字符均可关联到角色。具体映射：')
            lines.append('')
            lines.append('| 位置 6 值 | 角色 |')
            lines.append('|---|---|')
            for p in all_pos6:
                (r, _cnt), = pos6_role[p].items()
                lines.append(f'| {token_label(p)} | {role_label(r, roles)} |')
        else:
            lines.append('**结论：可关联范围内存在一一对应关系，另有未关联的控制字符。**')
            lines.append('')
            lines.append('每个可关联角色的控制字符中，角色与位置 6 值一一对应；')
            lines.append(f'但另有 **{without_role}** 个控制字符之前没有 `{{f859}}`')
            lines.append('（其说话人由 `{f812}` 等其它标记指定），无法参与判定。')
            lines.append('')
            lines.append('可关联范围内的映射：')
            lines.append('')
            lines.append('| 位置 6 值 | 角色 |')
            lines.append('|---|---|')
            for p in all_pos6:
                (r, _cnt), = pos6_role[p].items()
                lines.append(f'| {token_label(p)} | {role_label(r, roles)} |')
    else:
        lines.append('**结论：不存在一一对应关系。**')
        lines.append('')
        if conflicts_role:
            lines.append(f'- 同一角色对应多个位置 6 值：{len(conflicts_role)} 个角色')
            for r, c in sorted(conflicts_role.items()):
                items = '、'.join(
                    f'{token_label(p)}×{cnt}'
                    for p, cnt in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
                lines.append(f'  - {role_label(r, roles)}：{items}')
        if conflicts_pos6:
            lines.append(f'- 同一位置 6 值对应多个角色：{len(conflicts_pos6)} 个值')
            for p, c in sorted(conflicts_pos6.items()):
                items = '、'.join(
                    f'{role_label(r, roles)}×{cnt}'
                    for r, cnt in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))
                lines.append(f'  - {token_label(p)}：{items}')
    lines.append('')

    # 5.5 无角色样本
    if no_role_samples:
        lines.append('### 5.5 无法关联角色的控制字符样本')
        lines.append('')
        lines.append(f'> 共 {without_role} 个控制字符之前没有 `{{f859}}`，')
        lines.append(f'> 下表为前 {len(no_role_samples)} 个样本（每个文件取一条）。')
        lines.append('')
        lines.append('| 文件 | source 片段 | 位置 6 值 |')
        lines.append('|---|---|---|')
        for folder, name, preview, pos6 in no_role_samples:
            preview_esc = preview.replace('|', '\\|').replace('\n', ' ')
            lines.append(f'| `{folder}/{name}` | `{preview_esc}…` | {token_label(pos6)} |')
        lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(mbm_dir=MBM_DIR, output_file=OUTPUT_FILE):
    if not os.path.isdir(mbm_dir):
        print(f'目录不存在：{mbm_dir}', file=sys.stderr)
        return 1

    # 加载角色列表（{f859}{xxxx} → 角色名）；文件缺失时角色关联分析退化为
    # 只显示角色 ID，不影响其它统计。
    roles = load_f859_roles(ROLE_LIST_FILE)
    if not roles:
        print(f'警告：未解析到角色列表（{ROLE_LIST_FILE}），'
              f'第 5 章将只显示角色 ID。', file=sys.stderr)

    all_controls = []              # list[(folder, tokens)]
    all_controls_with_role = []    # list[(tokens, role_id | None)]
    no_role_samples = []           # list[(folder, name, src_preview, pos6)]
    seen_no_role = set()
    total_files = 0
    files_with_controls = 0
    sources_with_controls = 0
    unmatched_total = 0
    header_mismatch_total = 0

    for root, _dirs, names in os.walk(mbm_dir):
        for name in sorted(names):
            if not name.lower().endswith('.xml'):
                continue
            path = os.path.join(root, name)
            folder = os.path.relpath(root, mbm_dir).replace('\\', '/')
            total_files += 1
            file_controls = []
            file_sources = 0
            for src_text in iter_source_texts(path):
                controls, unmatched, header_mismatch = extract_controls_with_role(src_text)
                unmatched_total += unmatched
                header_mismatch_total += header_mismatch
                if controls:
                    file_sources += 1
                    for tokens, role_id in controls:
                        file_controls.append((folder, tokens))
                        all_controls_with_role.append((tokens, role_id))
                        # 记录"控制字符之前无 {f859}"的样本（每个文件最多一条）
                        if (role_id is None
                                and len(no_role_samples) < NO_ROLE_SAMPLE_MAX
                                and (folder, name) not in seen_no_role):
                            seen_no_role.add((folder, name))
                            no_role_samples.append(
                                (folder, name, src_text[:80],
                                 tokens[FIXED_HEADER_POS]))
            if file_controls:
                files_with_controls += 1
                sources_with_controls += file_sources
                all_controls.extend(file_controls)

    print(f'扫描完成：{total_files} 个 XML 文件，{len(all_controls)} 个控制字符')

    stats = collect_stats(all_controls)
    files_info = {
        'total_files': total_files,
        'files_with_controls': files_with_controls,
        'sources_with_controls': sources_with_controls,
    }

    # 组合统计：默认相邻二元组（排除固定标志位）
    combo_bigrams = find_frequent_sequences(
        [tokens for _folder, tokens in all_controls],
        n=COMBO_N_DEFAULT, top_k=COMBO_TOP_K_DEFAULT)

    md = build_markdown(stats, files_info, combo_bigrams,
                        unmatched_total, header_mismatch_total)

    # 第 5 章：位置 6 × 行内最近 {f859} 角色 对应关系分析
    role_pos6, pos6_role, role_totals = collect_role_pos6(all_controls_with_role)
    role_md = build_role_analysis_md(role_pos6, pos6_role, role_totals,
                                     roles, no_role_samples)
    md = md + '\n\n' + role_md

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f'报告已输出：{output_file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
