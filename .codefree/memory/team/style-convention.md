---
name: style-convention
type: project
scope: team
description: EO-translator-tools 的表单视图 WrappedTableView（canvas+滚动区，每行由 3 个 tk.Text 单元格构成）在水平拉伸窗口宽度时出现过明显卡顿，根因是 Configure 事件风暴触发全量重排、且 _display_lines 对每个单元格用 count(...
created: "2026-08-31T03:20:19.598Z"
updated: "2026-08-31T03:20:19.598Z"
---
EO-translator-tools 的表单视图 WrappedTableView（canvas+滚动区，每行由 3 个 tk.Text 单元格构成）在水平拉伸窗口宽度时出现过明显卡顿，根因是 Configure 事件风暴触发全量重排、且 _display_lines 对每个单元格用 count(...,'update','displaylines') 强制同步 Tk 布局。当前已用约 16ms 的防抖（debounce）合并 resize 期间的重排来缓解。此修复尚未在真实 GUI 环境运行验证，若后续继续优化，可考虑仅对可视区行做惰性重排、并去掉逐单元格的 update 同步标志。这是当前进行中的性能工作流，不影响现有重排语义。