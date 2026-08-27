# -*- coding: utf-8 -*-
"""生成 EO5 的持久化 voice hash 表（一次性预处理脚本）。

MBM 的 <source> 内容已确认不再变更，因此可事先把
{8位hash: 完整控制字符} 映射保存为 EO5/voice_hash_table.json，
随程序分发；运行 EO5/single_parser.py 时直接读取该文件，
无需再扫描 MBM，加快启动并减小打包体积。

用法：
    python -m EO5.build_voice_table
或：
    python EO5/build_voice_table.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from EO5.single_parser import VOICE_HASH_FILE, build_voice_hash_file  # noqa: E402


def main():
    count = build_voice_hash_file()
    print(f'voice hash 表已生成：{VOICE_HASH_FILE}（{count} 条）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
