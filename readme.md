# 《新·世界树的迷宫2》文本汉化用小工具

## 使用方法
下载dist文件夹中的xml_parser.exe，点击使用。
该工具有两项功能：将原始文件中的{fxxx}控制字符转换为可读的文本（如“[[下一页]]”、“[[speaker: xxx]]”），以及将这些文本转换回控制字符。

转换的文本会存放在.exe同一目录下的./parsed文件夹；转换回的文本则会存放在./reverted文件夹。

**转换回原始格式时，本工具会校验每行的文字数量，大于22个字符时将输出一项warning。译者需要手动在这些行内选择适当的位置，添加[[换行]]进行切换。**

## 已完成处理的控制字符

* 说话人（匹配主角团姓名，其余保留原格式）: {f859}->[[speaker: xxx]]
* 字体颜色: {f804}->[[文字？起始]]
* 语音（保留原格式）: {f813}->[[voice: xxxx]]
* 立绘（保留原格式）: {f855}->[[portrait: xxxx]]
* 经典模式队员名字（保留原格式）: {f843}->[[member: xxxx]]
* 换行符 {f801} 会转换为 [[换行]] 以保留原换行位置，回填时自动还原；若需调整换行位置，可增删 [[换行]]
* 换页符：{f801}{f802} -> [[下一页]] 注意，换页符前必定有一个{f801}，因此不需要写成“[[换行]][[下一页]]”这样的格式。
* 为方便阅读，在[[speaker]]和[[下一页]]等控制字符后加入"\n"


## TODO/WIP
* 转换过程中的错误日志输出（尚不完整）

## 表格化翻译编辑器

运行 `python translator_gui.py` 可打开表格化翻译界面：以三列（source / translation / target）展示 XML 中的全部条目，单元格内容会自动换行完整显示，双击 translation 或 target 单元格即可编辑。编辑译文后 target 会自动按逆转换重算；保存时写回原 XML，并自动生成 `.bak` 备份。

## 打包为独立 EXE（无需安装 Python）

将表格化翻译编辑器打包为单文件可执行程序（`dist/EO_Translator.exe`）：

```
python -m PyInstaller --noconfirm --clean translator_gui.spec
```

产物为单文件、无控制台窗口，已内置：

- `EO5/voice_hash_table.json`（voice 还原所需的 hash 表）；
- EO5 / EOU2 解析器与 checker 模块（`EO5.single_parser`、`EO5.checker`、`EOU2.single_parser`、`checker`）。

注意事项：GUI 通过 `importlib` 按字符串动态导入解析器模块，PyInstaller 的静态分析看不到这些模块名，必须在 `translator_gui.spec` 的 `hiddenimports` 中显式列出；hash 表通过 `datas` 一并打包进 exe。

等价命令行（不使用 spec 文件）：

```
python -m PyInstaller --noconfirm --clean --onefile --windowed --name EO_Translator --add-data "EO5/voice_hash_table.json;EO5" --hidden-import EO5.single_parser --hidden-import EO5.checker --hidden-import EOU2.single_parser --hidden-import checker translator_gui.py
```
