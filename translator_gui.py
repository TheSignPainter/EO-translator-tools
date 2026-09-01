# -*- coding: utf-8 -*-
"""EO5/EOU2 XML 表格化翻译编辑器。

以三列表格展示 mbm/entry(source/target) 结构 XML：
- source：<source> 转换后的只读文本；
- translation：<target> 转换后的可编辑译文；
- target：将 translation 还原后的控制字符文本，可编辑；保存时写回原 XML。

联动规则（单向自动）：编辑 translation 后自动用 revert 重算 target；
target 可手动修改，保存一律以 target 列内容为准。

运行：python translator_gui.py
"""

import codecs
import importlib
import re
import shutil
import sys
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PARSER_MODULES = {
    'EO5': {'parser': 'EO5.single_parser', 'checker': 'EO5.checker'},
    'EOU2': {'parser': 'EOU2.single_parser', 'checker': 'checker'},
}

COLUMNS = ('idx', 'source', 'translation', 'target')
COLUMN_TITLES = {
    'idx': '#',
    'source': 'source（转换后，只读）',
    'translation': 'translation（译文，可编辑）',
    'target': 'target（转换回，可编辑）',
}

# ---- target 列格式校验 -----------------------------------------------------

F859_TOKEN_RE = re.compile(r'\{f859\}')
F859_ID_RE = re.compile(r'\{[0-9a-fA-F]{4}\}')


def validate_target(text, checker_fn):
    """校验 target 列字符串，返回问题列表；空列表表示通过。"""
    issues = []
    if checker_fn is not None:
        msg = checker_fn(text)
        if msg:
            issues.append(msg)
    for idx, m in enumerate(F859_TOKEN_RE.finditer(text), 1):
        if F859_ID_RE.match(text, m.end()) is None:
            issues.append(
                f'第 {idx} 处 {{f859}} 后缺少合法的 4 位 hex 角色 ID（应为 {{xxxx}}）'
            )
    return issues


# ---- XML 读取 / 行数据 ------------------------------------------------------


def load_parser(game):
    """返回 (parse, revert, checker)，按游戏名动态导入。"""
    mod = importlib.import_module(PARSER_MODULES[game]['parser'])
    chk = importlib.import_module(PARSER_MODULES[game]['checker'])
    return mod.parse_single_entry, mod.parse_single_entry_revert, chk.check_reverted_entry


def build_rows(xml_path, parse_fn):
    """读取 XML，构造行数据列表（字典）。"""
    rows = []
    tree = ET.parse(xml_path)
    for entry in tree.getroot():
        if entry.tag != 'entry':
            continue
        src = entry.find('source')
        tgt = entry.find('target')
        source_raw = src.text if src is not None and src.text is not None else ''
        target_raw = tgt.text if tgt is not None and tgt.text is not None else ''
        rows.append({
            'entry_id': entry.attrib.get('id'),
            'idx': entry.attrib.get('id'),
            'source_raw': source_raw,
            'source': parse_fn(source_raw),
            'translation': parse_fn(target_raw),
            'target': target_raw,
            'issues': [],
        })
    return rows


def read_xml_bytes(path):
    """读取 XML 原始字节，返回 (文本, 编码, BOM)。"""
    data = Path(path).read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode('utf-8'), 'utf-8', codecs.BOM_UTF8
    for enc in ('utf-8', 'cp932', 'utf-16'):
        try:
            return data.decode(enc), enc, b''
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace'), 'utf-8', b''


# ---- 保存：定向替换 <target>，保留原文件格式 ---------------------------------

ENTRY_BLOCK_RE = re.compile(r'<entry\b[^>]*>.*?</entry>', re.DOTALL | re.IGNORECASE)
TARGET_OPEN_TAG_RE = re.compile(r'<target\b[^>]*>', re.IGNORECASE)
TARGET_CLOSE_TAG_RE = re.compile(r'</target\s*>', re.IGNORECASE)
TARGET_SELF_CLOSE_RE = re.compile(r'<target\b[^>]*/>', re.IGNORECASE)
SOURCE_INDENT_RE = re.compile(r'^(\s*)<source\b', re.MULTILINE | re.IGNORECASE)
ENTRY_CLOSE_RE = re.compile(r'</entry\s*>', re.IGNORECASE)


def replace_target_texts(raw_text, new_targets):
    """按条目顺序替换 <target> 文本，保留其余字节级格式。"""
    blocks = list(ENTRY_BLOCK_RE.finditer(raw_text))
    if len(blocks) != len(new_targets):
        raise ValueError(
            f'XML 条目数（{len(blocks)}）与表格行数（{len(new_targets)}）不一致，已取消保存'
        )
    parts = []
    last = 0
    for block_m, new_text in zip(blocks, new_targets):
        block = block_m.group(0)
        parts.append(raw_text[last:block_m.start()])
        parts.append(_replace_block_target(block, new_text))
        last = block_m.end()
    parts.append(raw_text[last:])
    return ''.join(parts)


def _display_path(path):
    """返回用于展示的路径：若父路径中含有名为 MBM 的文件夹，则展示从 MBM/ 开始；
    否则退化为仅展示文件名。"""
    p = Path(path).resolve()
    try:
        idx = p.parts.index('MBM')
    except ValueError:
        return Path(path).name
    return str(Path(*p.parts[idx:]))


def _replace_block_target(block, new_text):
    """替换单个 entry 块中的 <target> 文本。"""
    escaped = xml_escape(new_text)
    open_m = TARGET_OPEN_TAG_RE.search(block)
    close_m = TARGET_CLOSE_TAG_RE.search(block)
    if open_m and close_m and close_m.start() > open_m.end():
        return block[:open_m.end()] + escaped + block[close_m.start():]
    self_m = TARGET_SELF_CLOSE_RE.search(block)
    if self_m:
        return block[:self_m.start()] + f'<target>{escaped}</target>' + block[self_m.end():]
    close = ENTRY_CLOSE_RE.search(block)
    indent = '  '
    m = SOURCE_INDENT_RE.search(block)
    if m:
        indent = m.group(1)
    insert_at = close.start() if close else len(block)
    return block[:insert_at] + f'\n{indent}<target>{escaped}</target>' + block[insert_at:]


def save_file(xml_path, rows):
    """保存：先备份 .bak，再把各行的 target 写回原 XML，返回备份路径。"""
    xml_path = Path(xml_path)
    text, enc, bom = read_xml_bytes(xml_path)
    new_text = replace_target_texts(text, [row['target'] for row in rows])
    backup = xml_path.with_name(xml_path.name + '.bak')
    shutil.copy2(xml_path, backup)
    xml_path.write_bytes(bom + new_text.encode(enc))
    return backup


# ---- GUI -------------------------------------------------------------------


class WrappedTableView:
    """可自动换行的只读表格：每行三个 tk.Text 单元格，双击单元格弹出编辑框。"""

    FONT = 'TkTextFont'
    SELECT_BG = '#dcebff'

    def __init__(self, parent, columns, widths, titles):
        self.columns = columns
        self.widths = widths
        self.titles = titles
        self.on_cell_edit = None   # 回调 (row_idx, field)
        self.on_row_select = None  # 回调 (row_idx)
        self._cells = []
        self._row_frames = []
        self._selected = None
        self._relayouting = False
        self._relayout_job = None
        self._build(parent)

    def _build(self, parent):
        wrap = ttk.Frame(parent, padding=(8, 0))
        wrap.pack(side='top', fill='both', expand=True)
        body = tk.Frame(wrap)
        body.pack(side='top', fill='both', expand=True)
        vsb = ttk.Scrollbar(body, orient='vertical')
        vsb.pack(side='right', fill='y')
        header = tk.Frame(body, bg='#d9d9d9')
        header.pack(side='top', fill='x')
        for col_idx, (col, w) in enumerate(zip(self.columns, self.widths)):
            header.grid_columnconfigure(col_idx, weight=w)
            tk.Label(
                header, text=self.titles[col], font=self.FONT,
                anchor='w', bg='#d9d9d9', relief='groove',
                width=w,
            ).grid(row=0, column=col_idx, sticky='ew', padx=(0, 2))
        self.canvas = tk.Canvas(body, highlightthickness=0, bg='white')
        vsb.configure(command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.rows_frame = tk.Frame(self.canvas, bg='white')
        self._win_id = self.canvas.create_window((0, 0), window=self.rows_frame, anchor='nw')
        self.rows_frame.bind('<Configure>', self._on_rows_configure)
        self.rows_frame.bind('<Map>', self._on_rows_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind('<MouseWheel>', self._on_wheel)
        self.canvas.pack(side='left', fill='both', expand=True)

    # ---- 行数据 ----

    def set_rows(self, rows):
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self._cells = []
        self._row_frames = []
        self._selected = None
        for i, row in enumerate(rows):
            self._add_row(i, row)
        self._refresh_scrollregion()
        self.canvas.after_idle(self._relayout_all_rows)

    def _add_row(self, row_idx, row):
        rf = tk.Frame(self.rows_frame, bg='white')
        rf.pack(fill='x')
        texts = []
        for col_idx, field in enumerate(self.columns):
            rf.grid_columnconfigure(col_idx, weight=self.widths[col_idx])
            t = tk.Text(
                rf, width=self.widths[col_idx], wrap='char', height=1,
                bd=0, highlightthickness=0, padx=3, pady=2, font=self.FONT,
                bg='white',
            )
            t.insert('1.0', row[field])
            t.configure(state='disabled')
            t.grid(row=0, column=col_idx, sticky='new', padx=(0, 2))
            t.bind('<Button-1>', lambda e, idx=row_idx: self._select(idx))
            t.bind('<Double-1>', lambda e, idx=row_idx, f=field: self._edit(idx, f))
            t.bind('<MouseWheel>', self._on_wheel)
            texts.append(t)
        self._cells.append(texts)
        self._row_frames.append(rf)
        self._relayout_row(row_idx)
        # 条目之间的浅灰色分割线
        tk.Frame(self.rows_frame, height=1, bg='#d9d9d9').pack(fill='x')

    def update_cell(self, row_idx, field, value):
        col_idx = self.columns.index(field)
        t = self._cells[row_idx][col_idx]
        t.configure(state='normal')
        t.delete('1.0', 'end')
        t.insert('1.0', value)
        t.configure(state='disabled')
        self._relayout_row(row_idx)
        self._refresh_scrollregion()

    def set_invalid(self, row_idx, flag):
        t = self._cells[row_idx][self.columns.index('target')]
        t.configure(fg='#b00020' if flag else 'black')

    def _relayout_row(self, row_idx):
        texts = self._cells[row_idx]
        max_lines = max(self._display_lines(t) for t in texts)
        for t in texts:
            if int(t.cget('height')) != max_lines:
                t.configure(height=max_lines)

    def _display_lines(self, t):
        """计算单元格内容需要的显示行数；窗口未映射时按字符数估算。

        已显示时用 Tk 的 displaylines 统计（带 update 强制重算，否则可能返回过期值）；
        文本以实际换行结尾时去掉末尾空行，避免多算一行。
        """
        if t.winfo_ismapped() and t.winfo_width() > 1:
            end = 'end'
            if t.get('end-2c', 'end-1c') == '\n':
                end = 'end-1c'
            try:
                res = t.count('1.0', end, 'update', 'displaylines')
                if res:
                    return max(int(res), 1)
            except tk.TclError:
                pass
        text = t.get('1.0', 'end-1c')
        if not text:
            return 1
        n = len(text)
        width = int(t.cget('width') or 1)
        logical = text.count('\n') + 1
        if text.endswith('\n'):
            logical -= 1
        per_line = max(1, width // 2)  # 全角字符约占半列，取保守值
        return max(logical, (n + per_line - 1) // per_line)

    # ---- 交互 ----

    def _edit(self, row_idx, field):
        if self.on_cell_edit is not None:
            self.on_cell_edit(row_idx, field)

    def _select(self, row_idx):
        if self._selected is not None and self._selected < len(self._row_frames):
            self._set_row_bg(self._selected, 'white')
        self._selected = row_idx
        self._set_row_bg(row_idx, self.SELECT_BG)
        if self.on_row_select is not None:
            self.on_row_select(row_idx)

    def _set_row_bg(self, row_idx, bg):
        for t in self._cells[row_idx]:
            t.configure(bg=bg)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-event.delta // 120, 'units')

    def _on_rows_configure(self, event=None):
        self._schedule_relayout()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._win_id, width=event.width)

    def _schedule_relayout(self):
        """每隔一定间隔只执行一次全量重排，避免连续抖动触发大量重算。"""
        if self._relayout_job is not None:
            return
        self._relayout_job = self.canvas.after(16, self._run_relayout_all)

    def _run_relayout_all(self):
        self._relayout_job = None
        self.canvas.after_idle(self._relayout_all_rows)

    def _relayout_all_rows(self):
        """窗口尺寸变化/表格映射后，按新宽度重算所有行的换行与行高。"""
        if self._relayouting:
            return
        self._relayouting = True
        try:
            self.canvas.update_idletasks()
            for i in range(len(self._cells)):
                self._relayout_row(i)
            self._refresh_scrollregion()
        except tk.TclError:
            pass
        finally:
            self._relayouting = False

    def _refresh_scrollregion(self):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))


class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.game = 'EO5'
        self.parse_fn, self.revert_fn, self.checker_fn = load_parser(self.game)
        self.file_path = None
        self.rows = []
        self.dirty = False
        self.status_var = tk.StringVar(value='请打开一个 XML 文件')
        root.title('EO XML 翻译表格编辑器')
        root.geometry('1280x720')
        self._build_toolbar()
        self._build_table()
        self._build_statusbar()
        root.protocol('WM_DELETE_WINDOW', self.on_close)

    # ---- 控件 ----

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(8, 6))
        bar.pack(side='top', fill='x')
        ttk.Label(bar, text='解析器：').pack(side='left')
        self.parser_var = tk.StringVar(value=self.game)
        combo = ttk.Combobox(
            bar, textvariable=self.parser_var, values=('EO5', 'EOU2'),
            state='readonly', width=6,
        )
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', self.on_parser_change)
        ttk.Button(bar, text='打开文件', command=self.on_open).pack(side='left', padx=(16, 4))
        ttk.Button(bar, text='重新加载', command=self.on_reload).pack(side='left', padx=4)
        ttk.Button(bar, text='保存', command=self.on_save).pack(side='left', padx=4)

    def _build_table(self):
        self.table = WrappedTableView(self.root, COLUMNS, (10, 58, 58, 78), COLUMN_TITLES)
        self.table.on_cell_edit = self.open_editor
        self.table.on_row_select = self._show_row_status

    def _build_statusbar(self):
        ttk.Label(self.root, textvariable=self.status_var, anchor='w', padding=(8, 4)).pack(
            side='bottom', fill='x'
        )

    # ---- 数据 ----

    def load_file(self, path):
        rows = build_rows(path, self.parse_fn)
        self.file_path = str(path)
        self.rows = rows
        self.dirty = False
        for row in rows:
            row['issues'] = validate_target(row['target'], self.checker_fn)
        self.table.set_rows(rows)
        for i, row in enumerate(rows):
            self.table.set_invalid(i, bool(row['issues']))
        self._refresh_status(f'已加载 {_display_path(path)}')

    def apply_edit(self, row_idx, field, value):
        """应用单元格编辑：translation 编辑后自动重算 target（单向联动）。"""
        row = self.rows[row_idx]
        if field == 'translation':
            row['translation'] = value
            row['target'] = self.revert_fn(value)
            self.table.update_cell(row_idx, 'translation', value)
            self.table.update_cell(row_idx, 'target', row['target'])
        elif field == 'target':
            row['target'] = value
            self.table.update_cell(row_idx, 'target', value)
        else:
            return
        row['issues'] = validate_target(row['target'], self.checker_fn)
        self.table.set_invalid(row_idx, bool(row['issues']))
        self.dirty = True
        self._refresh_status()

    def _refresh_status(self, detail=None):
        bad = sum(1 for r in self.rows if r['issues'])
        if self.file_path:
            base = f'{_display_path(self.file_path)}（{len(self.rows)} 条，{bad} 行有问题）'
        else:
            base = '未打开文件'
        if detail:
            base += '  |  ' + detail
        self.status_var.set(base)

    # ---- 事件 ----

    def on_open(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title='选择 XML 文件',
            filetypes=[('XML files', '*.xml'), ('All files', '*.*')],
        )
        if not path:
            return
        try:
            self.load_file(path)
        except Exception as exc:
            messagebox.showerror('打开失败', str(exc))
            self._refresh_status(f'打开失败：{exc}')

    def on_reload(self):
        if not self.file_path:
            self._refresh_status('请先打开文件')
            return
        if not self._confirm_discard():
            return
        try:
            self.load_file(self.file_path)
        except Exception as exc:
            messagebox.showerror('重新加载失败', str(exc))
            self._refresh_status(f'重新加载失败：{exc}')

    def on_parser_change(self, event=None):
        game = self.parser_var.get()
        if game == self.game:
            return
        if not self._confirm_discard():
            self.parser_var.set(self.game)
            return
        self.game = game
        self.parse_fn, self.revert_fn, self.checker_fn = load_parser(game)
        if self.file_path:
            try:
                self.load_file(self.file_path)
            except Exception as exc:
                messagebox.showerror('切换解析器失败', str(exc))
                self._refresh_status(f'切换解析器失败：{exc}')

    def open_editor(self, row_idx, field):
        if field in ('source', 'idx'):
            self._refresh_status('source / # 列不可编辑')
            return
        row = self.rows[row_idx]
        win = tk.Toplevel(self.root)
        win.title(f'编辑第 {row_idx + 1} 行（id={row["entry_id"]}）· {field}')
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill='both', expand=True)
        text = tk.Text(frame, width=110, height=14, wrap='char')
        ysb = ttk.Scrollbar(frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=ysb.set)
        text.pack(side='left', fill='both', expand=True)
        ysb.pack(side='right', fill='y')
        text.insert('1.0', row[field])
        btns = ttk.Frame(frame)
        btns.pack(side='bottom', pady=(8, 0))

        def ok():
            value = text.get('1.0', 'end-1c')
            self.apply_edit(row_idx, field, value)
            win.destroy()

        def cancel():
            win.destroy()

        ttk.Button(btns, text='确定', command=ok).pack(side='left', padx=4)
        ttk.Button(btns, text='取消', command=cancel).pack(side='left', padx=4)
        text.focus_set()
        win.wait_window()

    def _show_row_status(self, row_idx):
        row = self.rows[row_idx]
        if row['issues']:
            self._refresh_status('；'.join(row['issues']))
        else:
            self._refresh_status(f'当前行（id={row["entry_id"]}）无格式问题')

    def on_save(self):
        if not self.file_path:
            self._refresh_status('请先打开文件')
            return
        for row in self.rows:
            row['issues'] = validate_target(row['target'], self.checker_fn)
        for i, row in enumerate(self.rows):
            self.table.set_invalid(i, bool(row['issues']))
        problem_rows = [(i, row) for i, row in enumerate(self.rows) if row['issues']]
        if problem_rows:
            total = sum(len(r['issues']) for _, r in problem_rows)
            lines = [f'共 {len(problem_rows)} 行、{total} 处格式问题：']
            for i, row in problem_rows[:5]:
                lines.append(f'第 {i + 1} 行（id={row["entry_id"]}）：{row["issues"][0]}')
            if len(problem_rows) > 5:
                lines.append(f'……（其余 {len(problem_rows) - 5} 行）')
            lines.append('\n仍要保存吗？')
            if not messagebox.askyesno('存在格式问题', '\n'.join(lines)):
                self._refresh_status('已取消保存')
                return
        try:
            backup = save_file(self.file_path, self.rows)
            self.dirty = False
            self._refresh_status(
                f'已保存 {Path(self.file_path).name}（备份：{Path(backup).name}）'
            )
        except Exception as exc:
            messagebox.showerror('保存失败', str(exc))
            self._refresh_status(f'保存失败：{exc}')

    def _confirm_discard(self):
        if self.dirty:
            return messagebox.askyesno(
                '未保存的修改', '当前有未保存的修改，继续将丢弃这些修改。是否继续？'
            )
        return True

    def on_close(self):
        if self._confirm_discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    TranslatorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
