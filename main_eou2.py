"""EOU2（新·世界树的迷宫2）版入口：打包为独立 exe 时使用。"""
from EOU2.processor import process_file, process_file_revert
from xml_parser import run_app


if __name__ == '__main__':
    run_app(process_file, process_file_revert, title='新树2XML译文转换')
