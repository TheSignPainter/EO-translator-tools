import os
import tkinter as tk
from tkinter import filedialog


def run_app(process_file, process_file_revert,
            parsed_dir='./parsed', reverted_dir='./reverted',
            title='XML译文转换'):
    """共享的 Tkinter 界面入口。

    界面代码与具体游戏格式解耦：由调用方传入该格式的
    process_file / process_file_revert 处理函数与输出目录。
    """
    def open_file_dialog(method, initialdir):
        file_paths = filedialog.askopenfilenames(
            title="选择需要处理的 XML 文件",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialdir=initialdir,
        )
        for path in file_paths:
            method(path)
        if file_paths:
            fpaths = '\n'.join(list(file_paths))
            selected_file_label.config(text=f"处理完毕!\n已处理的文件:{fpaths}")

    root = tk.Tk()
    root.geometry("750x200")
    root.title(title)

    open_button_parse = tk.Button(
        root,
        text="预处理控制符",
        command=lambda: open_file_dialog(
            process_file, os.path.abspath(os.getcwd())),
    )
    open_button_parse.pack(padx=20, pady=20)

    open_button_revert = tk.Button(
        root,
        text="回填控制符",
        command=lambda: open_file_dialog(
            process_file_revert,
            os.path.join(os.path.abspath(os.getcwd()), parsed_dir.lstrip('./'))),
    )
    open_button_revert.pack(padx=20, pady=20)

    selected_file_label = tk.Label(
        root,
        text=("请选择需要处理的文件。\n"
              "处理后的文件会被放置在工具目录的"
              f"{parsed_dir}或{reverted_dir}文件夹下。"),
    )
    selected_file_label.pack()

    root.mainloop()


if __name__ == '__main__':
    # 直接运行本文件时，默认使用 EOU2 的处理逻辑（向后兼容）
    from EOU2.processor import (
        process_file as eou2_process_file,
        process_file_revert as eou2_process_file_revert,
    )

    run_app(eou2_process_file, eou2_process_file_revert, title='新树2XML译文转换')