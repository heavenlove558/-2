# -*- coding: utf-8 -*-
"""
抽油杆三维力学模型 — 图形用户界面

左侧：参数输入（5个标签页）
右侧：模拟输出（matplotlib 图表）
"""
import sys
import os
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import threading

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# ---- 中文字体自动检测 ----
def _setup_chinese_font():
    """直接加载系统字体文件，确保中文正常显示"""
    import matplotlib.font_manager as fm
    import os, glob, shutil

    # 1. 彻底清除 matplotlib 字体缓存
    cache_dir = matplotlib.get_cachedir()
    for f in glob.glob(os.path.join(cache_dir, '*')):
        try:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f) and 'tex' not in f.lower():
                shutil.rmtree(f, ignore_errors=True)
        except Exception:
            pass

    # 2. 直接在系统字体目录查找中文ttf
    font_paths = glob.glob(r'C:\Windows\Fonts\msyh*.ttc')  # 微软雅黑
    font_paths += glob.glob(r'C:\Windows\Fonts\simhei.ttf')  # 黑体
    font_paths += glob.glob(r'C:\Windows\Fonts\simsun*.ttc')  # 宋体

    if not font_paths:
        # macOS / Linux
        font_paths = glob.glob('/System/Library/Fonts/PingFang*.ttc')
        font_paths += glob.glob('/usr/share/fonts/**/*CJK*.ttf', recursive=True)

    if font_paths:
        # 注册字体文件
        for fp in font_paths:
            try:
                fm.fontManager.addfont(fp)
            except Exception:
                pass

        # 用文件名（不含扩展名）作为 font family
        font_name = fm.FontProperties(fname=font_paths[0]).get_name()
        matplotlib.rcParams['font.family'] = 'sans-serif'
        matplotlib.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
        print('Chinese font loaded: {} ({})'.format(font_name, font_paths[0]))
    else:
        matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']
        print('WARNING: No CJK font found')

    matplotlib.rcParams['axes.unicode_minus'] = False
    # 全局字体大小：缩小坐标轴标注
    matplotlib.rcParams.update({
        'font.size': 8,
        'axes.titlesize': 10,
        'axes.labelsize': 8,
        'xtick.labelsize': 7,
        'ytick.labelsize': 7,
        'legend.fontsize': 7,
        'figure.titlesize': 11,
    })

_setup_chinese_font()

import well_trajectory as wt
import force_model as fm
import parameters as pm


# ============================================================
# 可编辑表格组件
# ============================================================
class EditableTable(ttk.Frame):
    """带 添加/删除/编辑 功能的 Treeview 表格"""

    def __init__(self, parent, columns, col_widths, col_editable=None):
        super().__init__(parent)

        self.columns = columns
        self.col_editable = col_editable or [True] * len(columns)
        self.col_widths = col_widths

        # Treeview
        self.tree = ttk.Treeview(self, columns=columns, show='headings',
                                  height=6, selectmode='browse')
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor='center')

        self.tree.bind('<Double-1>', self._on_double_click)

        # 滚动条
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 按钮
        btn_frame = ttk.Frame(self)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        btn_frame.pack(side='bottom', fill='x', pady=2)

        ttk.Button(btn_frame, text='+ 添加行', command=self.add_row).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='- 删除选中', command=self.delete_row).pack(side='left', padx=2)

        # 编辑相关
        self._edit_entry = None
        self._edit_row = None
        self._edit_col = None

    def _on_double_click(self, event):
        """双击编辑"""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            return
        col_idx = int(col.replace('#', '')) - 1
        if col_idx < 0 or col_idx >= len(self.columns):
            return
        if not self.col_editable[col_idx]:
            return
        self._start_edit(row, col_idx)

    def _start_edit(self, row, col_idx):
        self._cancel_edit()
        values = self.tree.item(row, 'values')
        bbox = self.tree.bbox(row, f'#{col_idx + 1}')
        if not bbox:
            return

        self._edit_entry = ttk.Entry(self.tree)
        self._edit_entry.insert(0, values[col_idx])
        self._edit_entry.select_range(0, 'end')
        x, y, w, h = bbox
        self._edit_entry.place(x=x + 2, y=y + 2, width=w - 4, height=h - 4)
        self._edit_entry.focus_set()
        self._edit_entry.bind('<Return>', lambda e: self._commit_edit(row, col_idx))
        self._edit_entry.bind('<FocusOut>', lambda e: self._commit_edit(row, col_idx))
        self._edit_entry.bind('<Escape>', lambda e: self._cancel_edit())
        self._edit_row = row
        self._edit_col = col_idx

    def _commit_edit(self, row, col_idx):
        if self._edit_entry is None:
            return
        new_val = self._edit_entry.get()
        values = list(self.tree.item(row, 'values'))
        values[col_idx] = new_val
        self.tree.item(row, values=values)
        self._cancel_edit()

    def _cancel_edit(self):
        if self._edit_entry:
            self._edit_entry.destroy()
            self._edit_entry = None
        self._edit_row = None
        self._edit_col = None

    def add_row(self, values=None):
        if values is None:
            values = [''] * len(self.columns)
        self.tree.insert('', 'end', values=values)

    def delete_row(self):
        selected = self.tree.selection()
        if selected:
            self.tree.delete(selected[0])

    def get_all_data(self):
        """获取所有行数据，转为浮点数列表"""
        data = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            try:
                row = [float(v) for v in values]
                data.append(row)
            except ValueError:
                continue
        return data

    def set_data(self, data):
        """加载数据"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in data:
            self.tree.insert('', 'end', values=[str(v) for v in row])

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)


# ============================================================
# 历史记录管理对话框
# ============================================================
class HistoryDialog(tk.Toplevel):
    """历史记录浏览器——列出保存的记录，支持加载/重命名/删除"""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title('历史记录管理')
        self.geometry('520x400')
        self.resizable(True, True)
        self.transient(app.root)
        self.grab_set()

        # 记录列表
        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(fill='both', expand=True)

        ttk.Label(list_frame, text='已保存的模拟记录:',
                  font=('', 10, 'bold')).pack(anchor='w')

        list_inner = ttk.Frame(list_frame)
        list_inner.pack(fill='both', expand=True, pady=5)

        scrollbar = ttk.Scrollbar(list_inner)
        scrollbar.pack(side='right', fill='y')

        self.listbox = tk.Listbox(list_inner, yscrollcommand=scrollbar.set,
                                   font=('Consolas', 10), selectmode='single')
        self.listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<Double-1>', lambda e: self._load_selected())
        self.listbox.bind('<Delete>', lambda e: self._delete_selected())
        self.listbox.bind('<F2>', lambda e: self._rename_selected())

        # 按钮
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill='x', pady=(5, 0))

        ttk.Button(btn_frame, text='加载', command=self._load_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='重命名 (F2)', command=self._rename_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='删除 (Del)', command=self._delete_selected).pack(side='left', padx=2)
        ttk.Button(btn_frame, text='关闭', command=self.destroy).pack(side='right', padx=2)

        # 刷新
        self._refresh()

    def _get_files(self):
        d = self.app._save_dir()
        if not os.path.isdir(d):
            return []
        return sorted([f for f in os.listdir(d) if f.endswith('.json')],
                       key=lambda f: os.path.getmtime(os.path.join(d, f)),
                       reverse=True)

    def _refresh(self):
        self.listbox.delete(0, 'end')
        self._records = []
        for fname in self._get_files():
            fpath = os.path.join(self.app._save_dir(), fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    r = __import__('json').load(f)
                ts = r.get('timestamp', '?')
                has_res = ' [有结果]' if 'results' in r else ''
                self.listbox.insert('end', '  {}  |  {}{}'.format(
                    r.get('name', fname), ts, has_res))
                self._records.append((fname, r))
            except Exception:
                self.listbox.insert('end', '  {} (损坏)'.format(fname))
                self._records.append((fname, None))

    def _get_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning('未选择', '请先选择一条记录')
            return None
        idx = sel[0]
        return self._records[idx]

    def _load_selected(self):
        entry = self._get_selected()
        if not entry:
            return
        fname, record = entry
        if record is None:
            messagebox.showerror('文件损坏', '该记录文件已损坏，无法加载')
            return
        self.app._load_record(record)
        self.destroy()

    def _rename_selected(self):
        entry = self._get_selected()
        if not entry:
            return
        fname, record = entry
        old_path = os.path.join(self.app._save_dir(), fname)
        from tkinter import simpledialog
        new = simpledialog.askstring('重命名', '新名称:', parent=self,
                                      initialvalue=record.get('name', fname))
        if not new or new == record.get('name'):
            return
        safe = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in new)
        new_path = os.path.join(self.app._save_dir(), safe + '.json')
        if os.path.exists(new_path) and new_path != old_path:
            messagebox.showerror('重命名失败', '"{}" 已存在'.format(new))
            return
        os.rename(old_path, new_path)
        self._refresh()

    def _delete_selected(self):
        entry = self._get_selected()
        if not entry:
            return
        fname, record = entry
        name = record.get('name', fname) if record else fname
        if not messagebox.askyesno('确认删除', '确定删除记录 "{}"?'.format(name)):
            return
        os.remove(os.path.join(self.app._save_dir(), fname))
        self._refresh()


# ============================================================
# 主应用
# ============================================================
class SuckerRodApp:
    def __init__(self, root):
        self.root = root
        self.root.title('抽油杆三维力学模型分析系统')
        self.root.geometry('1400x850')
        self.root.minsize(1200, 700)

        # 样式
        style = ttk.Style()
        style.theme_use('clam')

        # 井眼轨迹数据
        self.trajectory_data = None  # dict with well trajectory data
        self.trajectory_file = None

        # 模拟结果
        self.sim_results = {}
        self._opt_data = {}

        self._build_ui()

    # ============================================================
    # UI 布局
    # ============================================================
    def _build_ui(self):
        # 主容器
        main_pw = ttk.PanedWindow(self.root, orient='horizontal')
        main_pw.pack(fill='both', expand=True, padx=5, pady=5)

        # ---- 左侧：参数输入 ----
        left_frame = ttk.Frame(main_pw, width=550)
        main_pw.add(left_frame, weight=1)

        left_label = ttk.Label(left_frame, text='参数输入',
                                font=('Microsoft YaHei', 12, 'bold'))
        left_label.pack(anchor='w', pady=(0, 5))

        self.param_notebook = ttk.Notebook(left_frame)
        self.param_notebook.pack(fill='both', expand=True)

        self._build_trajectory_tab()
        self._build_rod_combo_tab()
        self._build_tubing_combo_tab()
        self._build_production_tab()
        self._build_other_tab()

        # ---- 右侧：模拟输出 ----
        right_frame = ttk.Frame(main_pw)
        main_pw.add(right_frame, weight=2)

        right_label = ttk.Label(right_frame, text='模拟输出',
                                 font=('Microsoft YaHei', 12, 'bold'))
        right_label.pack(anchor='w', pady=(0, 5))

        self.output_notebook = ttk.Notebook(right_frame)
        self.output_notebook.pack(fill='both', expand=True)

        # 输出标签页
        self._build_load_tab()
        self._build_dogleg_tab()
        self._build_wear_risk_tab()
        self._build_inertial_tab()
        self._build_optimization_tab()

        # ---- 底部按钮 ----
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill='x', padx=5, pady=(0, 5))

        ttk.Button(bottom_frame, text='运行模拟',
                   command=self._run_simulation).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text='保存记录',
                   command=self._save_record).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text='历史记录',
                   command=self._open_history).pack(side='left', padx=5)

        self.status_var = tk.StringVar(value='就绪')
        status_label = ttk.Label(bottom_frame, textvariable=self.status_var,
                                  foreground='gray')
        status_label.pack(side='right', padx=5)

    # ============================================================
    # Tab1: 井眼轨迹
    # ============================================================
    def _build_trajectory_tab(self):
        frame = ttk.Frame(self.param_notebook, padding=10)
        self.param_notebook.add(frame, text=' 井眼轨迹 ')

        # 导入按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', pady=(0, 5))

        ttk.Button(btn_frame, text='导入 Excel 测斜数据',
                   command=self._import_trajectory).pack(side='left', padx=2)
        self.traj_file_label = ttk.Label(btn_frame, text='未导入',
                                          foreground='gray')
        self.traj_file_label.pack(side='left', padx=10)

        # 数据预览
        ttk.Label(frame, text='测斜数据预览（双击可编辑）:', font=('', 9, 'bold')).pack(anchor='w')

        self.traj_table = EditableTable(
            frame,
            columns=['井深 m', '井斜角 deg', '方位角 deg'],
            col_widths=[120, 120, 120],
            col_editable=[True, True, True],
        )
        self.traj_table.pack(fill='both', expand=True, pady=5)

        # 默认加载 SP10-9 数据
        ttk.Button(frame, text='加载 SP10-9 默认数据',
                   command=self._load_default_trajectory).pack(anchor='w')

    def _import_trajectory(self):
        file_path = filedialog.askopenfilename(
            title='选择测斜数据文件',
            filetypes=[('Excel 文件', '*.xlsx *.xls'), ('CSV 文件', '*.csv'), ('所有文件', '*.*')]
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.csv'):
                import csv as csv_module
                # 尝试多种编码
                raw_data = []
                for enc in ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            reader = csv_module.DictReader(f)
                            raw_data = []
                            for row in reader:
                                raw_data.append(row)
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                if not raw_data:
                    raise ValueError('无法读取CSV文件，请确认编码为UTF-8或GBK')

                # 自动匹配列名
                headers = list(raw_data[0].keys())
                col_map = self._match_columns(headers)
                data = self._parse_rows(raw_data, col_map)

            else:
                import pandas as pd
                df = pd.read_excel(file_path)

                # 跳过全空行
                df = df.dropna(how='all')

                # 如果第一行看起来像标题（包含中文），跳过
                cols_str = [str(c).strip() for c in df.columns]
                headers = cols_str
                col_map = self._match_columns(headers)

                # 提取数据
                data = []
                for i in range(len(df)):
                    try:
                        depth = float(df[col_map['depth']].iloc[i])
                        incl = float(df[col_map['incl']].iloc[i])
                        azim = float(df[col_map['azim']].iloc[i])
                        if not (np.isnan(depth) or np.isnan(incl) or np.isnan(azim)):
                            data.append([depth, incl, azim])
                    except (ValueError, TypeError, KeyError):
                        continue

            # 校验
            if len(data) < 3:
                raise ValueError(
                    '有效数据行不足（需要至少3个测点）。\n'
                    '请确认Excel列名包含: 井深/Depth, 井斜角/Incl, 方位角/Azim\n'
                    '当前识别到的列名: {}'.format(headers))

            # 检查井深是否递增
            depths = [r[0] for r in data]
            if not all(depths[i] < depths[i+1] for i in range(len(depths)-1)):
                raise ValueError(
                    '井深数据必须严格递增！\n'
                    '发现非递增数据点，请检查数据排序。')

            self.traj_table.set_data(data)
            fname = os.path.basename(file_path)
            self.traj_file_label.config(text='{} ({}点)'.format(fname, len(data)),
                                         foreground='green')
            self.trajectory_file = file_path
            messagebox.showinfo('导入成功',
                '已导入 {} 行测斜数据\n井深范围: {:.0f} - {:.0f} m'.format(
                    len(data), depths[0], depths[-1]))

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror('导入失败', str(e))

    def _match_columns(self, headers):
        """智能匹配列名：井深、井斜角、方位角"""
        col_map = {}
        for col in headers:
            cl = str(col).strip().lower()
            # 井深列
            if any(kw in cl for kw in ['depth', 'md', '井深', '测深', '深度', '斜深']):
                col_map['depth'] = col
            # 井斜角列
            elif any(kw in cl for kw in ['incl', 'dev', '井斜', '斜度', '倾角', 'inc']):
                col_map['incl'] = col
            # 方位角列
            elif any(kw in cl for kw in ['azim', 'azi', '方位', 'azm']):
                col_map['azim'] = col

        # 回退：如果匹配不足3列，假设前3列为 depth, incl, azim
        if len(col_map) < 3:
            remain = [c for c in headers if c not in col_map.values()]
            for key, h in zip(['depth', 'incl', 'azim'], headers[:3]):
                if key not in col_map:
                    col_map[key] = h

        return col_map

    def _parse_rows(self, raw_data, col_map):
        """从CSV字典列表提取数值"""
        data = []
        for row in raw_data:
            try:
                depth = float(row.get(col_map['depth'], np.nan))
                incl = float(row.get(col_map['incl'], np.nan))
                azim = float(row.get(col_map['azim'], np.nan))
                if not (np.isnan(depth) or np.isnan(incl) or np.isnan(azim)):
                    data.append([depth, incl, azim])
            except (ValueError, TypeError, KeyError):
                continue
        return data

    def _load_default_trajectory(self):
        """加载 SP10-9 示例数据"""
        survey_depths = [0, 100, 200, 300, 400, 500, 600, 700, 800, 900,
                         1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350,
                         1400, 1450, 1500, 1550, 1600, 1631]
        survey_incl = [0.0, 0.2, 0.1, 0.3, 0.1, 0.2, 0.3, 0.1, 0.2, 0.1,
                       0.5, 5.0, 12.0, 22.0, 35.0, 50.0, 68.0, 80.0,
                       86.0, 88.0, 89.0, 87.5, 88.5, 88.0]
        survey_azim = [90, 92, 88, 91, 90, 89, 92, 90, 91, 89,
                       90, 88, 91, 89, 90, 91, 89, 90,
                       90, 91, 89, 90, 90, 90]
        data = [[d, i, a] for d, i, a in zip(survey_depths, survey_incl, survey_azim)]
        self.traj_table.set_data(data)
        self.traj_file_label.config(text='SP10-9 默认数据', foreground='blue')

    # ============================================================
    # Tab2: 杆柱组合
    # ============================================================
    def _build_rod_combo_tab(self):
        frame = ttk.Frame(self.param_notebook, padding=10)
        self.param_notebook.add(frame, text=' 杆柱组合 ')

        ttk.Label(frame, text='杆柱组合（从井口到泵挂）:', font=('', 9, 'bold')).pack(anchor='w')

        self.rod_table = EditableTable(
            frame,
            columns=['级数', '杆径 mm', '长度 m', '线密度 kg/m'],
            col_widths=[80, 100, 100, 110],
        )
        self.rod_table.pack(fill='both', expand=True, pady=5)

        # 默认数据
        self.rod_table.set_data([
            [1, 22, 571, 3.07],
            [2, 19, 815, 2.30],
            [3, 22, 245, 3.07],
        ])

        ttk.Label(frame, text='提示: 双击单元格编辑数值，+/- 按钮添加删除行',
                  foreground='gray', font=('', 8)).pack(anchor='w')

    # ============================================================
    # Tab3: 油管组合
    # ============================================================
    def _build_tubing_combo_tab(self):
        frame = ttk.Frame(self.param_notebook, padding=10)
        self.param_notebook.add(frame, text=' 油管组合 ')

        ttk.Label(frame, text='油管规格参数:', font=('', 9, 'bold')).pack(anchor='w')

        self.tubing_table = EditableTable(
            frame,
            columns=['段号', '内径 mm', '壁厚 mm', '长度 m', '钢级'],
            col_widths=[80, 100, 100, 100, 80],
            col_editable=[True, True, True, True, False],
        )
        self.tubing_table.pack(fill='both', expand=True, pady=5)

        self.tubing_table.set_data([
            [1, 62, 6.5, 1631, 'N80'],
        ])

    # ============================================================
    # Tab4: 生产参数
    # ============================================================
    def _build_production_tab(self):
        frame = ttk.Frame(self.param_notebook, padding=10)
        self.param_notebook.add(frame, text=' 生产参数 ')

        ttk.Label(frame, text='油井生产参数:', font=('', 9, 'bold')).pack(anchor='w', pady=(0, 10))

        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill='both', expand=True)

        params = [
            ('产液量 m3/d', '17.0'),
            ('产油量 t/d', '3.23'),
            ('含水率 %', '56.1'),
            ('泵径 mm', '44'),
            ('泵挂深度 m', '1631'),
            ('动液面深度 m', '1465'),
            ('冲程 m', '3.0'),
            ('冲次 min-1', '5.0'),
        ]
        self.prod_entries = {}

        for i, (label, default) in enumerate(params):
            row, col = divmod(i, 2)
            ttk.Label(grid_frame, text=label + ':').grid(
                row=row, column=col * 2, sticky='e', padx=5, pady=4)
            entry = ttk.Entry(grid_frame, width=12)
            entry.insert(0, default)
            entry.grid(row=row, column=col * 2 + 1, sticky='w', padx=5, pady=4)
            self.prod_entries[label] = entry

        # 泵效自动计算显示
        self.pump_eff_label = ttk.Label(grid_frame,
                                         text='泵效(自动计算): --%',
                                         foreground='blue', font=('', 9, 'italic'))
        self.pump_eff_label.grid(row=5, column=0, columnspan=4, sticky='w', padx=5, pady=8)

    # ============================================================
    # Tab5: 其他参数
    # ============================================================
    def _build_other_tab(self):
        frame = ttk.Frame(self.param_notebook, padding=10)
        self.param_notebook.add(frame, text=' 其他参数 ')

        ttk.Label(frame, text='材料与模型参数（通常不需修改）:',
                  font=('', 9, 'bold')).pack(anchor='w', pady=(0, 10))

        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill='both', expand=True)

        other = [
            ('钢弹性模量 GPa', '210'),
            ('杆柱密度 kg/m3', '7850'),
            ('井液密度 kg/m3', '1000'),
            ('井液粘度 Pa.s', '0.005'),
            ('杆管摩擦系数', '0.15'),
            ('柱塞配合间隙 mm', '0.053'),
            ('油管内径 mm', '62'),
            ('重力加速度 m/s2', '9.81'),
        ]
        self.other_entries = {}

        for i, (label, default) in enumerate(other):
            row, col = divmod(i, 2)
            ttk.Label(grid_frame, text=label + ':').grid(
                row=row, column=col * 2, sticky='e', padx=5, pady=4)
            entry = ttk.Entry(grid_frame, width=12)
            entry.insert(0, default)
            entry.grid(row=row, column=col * 2 + 1, sticky='w', padx=5, pady=4)
            self.other_entries[label] = entry

    # ============================================================
    # 输出标签页: 载荷与支持力
    # ============================================================
    def _build_load_tab(self):
        self.load_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.load_frame, text=' 载荷与支持力 ')
        self._create_output_canvas(self.load_frame, 'load')

    # ============================================================
    # 输出标签页: 狗腿度
    # ============================================================
    def _build_dogleg_tab(self):
        self.dogleg_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.dogleg_frame, text=' 狗腿度 ')
        self._create_output_canvas(self.dogleg_frame, 'dogleg')

    # ============================================================
    # 输出标签页: 偏磨风险
    # ============================================================
    def _build_wear_risk_tab(self):
        self.wear_risk_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.wear_risk_frame, text=' 偏磨风险 ')

        # 泵径选择器
        ctrl_bar = ttk.Frame(self.wear_risk_frame)
        ctrl_bar.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Label(ctrl_bar, text='泵径:').pack(side='left')
        self.wear_pump_var = tk.StringVar(value='44')
        self.wear_pump_combo = ttk.Combobox(ctrl_bar, textvariable=self.wear_pump_var,
                                              values=[], state='readonly', width=6)
        self.wear_pump_combo.pack(side='left', padx=5)
        self.wear_pump_combo.bind('<<ComboboxSelected>>',
                                   lambda e: self._draw_wear_risk())

        self._create_output_canvas(self.wear_risk_frame, 'wear_risk')

    def _build_inertial_tab(self):
        frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(frame, text=' 惯性接触力 ')
        self._create_output_canvas(frame, 'inertial')

    def _build_optimization_tab(self):
        frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(frame, text=' 杆柱优化 ')

        # 泵径选择
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill='x', padx=5, pady=(5, 0))
        ttk.Label(ctrl, text='泵径:').pack(side='left')
        self.opt_pump_var = tk.StringVar(value='44')
        self.opt_pump_combo = ttk.Combobox(ctrl, textvariable=self.opt_pump_var,
                                             values=[], state='readonly', width=6)
        self.opt_pump_combo.pack(side='left', padx=5)
        self.opt_pump_combo.bind('<<ComboboxSelected>>',
                                  lambda e: self._draw_optimization())

        self._create_output_canvas(frame, 'optimization')

    def _create_output_canvas(self, parent, name):
        """在给定的 frame 中创建 matplotlib 画布"""
        setattr(self, f'fig_{name}', Figure(figsize=(7, 5), dpi=100))
        fig = getattr(self, f'fig_{name}')

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

        # 工具栏
        toolbar = NavigationToolbar2Tk(canvas, parent)
        toolbar.update()

        setattr(self, f'canvas_{name}', canvas)

    # ============================================================
    # 参数汇总 + 运行模拟
    # ============================================================
    def _get_all_params(self):
        """汇总所有输入参数"""
        # 生产参数
        prod = {}
        try:
            prod['liquid_rate'] = float(self.prod_entries['产液量 m3/d'].get())
            prod['oil_rate'] = float(self.prod_entries['产油量 t/d'].get())
            prod['water_cut'] = float(self.prod_entries['含水率 %'].get()) / 100.0
            prod['pump_diameter'] = float(self.prod_entries['泵径 mm'].get()) / 1000.0  # m
            prod['pump_depth'] = float(self.prod_entries['泵挂深度 m'].get())
            prod['fluid_level'] = float(self.prod_entries['动液面深度 m'].get())
            prod['stroke'] = float(self.prod_entries['冲程 m'].get())
            prod['stroke_rate'] = float(self.prod_entries['冲次 min-1'].get())
            # 泵效 = 实际产液量 / 理论排量 × 100%
            # 理论排量 = 1440 × πD²/4 × S × N  (m³/d)
            liquid_rate = prod['liquid_rate']  # m³/d
            D_p = prod['pump_diameter']  # m
            S = prod['stroke']  # m
            N = prod['stroke_rate']  # min⁻¹
            theoretical_rate = 1440.0 * np.pi * D_p**2 / 4.0 * S * N
            if theoretical_rate > 0:
                eff = liquid_rate / theoretical_rate * 100.0
            else:
                eff = 43.0  # 默认值
            prod['pump_efficiency'] = eff / 100.0
            # 更新显示
            self.pump_eff_label.config(
                text='泵效(自动计算): {:.1f}% (理论排量 {:.1f} m3/d)'.format(eff, theoretical_rate))
        except ValueError as e:
            messagebox.showerror('输入错误', f'生产参数格式错误:\n{str(e)}')
            return None

        # 其他参数
        other = {}
        try:
            other['E_steel'] = float(self.other_entries['钢弹性模量 GPa'].get())
            other['rho_rod'] = float(self.other_entries['杆柱密度 kg/m3'].get())
            other['rho_fluid'] = float(self.other_entries['井液密度 kg/m3'].get())
            other['mu_fluid'] = float(self.other_entries['井液粘度 Pa.s'].get())
            other['f_friction'] = float(self.other_entries['杆管摩擦系数'].get())
            other['delta'] = float(self.other_entries['柱塞配合间隙 mm'].get()) / 1000.0
            other['D_tube'] = float(self.other_entries['油管内径 mm'].get()) / 1000.0
            other['g'] = float(self.other_entries['重力加速度 m/s2'].get())
        except ValueError as e:
            messagebox.showerror('输入错误', f'其他参数格式错误:\n{str(e)}')
            return None

        # 更新全局参数
        pm.E_STEEL = other['E_steel'] * 1e9
        pm.RHO_R = other['rho_rod']
        pm.RHO_L = other['rho_fluid']
        pm.MU_OIL = other['mu_fluid']
        pm.F_FRICTION = other['f_friction']
        pm.DELTA = other['delta']
        pm.D_TUBE = other['D_tube']
        pm.G = other['g']

        return {'prod': prod, 'other': other}

    def _get_trajectory_from_table(self):
        """从表格读取井眼轨迹数据（带校验）"""
        data = self.traj_table.get_all_data()
        if len(data) < 3:
            messagebox.showerror('数据不足',
                '测斜数据至少需要3个点，当前仅有 {} 个有效数据行。\n'
                '请先导入Excel文件或点击"加载SP10-9默认数据"。'.format(len(data)))
            return None

        depths = np.array([r[0] for r in data])
        incls = np.array([r[1] for r in data])
        azims = np.array([r[2] for r in data])

        # 检查井深递增
        diffs = np.diff(depths)
        if np.any(diffs <= 0):
            bad_idx = np.where(diffs <= 0)[0]
            messagebox.showerror('数据错误',
                '井深数据必须严格递增！\n'
                '第{}行附近存在非递增数据点。\n'
                '请在表格中修正或重新导入。'.format(bad_idx[0] + 1))
            return None

        try:
            return wt.build_well_trajectory(depths, incls, azims, dl=5.0)
        except Exception as e:
            messagebox.showerror('轨迹计算失败',
                '三次样条插值失败:\n{}\n请检查数据是否有突变。'.format(str(e)))
            return None

    def _get_rod_combo_from_table(self):
        """从表格读取杆柱组合"""
        data = self.rod_table.get_all_data()
        if not data:
            return [(0.022, 1.0)]
        total_len = sum(r[2] for r in data)
        if total_len < 1:
            return [(0.022, 1.0)]
        return [(r[1] / 1000.0, r[2] / total_len) for r in data]

    def _run_simulation(self):
        """运行模拟（在后台线程中）"""
        params = self._get_all_params()
        if params is None:
            return

        trajectory = self._get_trajectory_from_table()
        if trajectory is None:
            messagebox.showerror('数据错误', '请先导入或加载井眼轨迹数据！')
            return

        # 截断到泵挂深度（杆柱只到泵，不到井底）
        pump_depth = params['prod']['pump_depth']
        mask = trajectory['depths'] <= pump_depth + 1e-6
        for key in ['depths', 'alpha_rad', 'alpha_deg', 'phi_rad', 'phi_deg',
                     'K', 'K_deg30m', 'R_curvature']:
            if key in trajectory:
                trajectory[key] = trajectory[key][mask]
        print('Trajectory truncated to pump depth: {:.0f}m, {} nodes'.format(
            pump_depth, len(trajectory['depths'])))

        self.status_var.set('正在运行模拟...')
        self.root.update()

        # 在后台线程中运行以避免 UI 冻结
        def _run():
            try:
                prod = params['prod']
                rod_combo = self._get_rod_combo_from_table()

                # 构建杆径数组
                rod_diameters = fm.build_rod_diameter_array(
                    trajectory['depths'], prod['pump_depth'], rod_combo)

                # 对4种泵径分别计算
                pump_dias = [0.028, 0.032, 0.038, 0.044]  # 28, 32, 38, 44 mm
                all_results = {}
                for dia in pump_dias:
                    result = fm.solve_axial_forces(
                        trajectory, rod_diameters,
                        pump_diameter_m=dia,
                        stroke=prod['stroke'],
                        stroke_rate=prod['stroke_rate'],
                        pump_depth=prod['pump_depth'],
                        fluid_level=prod['fluid_level'],
                        pump_efficiency=prod['pump_efficiency'],
                    )
                    neutral = fm.find_neutral_point(trajectory['depths'], result['P_down'])
                    result['neutral_depth'] = neutral
                    all_results[f'{dia*1000:.0f}'] = result

                # 惯性接触力分析
                inertial = fm.calc_inertial_contact(
                    trajectory, rod_diameters,
                    prod['stroke'], prod['stroke_rate'])
                self._opt_data['inertial'] = inertial

                # 疲劳分析
                import optimization as opt
                fatigue = opt.analyze_fatigue(all_results, rod_diameters, grade='D')
                self._opt_data = {
                    'fatigue': fatigue,
                    'rod_diameters': rod_diameters,
                    'rod_combo': rod_combo,
                }

                # 无压缩优化（三级：底部22mm -> 中部19mm -> 顶部22mm）
                dias_mm = [22, 19, 22]
                prod_params = prod
                opt_combo, opt_iter, opt_min_p = opt.optimize_compression_free(
                    prod_params['pump_diameter'], prod_params['pump_depth'],
                    prod_params['fluid_level'],
                    prod_params['stroke'], prod_params['stroke_rate'],
                    dias_mm, trajectory,
                    pump_efficiency=prod_params['pump_efficiency'])
                self._opt_data['opt_combo'] = opt_combo
                self._opt_data['opt_iter'] = opt_iter
                self._opt_data['opt_min_p'] = opt_min_p

                # 主线程中更新UI
                self.root.after(0, lambda: self._safe_update(trajectory, all_results, rod_combo))

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.status_var.set('Error: {}'.format(str(e)[:80])))
                self.root.after(0, lambda: messagebox.showerror('模拟错误', str(e)))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    # ============================================================
    # 历史记录管理
    # ============================================================
    def _save_dir(self):
        d = os.path.join(os.path.dirname(__file__), 'saved_runs')
        os.makedirs(d, exist_ok=True)
        return d

    def _save_record(self):
        """保存当前参数和结果为一条历史记录"""
        from tkinter import simpledialog
        name = simpledialog.askstring('保存记录', '请输入记录名称:', parent=self.root)
        if not name:
            return

        # 收集数据
        record = {
            'name': name,
            'timestamp': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trajectory': self.traj_table.get_all_data(),
            'rod_combo': self.rod_table.get_all_data(),
            'tubing_combo': self.tubing_table.get_all_data(),
            'prod_params': {k: v.get() for k, v in self.prod_entries.items()},
            'other_params': {k: v.get() for k, v in self.other_entries.items()},
        }
        # 模拟结果（如果有）
        if self.sim_results:
            summary = {}
            for label, r in self.sim_results.items():
                summary[label] = {
                    'neutral_depth': round(float(r['neutral_depth']), 1),
                    'P_up_max_kN': round(float(r['P_up'].max() / 1000.0), 1),
                    'P_down_min_kN': round(float(r['P_down'].min() / 1000.0), 1),
                    'max_sigma_bend_MPa': round(float(r['sigma_bend'].max()), 2),
                }
            record['results'] = summary

        # 写入文件
        safe_name = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in name)
        fpath = os.path.join(self._save_dir(), safe_name + '.json')
        with open(fpath, 'w', encoding='utf-8') as f:
            __import__('json').dump(record, f, ensure_ascii=False, indent=2)

        self.status_var.set('已保存: {}'.format(name))
        messagebox.showinfo('保存成功', '记录 "{}" 已保存'.format(name))

    def _open_history(self):
        """打开历史记录管理对话框"""
        HistoryDialog(self)

    def _load_record(self, record):
        """加载一条历史记录到当前界面"""
        # 井眼轨迹
        if record.get('trajectory'):
            self.traj_table.set_data(record['trajectory'])
            self.traj_file_label.config(text='已加载: {}'.format(record.get('name', '?')),
                                         foreground='blue')
        # 杆柱组合
        if record.get('rod_combo'):
            self.rod_table.set_data(record['rod_combo'])
        # 油管组合
        if record.get('tubing_combo'):
            self.tubing_table.set_data(record['tubing_combo'])
        # 生产参数
        for k, v in record.get('prod_params', {}).items():
            if k in self.prod_entries:
                self.prod_entries[k].delete(0, 'end')
                self.prod_entries[k].insert(0, v)
        # 其他参数
        for k, v in record.get('other_params', {}).items():
            if k in self.other_entries:
                self.other_entries[k].delete(0, 'end')
                self.other_entries[k].insert(0, v)

        self.status_var.set('已加载记录: {}'.format(record.get('name', '?')))
        messagebox.showinfo('加载成功',
            '已加载 "{}"\n时间: {}\n含模拟结果: {}'.format(
                record.get('name', '?'),
                record.get('timestamp', '?'),
                '是' if 'results' in record else '否'))

    def _draw_wear_risk(self):
        """根据当前选中的泵径重绘偏磨风险图表"""
        if not hasattr(self, '_wear_results') or not self._wear_results:
            return
        dia = self.wear_pump_var.get()
        if dia not in self._wear_results:
            return

        trajectory = self._wear_trajectory
        result = self._wear_results[dia]
        depths = trajectory['depths']

        fig = self.fig_wear_risk
        fig.clear()

        ax_bend = fig.add_subplot(131)
        ax_bend.plot(result['sigma_bend'], depths, 'r-', linewidth=1.2)
        ax_bend.fill_betweenx(depths, 0, result['sigma_bend'], alpha=0.15, color='red')
        ax_bend.invert_yaxis()
        ax_bend.set_xlabel('弯曲应力 / MPa')
        ax_bend.set_title('弯曲应力 ({}mm)'.format(dia))
        ax_bend.grid(True, alpha=0.3)

        ax_N = fig.add_subplot(132)
        N_max = np.maximum(result['N_rt_up'], result['N_rt_down'])
        ax_N.plot(N_max / 1000.0, depths, 'purple', linewidth=1.2)
        ax_N.fill_betweenx(depths, 0, N_max / 1000.0, alpha=0.15, color='purple')
        ax_N.invert_yaxis()
        ax_N.set_xlabel('支持力 / kN')
        ax_N.set_title('最大支持力 ({}mm)'.format(dia))
        ax_N.grid(True, alpha=0.3)

        ax_risk = fig.add_subplot(133)
        K_norm = trajectory['K_deg30m'] / max(trajectory['K_deg30m'].max(), 1e-12)
        sigma_norm = result['sigma_bend'] / max(result['sigma_bend'].max(), 1e-12)
        N_norm = N_max / max(N_max.max(), 1e-12)
        risk = 0.3 * K_norm + 0.3 * sigma_norm + 0.4 * N_norm
        ax_risk.plot(risk, depths, 'k-', linewidth=1.5)
        ax_risk.fill_betweenx(depths, 0, risk, alpha=0.2, color='black',
                               where=(risk > 0.3))
        ax_risk.invert_yaxis()
        ax_risk.set_xlabel('风险指数')
        ax_risk.set_title('偏磨综合风险')
        ax_risk.set_xlim(0, 1)
        ax_risk.grid(True, alpha=0.3)

        for ax in [ax_bend, ax_N, ax_risk]:
            ax.axhline(y=result['neutral_depth'], color='orange',
                       linestyle='--', linewidth=0.8, alpha=0.7)

        fig.suptitle('偏磨风险综合分析 ({}mm泵)'.format(dia),
                     fontsize=12, fontweight='bold')
        fig.tight_layout()
        self.canvas_wear_risk.draw()

    def _draw_inertial(self):
        """绘制冲程转换时的惯性接触力"""
        if not hasattr(self, '_opt_data') or not self._opt_data:
            return
        inertial = self._opt_data.get('inertial')
        if inertial is None:
            return

        depths = inertial['depths']
        fig = self.fig_inertial
        fig.clear()

        # 左: 惯性压缩力 vs 井深
        ax1 = fig.add_subplot(131)
        ax1.plot(inertial['F_inertial'] / 1000.0, depths, 'b-', linewidth=1.2)
        ax1.fill_betweenx(depths, 0, inertial['F_inertial'] / 1000.0,
                           alpha=0.15, color='blue')
        ax1.invert_yaxis()
        ax1.set_xlabel('惯性压缩力 / kN')
        ax1.set_ylabel('井深 / m')
        ax1.set_title('惯性压缩力 (下冲程启动)')
        ax1.grid(True, alpha=0.3)

        # 中: 每米接触力 vs 井深
        ax2 = fig.add_subplot(132)
        ax2.plot(inertial['N_per_m'], depths, 'r-', linewidth=1.2)
        ax2.fill_betweenx(depths, 0, inertial['N_per_m'],
                           alpha=0.15, color='red')
        ax2.invert_yaxis()
        ax2.set_xlabel('接触力 / (N/m)')
        ax2.set_title('惯性接触力密度')
        ax2.grid(True, alpha=0.3)
        # 标出最大值
        max_idx = np.argmax(inertial['N_per_m'])
        ax2.annotate('{:.1f} N/m @ {:.0f}m'.format(
            inertial['N_per_m'][max_idx], depths[max_idx]),
            xy=(inertial['N_per_m'][max_idx], depths[max_idx]),
            fontsize=8, color='darkred')

        # 右: 与狗腿度对比
        ax3 = fig.add_subplot(133)
        ax3.plot(inertial['N_per_m'], depths, 'r-', linewidth=1.2, label='惯性接触力密度')
        # 双y轴: 狗腿度
        ax3b = ax3.twiny()
        if hasattr(self, '_wear_trajectory'):
            K = self._wear_trajectory['K_deg30m']
            ax3b.plot(K, depths, 'b--', linewidth=0.8, alpha=0.5, label='狗腿度')
            ax3b.set_xlabel('狗腿度 / (°/30m)', color='blue')
        ax3.invert_yaxis()
        ax3.set_xlabel('接触力 / (N/m)', color='red')
        ax3.set_title('惯性接触力 vs 狗腿度')
        ax3.grid(True, alpha=0.3)
        ax3.legend(fontsize=7, loc='lower right')

        fig.suptitle('冲程转换惯性接触力分析 (a_max={:.3f} m/s2)'.format(inertial['a_max']),
                     fontsize=11, fontweight='bold')
        fig.tight_layout()
        self.canvas_inertial.draw()

    def _draw_optimization(self):
        """绘制杆柱优化图表：应力幅值 + 疲劳寿命 + 等强度推荐"""
        if not hasattr(self, '_opt_data') or not self._opt_data:
            return
        dia_label = self.opt_pump_var.get()
        fatigue = self._opt_data['fatigue']
        if dia_label not in fatigue:
            return
        f = fatigue[dia_label]
        rod_diameters = self._opt_data['rod_diameters']
        depths = np.arange(len(f['sigma_a'])) * 5.0  # approximate

        fig = self.fig_optimization
        fig.clear()

        # 获取实际井深（从已保存的轨迹数据）
        depths = np.array(self._opt_data.get('_depths_opt', range(len(f['sigma_a']))))

        # 左: 应力幅值 vs 井深
        ax1 = fig.add_subplot(221)
        ax1.plot(f['sigma_a'], depths, 'b-', linewidth=1.5)
        ax1.fill_betweenx(depths, 0, f['sigma_a'], alpha=0.15, color='blue')
        ax1.invert_yaxis()
        ax1.set_xlabel('应力幅值 / MPa')
        ax1.set_ylabel('井深 / m')
        ax1.set_title('应力幅值分布 ({}mm泵)'.format(dia_label))
        ax1.grid(True, alpha=0.3)

        # 右: 疲劳寿命柱状图
        ax2 = fig.add_subplot(222)
        pump_labels = list(self._opt_data['fatigue'].keys())
        years_list = [self._opt_data['fatigue'][k]['years'] for k in pump_labels]
        colors = ['green' if y > 10 else 'orange' if y > 3 else 'red' for y in years_list]
        bars = ax2.bar(pump_labels, [min(y, 99) for y in years_list], color=colors)
        ax2.set_xlabel('泵径 / mm')
        ax2.set_ylabel('预估疲劳寿命 / 年')
        ax2.set_title('疲劳寿命对比')
        for bar, y in zip(bars, years_list):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     '{:.1f}'.format(y), ha='center', fontsize=8)
        ax2.axhline(y=3, color='orange', linestyle='--', alpha=0.5, label='3年警戒线')
        ax2.axhline(y=10, color='green', linestyle='--', alpha=0.5, label='10年目标线')
        ax2.legend(fontsize=7)

        # 左下: PL 对比
        ax3 = fig.add_subplot(223)
        pl_list = [self._opt_data['fatigue'][k]['PL'] for k in pump_labels]
        colors_pl = ['green' if p < 85 else 'orange' if p < 100 else 'red' for p in pl_list]
        bars3 = ax3.bar(pump_labels, pl_list, color=colors_pl)
        ax3.set_xlabel('泵径 / mm')
        ax3.set_ylabel('应力范围比 PL / %')
        ax3.set_title('应力范围比 (PL<100% 合格)')
        ax3.axhline(y=100, color='red', linestyle='--', alpha=0.5, label='100%上限')
        for bar, p in zip(bars3, pl_list):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     '{:.0f}%'.format(p), ha='center', fontsize=8)
        ax3.legend(fontsize=7)

        # 右下: 杆柱优化推荐
        ax4 = fig.add_subplot(224)
        ax4.axis('off')
        opt_combo = self._opt_data.get('opt_combo', [])
        opt_iter = self._opt_data.get('opt_iter', 0)
        opt_min_p = self._opt_data.get('opt_min_p', 0)
        status = '无受压' if opt_min_p >= 0 else '仍有 {:.1f}kN 受压'.format(abs(opt_min_p)/1000)
        lines = ['杆柱优化推荐 (迭代{}次, {}):'.format(opt_iter, status), '']
        total = sum(L for _, L, _ in opt_combo)
        for d, L, pct in opt_combo:
            lines.append('  {}mm x {:.0f}m ({:.0f}%)'.format(d, L, pct))
        lines.append('')
        lines.append('总长: {:.0f} m'.format(total))
        lines.append('')
        max_sa_label = dia_label
        if max_sa_label in fatigue:
            lines.append('最大应力幅: {:.1f} MPa @ {:.0f}m'.format(
                fatigue[max_sa_label]['max_sigma_a'],
                fatigue[max_sa_label]['max_sigma_a_depth']))
            lines.append('预估疲劳寿命: {:.1f} 年'.format(
                fatigue[max_sa_label]['years']))
            lines.append('应力范围比 PL: {:.0f}%'.format(
                fatigue[max_sa_label]['PL']))
        ax4.text(0.05, 0.95, '\n'.join(lines), transform=ax4.transAxes,
                 fontsize=8, verticalalignment='top', fontfamily='monospace')

        fig.suptitle('杆柱优化分析 ({}mm泵, D级杆)'.format(dia_label),
                     fontsize=12, fontweight='bold')
        fig.tight_layout()
        self.canvas_optimization.draw()

    def _safe_update(self, trajectory, all_results, rod_combo):
        """带错误保护的图表更新"""
        try:
            self._update_outputs(trajectory, all_results, rod_combo)
            self.status_var.set('模拟完成')
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print(err_msg, file=sys.stderr)
            self.status_var.set('图表更新失败: {}'.format(str(e)[:60]))
            messagebox.showerror('图表错误',
                '计算完成但图表绘制失败:\n\n{}\n\n详情见终端输出'.format(str(e)))

    # ============================================================
    # 更新图表
    # ============================================================
    def _update_outputs(self, trajectory, all_results, rod_combo):
        """用计算结果更新所有输出图表"""
        self.sim_results = all_results

        # ---- 图表1: 载荷与支持力 ----
        fig = self.fig_load
        fig.clear()
        depths = trajectory['depths']

        # 上冲程载荷 (2x2 布局)
        ax1 = fig.add_subplot(221)
        for label, result in all_results.items():
            ax1.plot(result['P_up'] / 1000.0, depths, linewidth=1.2, label=f'{label}mm')
        ax1.invert_yaxis()
        ax1.set_xlabel('轴向力 / kN')
        ax1.set_ylabel('井深 / m')
        ax1.set_title('上冲程轴向力')
        ax1.legend(fontsize=7, loc='lower right')
        ax1.axvline(x=0, color='gray', linestyle=':')
        ax1.grid(True, alpha=0.3)

        # 下冲程载荷
        ax2 = fig.add_subplot(222)
        for label, result in all_results.items():
            ax2.plot(result['P_down'] / 1000.0, depths, linewidth=1.2, label=f'{label}mm')
        ax2.invert_yaxis()
        ax2.set_xlabel('轴向力 / kN')
        ax2.set_title('下冲程轴向力')
        ax2.legend(fontsize=7, loc='lower right')
        ax2.axvline(x=0, color='gray', linestyle=':')
        ax2.grid(True, alpha=0.3)

        # 上冲程支持力
        ax3 = fig.add_subplot(223)
        for label, result in all_results.items():
            ax3.plot(result['N_rt_up'] / 1000.0, depths, linewidth=1.2, label=f'{label}mm')
        ax3.invert_yaxis()
        ax3.set_xlabel('支持力 / kN')
        ax3.set_ylabel('井深 / m')
        ax3.set_title('上冲程油管支持力')
        ax3.legend(fontsize=7)
        ax3.grid(True, alpha=0.3)

        # 下冲程支持力
        ax4 = fig.add_subplot(224)
        for label, result in all_results.items():
            ax4.plot(result['N_rt_down'] / 1000.0, depths, linewidth=1.2, label=f'{label}mm')
        ax4.invert_yaxis()
        ax4.set_xlabel('支持力 / kN')
        ax4.set_title('下冲程油管支持力')
        ax4.legend(fontsize=7)
        ax4.grid(True, alpha=0.3)

        fig.suptitle(f'不同泵径下杆柱载荷与支持力对比 (杆柱: '
                     + ' + '.join([f'{d*1000:.0f}mm' for d, _ in rod_combo]) + ')',
                     fontsize=12, fontweight='bold')
        fig.tight_layout()
        self.canvas_load.draw()

        # ---- 图表2: 狗腿度 ----
        fig2 = self.fig_dogleg
        fig2.clear()
        ax = fig2.add_subplot(111)
        ax.plot(trajectory['K_deg30m'], depths, 'b-', linewidth=1.5)
        ax.fill_betweenx(depths, 0, trajectory['K_deg30m'], alpha=0.2)
        ax.invert_yaxis()
        ax.set_xlabel('狗腿度 / (°/30m)')
        ax.set_ylabel('井深 / m')
        ax.set_title('井眼狗腿度随井深变化')
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)

        # 标注中和点
        for label, result in all_results.items():
            ax.axhline(y=result['neutral_depth'], linestyle='--', alpha=0.4,
                       linewidth=0.8, label=f'中和点 {label}mm: {result["neutral_depth"]:.0f}m')
        ax.legend(fontsize=7, loc='upper right')

        fig2.tight_layout()
        self.canvas_dogleg.draw()

        # ---- 图表3: 偏磨风险 ----
        # 存储数据供切换泵径时重绘
        self._wear_trajectory = trajectory
        self._wear_results = all_results
        # 优化图表也用这些深度
        if hasattr(self, '_opt_data') and self._opt_data:
            self._opt_data['_depths_opt'] = trajectory['depths']
        # 更新泵径选择器选项
        dias = list(all_results.keys())
        self.wear_pump_combo['values'] = dias
        self.opt_pump_combo['values'] = dias
        if self.wear_pump_var.get() not in dias:
            self.wear_pump_var.set(dias[-1])
        if self.opt_pump_var.get() not in dias:
            self.opt_pump_var.set(dias[-1])
        self._draw_wear_risk()
        self._draw_inertial()
        self._draw_optimization()


# ============================================================
# 入口
# ============================================================
def main():
    root = tk.Tk()
    app = SuckerRodApp(root)
    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # 写入错误日志
        err_msg = ''.join(traceback.format_exc())
        log_path = os.path.join(os.path.dirname(__file__), 'gui_error.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(err_msg)
        # 弹出错误对话框
        try:
            from tkinter import messagebox
            messagebox.showerror('启动失败', f'错误已写入 gui_error.log\n\n{str(e)}')
        except Exception:
            pass
        print(err_msg)
        sys.exit(1)
