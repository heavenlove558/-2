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
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

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

        # ---- 底部按钮 ----
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill='x', padx=5, pady=(0, 5))

        ttk.Button(bottom_frame, text='运行模拟',
                   command=self._run_simulation).pack(side='left', padx=5)

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
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    data = []
                    for row in reader:
                        data.append([
                            float(row.get('depth_m', row.get('井深', 0))),
                            float(row.get('inclination_deg', row.get('井斜角', 0))),
                            float(row.get('azimuth_deg', row.get('方位角', 0))),
                        ])
            else:
                import pandas as pd
                df = pd.read_excel(file_path)
                # 尝试自动匹配列名
                col_map = {}
                for col in df.columns:
                    cl = col.lower()
                    if 'depth' in cl or '井深' in col or 'md' in cl:
                        col_map['depth'] = col
                    elif 'incl' in cl or '井斜' in col or 'dev' in cl:
                        col_map['incl'] = col
                    elif 'azim' in cl or '方位' in col:
                        col_map['azim'] = col
                if len(col_map) < 3:
                    # fallback: assume first 3 columns
                    cols = df.columns[:3]
                    col_map = {'depth': cols[0], 'incl': cols[1], 'azim': cols[2]}
                data = [[float(df[col_map['depth']].iloc[i]),
                         float(df[col_map['incl']].iloc[i]),
                         float(df[col_map['azim']].iloc[i])] for i in range(len(df))]

            self.traj_table.set_data(data)
            fname = os.path.basename(file_path)
            self.traj_file_label.config(text=fname, foreground='green')
            self.trajectory_file = file_path
            messagebox.showinfo('导入成功', f'已导入 {len(data)} 行测斜数据')

        except Exception as e:
            messagebox.showerror('导入失败', f'无法读取文件:\n{str(e)}')

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
            ('泵效 %', '43'),
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
        self._create_output_canvas(self.wear_risk_frame, 'wear_risk')

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
            prod['pump_efficiency'] = float(self.prod_entries['泵效 %'].get()) / 100.0
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
        """从表格读取井眼轨迹数据"""
        data = self.traj_table.get_all_data()
        if len(data) < 3:
            return None
        depths = np.array([r[0] for r in data])
        incls = np.array([r[1] for r in data])
        azims = np.array([r[2] for r in data])
        return wt.build_well_trajectory(depths, incls, azims, dl=5.0)

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
                        fluid_depth=prod['fluid_level'],
                        pump_efficiency=prod['pump_efficiency'],
                    )
                    neutral = fm.find_neutral_point(trajectory['depths'], result['P_down'])
                    result['neutral_depth'] = neutral
                    all_results[f'{dia*1000:.0f}'] = result

                # 主线程中更新UI
                self.root.after(0, lambda: self._update_outputs(
                    trajectory, all_results, rod_combo))
                self.root.after(0, lambda: self.status_var.set('模拟完成'))

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.status_var.set(f'错误: {str(e)[:80]}'))
                self.root.after(0, lambda: messagebox.showerror('模拟错误', str(e)))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

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
        fig3 = self.fig_wear_risk
        fig3.clear()

        ax_bend = fig3.add_subplot(131)
        result_44 = all_results['44']
        ax_bend.plot(result_44['sigma_bend'], depths, 'r-', linewidth=1.2)
        ax_bend.fill_betweenx(depths, 0, result_44['sigma_bend'], alpha=0.15, color='red')
        ax_bend.invert_yaxis()
        ax_bend.set_xlabel('弯曲应力 / MPa')
        ax_bend.set_title('弯曲应力 (44mm泵)')
        ax_bend.grid(True, alpha=0.3)

        ax_N = fig3.add_subplot(132)
        N_max = np.maximum(result_44['N_rt_up'], result_44['N_rt_down'])
        ax_N.plot(N_max / 1000.0, depths, 'purple', linewidth=1.2)
        ax_N.fill_betweenx(depths, 0, N_max / 1000.0, alpha=0.15, color='purple')
        ax_N.invert_yaxis()
        ax_N.set_xlabel('支持力 / kN')
        ax_N.set_title('最大支持力 (44mm泵)')
        ax_N.grid(True, alpha=0.3)

        ax_risk = fig3.add_subplot(133)
        K_norm = trajectory['K_deg30m'] / max(trajectory['K_deg30m'].max(), 1e-12)
        sigma_norm = result_44['sigma_bend'] / max(result_44['sigma_bend'].max(), 1e-12)
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

        # 标注
        for ax in [ax_bend, ax_N, ax_risk]:
            ax.axhline(y=result_44['neutral_depth'], color='orange',
                       linestyle='--', linewidth=0.8, alpha=0.7)

        fig3.suptitle('偏磨风险综合分析', fontsize=12, fontweight='bold')
        fig3.tight_layout()
        self.canvas_wear_risk.draw()


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
