import os
import sys
import xml.etree.ElementTree as ET
from loguru import logger

# 将项目根目录加入 sys.path，以便以包形式导入 checker 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from EOU2.single_parser import parse_single_entry, parse_single_entry_revert
from checker import check_reverted_entry

PARSED_DIR = './parsed'
REVERTED_DIR = './reverted'


def process_file(file_path, output_dir=PARSED_DIR):
    fname = os.path.basename(file_path)
    tree = ET.parse(file_path)
    tree_root = tree.getroot()

    for child in tree_root:
        for subchild in child:
            if subchild.tag == 'target':
                parsed_text = parse_single_entry(subchild.text)
                # 预处理阶段的校验（check_parsed_entry）尚未实现，见根目录 checker.py
                subchild.text = parsed_text

    os.makedirs(output_dir, exist_ok=True)
    tree.write(os.path.join(output_dir, fname), encoding='utf-8', xml_declaration=False)


def process_file_revert(file_path, output_dir=REVERTED_DIR):
    fname = os.path.basename(file_path)
    tree = ET.parse(file_path)
    tree_root = tree.getroot()

    for child in tree_root:
        for subchild in child:
            if subchild.tag == 'target':
                parsed_text = parse_single_entry_revert(subchild.text)
                chk_result = check_reverted_entry(parsed_text)
                if chk_result:
                    logger.warning(
                        f"{fname} ID={child.attrib['id']}的行校验失败: {chk_result}")
                subchild.text = parsed_text

    os.makedirs(output_dir, exist_ok=True)
    tree.write(os.path.join(output_dir, fname), encoding='utf-8', xml_declaration=False)
