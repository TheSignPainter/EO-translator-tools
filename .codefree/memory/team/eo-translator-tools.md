---
name: EO-translator-tools
type: project
scope: team
description: EO-translator-tools 是《世界树的迷宫》系列（EO5、新树2/EOU2）文本汉化辅助工具，仓库 github.com/TheSignPainter/EO-translator-tools。纯 Python + tkinter GUI，用 PyInstaller 打包为 Window...
created: "2026-08-25T07:34:01.497Z"
updated: "2026-08-25T07:34:01.497Z"
---
EO-translator-tools 是《世界树的迷宫》系列（EO5、新树2/EOU2）文本汉化辅助工具，仓库 github.com/TheSignPainter/EO-translator-tools。纯 Python + tkinter GUI，用 PyInstaller 打包为 Windows exe 分发（xml_parser.spec、xml_parser_eo5.spec，产物在 dist/）。核心功能：在 XML 的 <target> 文本中把 {fxxx} 控制字符与可读 [[...]] 标记双向转换。架构：xml_parser.py 提供共享 run_app() 界面入口，通过注入 process_file/process_file_revert 函数与输出目录解耦具体游戏；EO5/ 与 EOU2/ 是平行实现模块，各含 processor.py（XML 遍历）、single_parser.py（控制字符解析）、checker.py（回填校验）与角色列表 txt；main_eo5.py/main_eou2.py 为打包入口；f81b_stats.py 为 EO5 控制字符统计分析脚本（输出 f81b_stats.md）；others/ 与 utils/查错脚本/ 含辅助检查脚本；data/ 有示例 XML。依赖 loguru。当前状态：check_parsed_entry（预处理校验）、换页符前标点校验、错误日志输出均未实现；EO5 的 {f81b} 声音控制字符已全量统计并持久化为 EO5/voice_hash_table.json，运行时直接读取。