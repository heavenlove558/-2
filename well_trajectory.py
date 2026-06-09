"""
模块1：井眼轨迹计算
   - 三次样条插值拟合井斜角/方位角
   - 全角变化率（狗腿度）计算
   - 曲率半径计算
"""
import numpy as np
from scipy.interpolate import CubicSpline
import parameters as pm


def build_well_trajectory(depths, inclinations_deg, azimuths_deg, dl=5.0):
    """
    输入离散测斜数据，输出插值后的连续井眼轨迹。

    参数
    ----
    depths : array, 测深序列 (m)
    inclinations_deg : array, 井斜角 (°)
    azimuths_deg : array, 方位角 (°)
    dl : float, 输出网格步长 (m)

    返回
    ----
    result : dict，包含:
        depths_out : 均匀网格井深
        alpha_rad, alpha_deg : 井斜角
        phi_rad, phi_deg : 方位角
        K : 全角变化率 (rad/m)
        K_deg30m : 狗腿度 (°/30m)
        R_curvature : 曲率半径 (m)
        spline_alpha, spline_phi : 样条函数对象
    """
    # 转换角度为弧度
    alpha_rad = pm.deg_to_rad(inclinations_deg)
    phi_rad = pm.deg_to_rad(azimuths_deg)

    # 三次样条插值，自然边界条件
    spline_alpha = CubicSpline(depths, alpha_rad, bc_type='natural')
    spline_phi = CubicSpline(depths, phi_rad, bc_type='natural')

    # 生成均匀网格输出
    depths_out = np.arange(depths[0], depths[-1] + dl, dl)
    alpha_out = spline_alpha(depths_out)
    phi_out = spline_phi(depths_out)

    # 计算每段的狗腿度和曲率半径
    K = np.zeros(len(depths_out) - 1)
    for i in range(len(K)):
        da = alpha_out[i+1] - alpha_out[i]
        dp = phi_out[i+1] - phi_out[i]
        avg_alpha = (alpha_out[i+1] + alpha_out[i]) / 2.0
        K[i] = np.sqrt((da/dl)**2 + (dp/dl)**2 * np.sin(avg_alpha)**2)

    # 在边界处重复最后一个值以保持数组长度一致
    K_full = np.zeros(len(depths_out))
    K_full[:-1] = K
    K_full[-1] = K[-1]

    # 曲率半径 R = 1/K（处理 K=0 的情况）
    R_curvature = np.full_like(K_full, np.inf)
    mask = K_full > 1e-12
    R_curvature[mask] = 1.0 / K_full[mask]

    return {
        'depths': depths_out,
        'alpha_rad': alpha_out,
        'alpha_deg': pm.rad_to_deg(alpha_out),
        'phi_rad': phi_out,
        'phi_deg': pm.rad_to_deg(phi_out),
        'K': K_full,
        'K_deg30m': pm.rad_to_deg(K_full) * 30.0,  # 转换为 °/30m
        'R_curvature': R_curvature,
        'spline_alpha': spline_alpha,
        'spline_phi': spline_phi,
    }


def create_sp10_9_trajectory(dl=5.0):
    """
    根据论文[1]的SP10-9井描述构造代表性井眼轨迹数据。

    论文描述：
    - 造斜点：1000 m
    - 泵挂：1631 m
    - 造斜段狗腿度 1-7 °/30m（见图7）
    - 水平井（最大井斜角 ~85-90°）

    构造思路：
    - 0-1000m：直井段（α≈0，φ随机的轻微变化）
    - 1000-1400m：增斜段（α从0增至85°，φ≈90°）
    - 1400-1631m：稳斜/水平段（α≈87-90°）
    """
    survey_depths = np.array([
        0, 100, 200, 300, 400, 500, 600, 700, 800, 900,
        1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350,
        1400, 1450, 1500, 1550, 1600, 1631
    ], dtype=float)

    survey_incl = np.array([
        0.0, 0.2, 0.1, 0.3, 0.1, 0.2, 0.3, 0.1, 0.2, 0.1,
        0.5, 5.0, 12.0, 22.0, 35.0, 50.0, 68.0, 80.0,
        86.0, 88.0, 89.0, 87.5, 88.5, 88.0
    ], dtype=float)

    survey_azim = np.array([
        90, 92, 88, 91, 90, 89, 92, 90, 91, 89,
        90, 88, 91, 89, 90, 91, 89, 90,
        90, 91, 89, 90, 90, 90
    ], dtype=float)

    return build_well_trajectory(survey_depths, survey_incl, survey_azim, dl=dl)


def build_trajectory_from_csv(csv_path, dl=5.0):
    """
    从 CSV 文件读取井斜数据。

    CSV格式: depth_m, inclination_deg, azimuth_deg
    """
    import csv
    depths, incls, azims = [], [], []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            depths.append(float(row['depth_m']))
            incls.append(float(row['inclination_deg']))
            azims.append(float(row['azimuth_deg']))
    return build_well_trajectory(
        np.array(depths), np.array(incls), np.array(azims), dl=dl
    )


if __name__ == '__main__':
    traj = create_sp10_9_trajectory(dl=5.0)
    print("=== SP10-9 井眼轨迹计算结果 ===")
    print(f"井深范围: {traj['depths'][0]:.0f} - {traj['depths'][-1]:.0f} m")
    print(f"网格步长: {traj['depths'][1] - traj['depths'][0]:.1f} m")
    print(f"节点数: {len(traj['depths'])}")
    print(f"\n前10个节点:")
    print(f"{'深度(m)':>8} {'井斜(°)':>8} {'方位(°)':>8} {'狗腿度(°/30m)':>14}")
    for i in range(min(10, len(traj['depths']))):
        print(f"{traj['depths'][i]:8.1f} {traj['alpha_deg'][i]:8.2f} "
              f"{traj['phi_deg'][i]:8.2f} {traj['K_deg30m'][i]:14.4f}")
