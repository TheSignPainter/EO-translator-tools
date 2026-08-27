import re
from collections import OrderedDict
from loguru import logger

# core idea：将所有的控制字符串替换为可理解的文本，并包括在[[]]中。

person_name = [ ('{f859}\{1300\}','亚莉安娜'), 
                ('{f859}\{1400\}', '弗拉维奥'),
                ('{f859}\{1500\}', '贝尔托兰'), 
                ('{f859}\{1600\}', '库洛艾')
            ]

person_name.append(('{f859}{([0-9a-f]{4})}', '其他人物-\g<1>'))

def parse_single_entry(line: str):

    # 首先：保留立绘控制{f855}{x}{x} 语音：{f813}{x}{x}{x}{x}
    # 结束的标志是{f85c}
    line = re.sub('{f813}{([0-9a-f]{4})}{([0-9a-f]{4})}{([0-9a-f]{4})}{([0-9a-f]{4})}', repl='[[voice: \g<1> \g<2> \g<3> \g<4>]]\n', string=line)

    line = re.sub('{f855}{([0-9a-f]{4})}{([0-9a-f]{4})}', repl='[[portrait: \g<1> \g<2>]]\n', string=line)

    # {f859}：说话人信息
    for (patt, name) in person_name:
        line = re.sub(patt, repl='[[speaker: '+name+']]\n', string=line)

    # （经典模式）队员名字
    line = re.sub('{f843}{([0-9a-f]{4})}', repl='[[member: \g<1>]]', string=line)

    # 文字颜色
    line = line.replace('{f804}{0000}', '[[文字白起始]]')
    line = line.replace('{f804}{0500}', '[[文字黄起始]]')
    line = line.replace('{f804}{0300}', '[[文字灰起始]]')
    line = line.replace('{f804}{0800}', '[[颜色8起始]]')
    line = line.replace('{f804}{0900}', '[[颜色9起始]]')
    line = line.replace('{f804}{0200}', '[[颜色2起始]]')
    line = line.replace('{f804}{0600}', '[[颜色6起始]]')
    

    # 删除{f801}（换行）和{f802}（下一页）
    line = line.replace('{f801}{f802}', '[[下一页]]\n')
    line = line.replace('{f801}', '')
    line = line.replace('{f85c}', '[[对话结束]]')

    

    return line

def parse_single_entry_revert(line: str):

    # 删除展示用的\n
    line = line.replace('\n', '')
    # 放回{f801}（换行）和{f802}（下一页）
    line = line.replace('[[换行]]', '{f801}')
    line = line.replace('[[下一页]]', '{f801}{f802}')
    line = line.replace('[[对话结束]]', '{f85c}')

    # 放回立绘控制：{f855}{x}{x}语音：{f813}{x}{x}{x}{x}
    line = re.sub('\[\[voice: ([0-9a-f]{4}) ([0-9a-f]{4}) ([0-9a-f]{4}) ([0-9a-f]{4})\]\]', repl='{f813}{\g<1>}{\g<2>}{\g<3>}{\g<4>}', string=line)
    line = re.sub('\[\[portrait: ([0-9a-f]{4}) ([0-9a-f]{4})\]\]', repl='{f855}{\g<1>}{\g<2>}', string=line)

    # {f859}：说话人信息
    for (patt, name) in person_name:
        if name.startswith("其他人物"):
            line = re.sub('\[\[speaker: 其他人物-([0-9a-f]{4})\]\]', repl='{f859}{\g<1>}', string=line)
        else:
            line = re.sub(f'\[\[speaker: {name}\]\]', repl=patt.replace('\\', ''), string=line)
    # （经典模式）队员名字
    line = re.sub('\[\[member: ([0-9a-f]{4})\]\]', repl='{f843}{\g<1>}', string=line)

    # 文字颜色

    line = line.replace('[[文字白起始]]', '{f804}{0000}')
    line = line.replace('[[文字黄起始]]', '{f804}{0500}')
    line = line.replace('[[文字灰起始]]', '{f804}{0300}')
    line = line.replace('[[颜色8起始]]', '{f804}{0800}')
    line = line.replace('[[颜色9起始]]', '{f804}{0900}')
    line = line.replace('[[颜色2起始]]', '{f804}{0200}')
    line = line.replace('[[颜色6起始]]', '{f804}{0600}')

    # 如果line不是以{f801}或{f802}结束，则添加{f801}
    if not line.endswith('{f801}') and not line.endswith('{f802}'):
        line += '{f801}'

    return line
