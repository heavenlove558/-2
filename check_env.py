# -*- coding: utf-8 -*-
"""环境诊断脚本 —— 逐项检查 GUI 所需组件"""
import sys, os

print("=" * 50)
print("抽油杆三维力学模型 — 环境诊断")
print("=" * 50)

# 1. Python 版本
print(f"\n1. Python: {sys.version}")

# 2. tkinter
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.destroy()
    print("2. tkinter : OK")
except Exception as e:
    print(f"2. tkinter : FAILED — {e}")

# 3. matplotlib + TkAgg
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    print("3. matplotlib (TkAgg): OK")
except Exception as e:
    print(f"3. matplotlib (TkAgg): FAILED — {e}")

# 4. numpy
try:
    import numpy as np
    print("4. numpy : OK")
except Exception as e:
    print(f"4. numpy : FAILED — {e}")

# 5. scipy
try:
    import scipy
    print("5. scipy : OK")
except Exception as e:
    print(f"5. scipy : FAILED — {e}")

# 6. pandas (excel)
try:
    import pandas as pd
    import openpyxl
    print("6. pandas/openpyxl : OK")
except Exception as e:
    print(f"6. pandas/openpyxl : FAILED — {e}")

# 7. 导入项目模块
try:
    import parameters
    import well_trajectory
    import force_model
    print("7. 项目模块 : OK")
except Exception as e:
    print(f"7. 项目模块 : FAILED — {e}")

# 8. 测试 GUI 初始化
try:
    import gui_app
    root = tk.Tk()
    app = gui_app.SuckerRodApp(root)
    print("8. GUI 初始化 : OK")
    root.destroy()
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"8. GUI 初始化 : FAILED — {e}")

print("\n" + "=" * 50)
print("诊断完成")
input("按 Enter 键退出...")
