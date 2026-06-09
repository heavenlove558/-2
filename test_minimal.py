# -*- coding: utf-8 -*-
"""逐步诊断 —— 每步结果写入 test_result.txt"""
import sys, os, traceback

LOG = open('test_result.txt', 'w', encoding='utf-8')

def check(step, code):
    try:
        exec(code)
        LOG.write("[OK] " + step + "\n")
        LOG.flush()
        return True
    except Exception:
        LOG.write("[FAIL] " + step + "\n")
        LOG.write(traceback.format_exc() + "\n")
        LOG.flush()
        return False

checks = [
    ("Python import", "import sys"),
    ("tkinter", "import tkinter as tk; r=tk.Tk(); r.withdraw(); r.destroy()"),
    ("numpy", "import numpy"),
    ("scipy", "import scipy"),
    ("matplotlib + TkAgg", "import matplotlib; matplotlib.use('TkAgg')"),
    ("matplotlib Figure", "from matplotlib.figure import Figure"),
    ("matplotlib Tk Canvas", "from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg"),
    ("pandas + openpyxl", "import pandas; import openpyxl"),
    ("项目 parameters", "import parameters"),
    ("项目 well_trajectory", "import well_trajectory"),
    ("项目 force_model", "import force_model"),
    ("项目 visualization", "import visualization"),
    ("项目 gui_app (导入)", "import gui_app"),
]

all_ok = True
for name, code in checks:
    if not check(name, code):
        all_ok = False
        break

LOG.write("\n" + "="*40 + "\n")
LOG.write("Result: " + ("ALL " + str(len(checks)) + " PASS" if all_ok else "FAILED") + "\n")
LOG.close()

if all_ok:
    try:
        import gui_app
        import tkinter as tk
        root = tk.Tk()
        gui_app.SuckerRodApp(root)
        root.mainloop()
    except Exception:
        with open('test_result.txt', 'a', encoding='utf-8') as f:
            f.write("\n[FAIL] GUI startup crashed!\n")
            f.write(traceback.format_exc())
else:
    import time
    print("FAILED - open test_result.txt")
    time.sleep(30)
