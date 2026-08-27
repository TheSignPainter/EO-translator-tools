"""EO5（世界树的迷宫5）版入口：打包为独立 exe 时使用。"""
from EO5.processor import process_file, process_file_revert
from xml_parser import run_app


if __name__ == '__main__':
    run_app(process_file, process_file_revert,
            parsed_dir='./parsed_eo5', reverted_dir='./reverted_eo5',
            title='世界树5XML译文转换')
