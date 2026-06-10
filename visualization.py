"""
抽油杆三维力学模型 — 可视化

参照论文[1][2]的输出图表：
  - 杆柱轴向力 vs 井深（上下冲程）
  - 支持力 vs 井深
  - 摩擦力 vs 井深
  - 弯曲应力分布
  - 井眼曲率分布
  - 中和点标注
"""
import numpy as np
import os, glob, shutil
import matplotlib
matplotlib.use('Agg')  # 非交互后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rcParams

# 中文字体设置（直接加载字体文件）
_cache_dir = matplotlib.get_cachedir()
for f in glob.glob(os.path.join(_cache_dir, '*')):
    try:
        if os.path.isfile(f): os.remove(f)
        elif os.path.isdir(f): shutil.rmtree(f, ignore_errors=True)
    except Exception: pass

_font_paths = glob.glob(r'C:\Windows\Fonts\msyh*.ttc')
_font_paths += glob.glob(r'C:\Windows\Fonts\simhei.ttf')
_font_paths += glob.glob(r'C:\Windows\Fonts\simsun*.ttc')
if _font_paths:
    for fp in _font_paths:
        try: fm.fontManager.addfont(fp)
        except Exception: pass
    rcParams['font.sans-serif'] = [fm.FontProperties(fname=_font_paths[0]).get_name(), 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False


def plot_axial_force(result, save_path='output_axial_force.png'):
    """杆柱轴向力 vs 井深（上下冲程对比）— 参照论文[2]图4a"""
    fig, ax = plt.subplots(figsize=(7, 9))
    depths = result['depths']

    ax.plot(result['P_up'] / 1000.0, depths, 'b-', linewidth=1.5, label='上冲程')
    ax.plot(result['P_down'] / 1000.0, depths, 'r--', linewidth=1.5, label='下冲程')
    ax.axvline(x=0, color='gray', linestyle=':', linewidth=0.8)

    # 标注中和点
    ax.axhline(y=result.get('neutral_depth', 0), color='orange',
               linestyle='-.', linewidth=1.0, label=f"中和点 {result.get('neutral_depth', 0):.0f}m")

    ax.invert_yaxis()
    ax.set_xlabel('轴向力 / kN', fontsize=12)
    ax.set_ylabel('井深 / m', fontsize=12)
    ax.set_title('抽油杆柱轴向力随井深变化', fontsize=14)
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_support_force(result, save_path='output_support_force.png'):
    """支持力 vs 井深（上下冲程对比）— 参照论文[2]图4b"""
    fig, ax = plt.subplots(figsize=(7, 9))
    depths = result['depths']

    ax.plot(result['N_rt_up'] / 1000.0, depths, 'b-', linewidth=1.5, label='上冲程')
    ax.plot(result['N_rt_down'] / 1000.0, depths, 'r--', linewidth=1.5, label='下冲程')

    ax.invert_yaxis()
    ax.set_xlabel('支持力 / kN', fontsize=12)
    ax.set_ylabel('井深 / m', fontsize=12)
    ax.set_title('不同井深处抽油杆柱受到油管支持力', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_friction_force(result, save_path='output_friction_force.png'):
    """摩擦力 vs 井深 — 参照论文[2]图4c"""
    fig, ax = plt.subplots(figsize=(7, 9))
    depths = result['depths']

    ax.plot(result['F_fric_up'] / 1000.0, depths, 'b-', linewidth=1.5, label='上冲程')
    ax.plot(result['F_fric_down'] / 1000.0, depths, 'r--', linewidth=1.5, label='下冲程')

    ax.invert_yaxis()
    ax.set_xlabel('摩擦力 / kN', fontsize=12)
    ax.set_ylabel('井深 / m', fontsize=12)
    ax.set_title('不同井深处抽油杆柱受到摩擦力', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_bending_stress(trajectory, result, save_path='output_bending_stress.png'):
    """弯曲应力及杆柱支持力分布 — 参照论文[1]图8"""
    fig, axes = plt.subplots(1, 3, figsize=(14, 10))

    depths = trajectory['depths']

    # 左：弯曲应力
    axes[0].plot(result['sigma_bend'], depths, 'b-', linewidth=1.5)
    axes[0].invert_yaxis()
    axes[0].set_xlabel('弯曲应力 / MPa', fontsize=11)
    axes[0].set_ylabel('井深 / m', fontsize=11)
    axes[0].set_title('弯曲应力')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(left=0)

    # 中：上冲程支持力
    axes[1].plot(result['N_rt_up'] / 1000.0, depths, 'b-', linewidth=1.5, label='上冲程')
    axes[1].invert_yaxis()
    axes[1].set_xlabel('支持力 / kN', fontsize=11)
    axes[1].set_title('上冲程支持力')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_xlim(left=0)

    # 右：下冲程支持力
    axes[2].plot(result['N_rt_down'] / 1000.0, depths, 'r-', linewidth=1.5, label='下冲程')
    axes[2].invert_yaxis()
    axes[2].set_xlabel('支持力 / kN', fontsize=11)
    axes[2].set_title('下冲程支持力')
    axes[2].grid(True, alpha=0.3)
    axes[2].set_xlim(left=0)

    # 标注中和点
    neutral = result.get('neutral_depth', 0)
    for ax in axes:
        ax.axhline(y=neutral, color='orange', linestyle='--', linewidth=0.8, alpha=0.7)

    fig.suptitle('抽油杆柱弯曲应力及支持力分布', fontsize=14)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_well_curvature(trajectory, save_path='output_curvature.png'):
    """井眼曲率分布 — 参照论文[1]图7"""
    fig, ax = plt.subplots(figsize=(7, 6))
    depths = trajectory['depths']

    ax.plot(trajectory['K_deg30m'], depths, 'b-', linewidth=1.5)
    ax.fill_betweenx(depths, 0, trajectory['K_deg30m'], alpha=0.2)

    ax.invert_yaxis()
    ax.set_xlabel('狗腿度 / (°/30m)', fontsize=12)
    ax.set_ylabel('井深 / m', fontsize=12)
    ax.set_title('井眼曲率分布', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_sensitivity_pump_diameter(all_results, save_path='output_sensitivity_pump.png'):
    """不同泵径下支持力对比 — 参照论文[1]图3"""
    fig, ax = plt.subplots(figsize=(8, 9))

    colors = ['blue', 'green', 'orange', 'red', 'purple']
    for (pump_dia, result), color in zip(all_results.items(), colors):
        ax.plot(result['N_rt_up'] / 1000.0, result['depths'],
                color=color, linewidth=1.5, label=f'{pump_dia} mm')

    ax.invert_yaxis()
    ax.set_xlabel('支持力 / kN', fontsize=12)
    ax.set_ylabel('井深 / m', fontsize=12)
    ax.set_title('不同泵径下杆柱支持力', fontsize=14)
    ax.legend(title='泵径')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")


def plot_wear_risk(trajectory, result, save_path='output_wear_risk.png'):
    """
    偏磨风险综合分析图

    标记三个高风险区：
    1. 造斜段（井眼弯曲剧烈区）
    2. 中和点以下区（受压段）
    3. 支持力峰值区
    """
    fig, axes = plt.subplots(1, 4, figsize=(18, 10))
    depths = trajectory['depths']
    neutral = result.get('neutral_depth', 0)

    # 1. 狗腿度
    axes[0].plot(trajectory['K_deg30m'], depths, 'b-', linewidth=1.2)
    axes[0].fill_betweenx(depths, 0, trajectory['K_deg30m'], alpha=0.15, color='blue')
    axes[0].invert_yaxis()
    axes[0].set_xlabel('狗腿度 (°/30m)')
    axes[0].set_title('井眼曲率')

    # 2. 弯曲应力
    axes[1].plot(result['sigma_bend'], depths, 'r-', linewidth=1.2)
    axes[1].fill_betweenx(depths, 0, result['sigma_bend'], alpha=0.15, color='red')
    axes[1].invert_yaxis()
    axes[1].set_xlabel('弯曲应力 (MPa)')
    axes[1].set_title('弯曲应力')

    # 3. 支持力（上下冲程取大值）
    N_max = np.maximum(result['N_rt_up'], result['N_rt_down'])
    axes[2].plot(N_max / 1000.0, depths, 'purple', linewidth=1.2)
    axes[2].fill_betweenx(depths, 0, N_max / 1000.0, alpha=0.15, color='purple')
    axes[2].invert_yaxis()
    axes[2].set_xlabel('最大支持力 (kN)')
    axes[2].set_title('油管支持力')

    # 4. 综合风险评定
    # 归一化各指标后加和
    risk = np.zeros(len(depths))
    K_norm = trajectory['K_deg30m'] / max(trajectory['K_deg30m'].max(), 1e-12)
    sigma_norm = result['sigma_bend'] / max(result['sigma_bend'].max(), 1e-12)
    N_norm = N_max / max(N_max.max(), 1e-12)

    risk = 0.3 * K_norm + 0.3 * sigma_norm + 0.4 * N_norm

    axes[3].plot(risk, depths, 'k-', linewidth=1.5)
    axes[3].fill_betweenx(depths, 0, risk, alpha=0.2, color='black',
                          where=(risk > 0.3))
    axes[3].invert_yaxis()
    axes[3].set_xlabel('综合风险指数')
    axes[3].set_title('偏磨风险综合评定')
    axes[3].set_xlim(0, 1)

    # 标注中和点
    for ax in axes:
        ax.axhline(y=neutral, color='orange', linestyle='--', linewidth=0.8, alpha=0.7)
    axes[0].text(0.02, neutral + 10, f'中和点 {neutral:.0f}m',
                 color='orange', fontsize=9, va='bottom')

    fig.suptitle('抽油杆偏磨风险综合分析', fontsize=14, fontweight='bold')
    plt.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"[✓] {save_path}")
