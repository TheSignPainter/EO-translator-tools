import re


def check_parsed_entry(line: str):
    # TODO: 确保解析后的条目符合格式规范。
    pass


def check_reverted_entry(line: str):
    # 转换回原格式（{}）后的条目不应含有任何的控制字符
    if (ctrl := line.find('[[')) != -1:
        return f"有控制字符未解析: {ctrl}"
    if (ctrl := line.find(']]')) != -1:
        return f"有控制字符未解析: {ctrl}"

    # 校验转换后的每行长度
    raw_spaces = re.sub(r'\{(?!f801)[0-9a-f]{4}\}', '', line)
    rows = raw_spaces.split('{f801}')
    for i, row in enumerate(rows):
        if len(row) > 22:
            return f"第 {i+1} 行长度超过22个字符: {row}"

    # TODO: 换页符前必须出现标点
    pass
