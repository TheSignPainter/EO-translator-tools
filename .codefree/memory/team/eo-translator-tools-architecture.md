---
name: eo-translator-tools-architecture
type: project
scope: team
description: EO-translator-tools 采用共享界面、按游戏区分处理逻辑的架构：共享的 tkinter 界面通过 run_app 注入各游戏的处理函数与输入输出目录，EOU2 和 EO5 各有自己的处理器（控制字符与可读文本互转）和独立入口，打包成不同 exe。新增游戏版本时需沿用"写一套对应处理逻...
created: "2026-08-26T03:20:22.377Z"
updated: "2026-08-26T03:20:22.377Z"
---
EO-translator-tools 采用共享界面、按游戏区分处理逻辑的架构：共享的 tkinter 界面通过 run_app 注入各游戏的处理函数与输入输出目录，EOU2 和 EO5 各有自己的处理器（控制字符与可读文本互转）和独立入口，打包成不同 exe。新增游戏版本时需沿用"写一套对应处理逻辑 + 一个独立打包入口"的模式，保持界面层复用。