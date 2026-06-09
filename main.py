"""
抽油杆三维力学模型 — 主入口

运行完整的力学分析流程：
  1. 井眼轨迹计算
  2. 受力分析（上下冲程）
  3. 支持力/摩擦力/弯曲应力
  4. 中和点定位
  5. 偏磨风险评定
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import well_trajectory as wt
import force_model as fm
import parameters as pm
import visualization as vis
import os


def run_analysis(params=None, output_dir='output'):
    """运行完整分析流程"""
    if params is None:
        params = pm.SP10_9_PARAMS

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  抽油杆三维力学模型 — 偏磨分析")
    print("=" * 60)
    print(f"\n生产参数:")
    print(f"  冲程: {params['stroke']} m, 冲次: {params['stroke_rate']} min-1")
    print(f"  泵径: {params['pump_diameter']*1000:.0f} mm, 泵挂: {params['pump_depth']} m")
    print(f"  动液面: {params['fluid_level']} m")

    # ---- Step 1: 井眼轨迹 ----
    print("\n[Step 1] 井眼轨迹计算...")
    trajectory = wt.create_sp10_9_trajectory(dl=5.0)
    print(f"  井深: {trajectory['depths'][0]:.0f} - {trajectory['depths'][-1]:.0f} m")
    print(f"  网格: {len(trajectory['depths'])} 节点, 步长 {trajectory['depths'][1]-trajectory['depths'][0]:.0f} m")
    print(f"  最大狗腿度: {trajectory['K_deg30m'].max():.2f} °/30m "
          f"@ {trajectory['depths'][np.argmax(trajectory['K_deg30m'])]:.0f} m")

    # ---- Step 2: 杆柱组合 ----
    print("\n[Step 2] 构建杆柱组合...")
    rod_diameters = fm.build_rod_diameter_array(
        trajectory['depths'], params['pump_depth'], pm.ROD_COMBO)
    unique_dias = np.unique(np.round(rod_diameters, 3))
    print(f"  杆径: {[f'{d*1000:.0f}mm' for d in unique_dias]}")

    # ---- Step 3: 受力分析 ----
    print("\n[Step 3] 三维受力分析...")
    result = fm.solve_axial_forces(
        trajectory=trajectory,
        rod_diameters=rod_diameters,
        pump_diameter_m=params['pump_diameter'],
        stroke=params['stroke'],
        stroke_rate=params['stroke_rate'],
        fluid_depth=params['fluid_level'],
        pump_efficiency=params['pump_efficiency'],
    )

    # ---- Step 4: 中和点 ----
    print("\n[Step 4] 中和点计算...")
    neutral_depth = fm.find_neutral_point(trajectory['depths'], result['P_down'])
    result['neutral_depth'] = neutral_depth
    print(f"  中和点位置: {neutral_depth:.1f} m")

    # 受压段分析
    compressed = result['P_down'] < 0
    if compressed.any():
        comp_start = trajectory['depths'][np.where(compressed)[0][0]]
        comp_end = trajectory['depths'][np.where(compressed)[0][-1]]
        print(f"  受压段范围: {comp_start:.0f} - {comp_end:.0f} m "
              f"(长度 {comp_end - comp_start:.0f} m)")
    else:
        print(f"  杆柱全受拉，无受压段")

    # 与论文验证数据对比
    print("\n  论文[1]实测数据对比：")
    for i, event in enumerate(pm.BREAK_EVENTS):
        print(f"    事件{i+1}: 杆断@{event['break_pos']}m, "
              f"中和点@{event['neutral']}m, "
              f"服役{event['service_years']}年")

    # ---- 偏磨风险分析 ----
    print("\n[Step 5] 偏磨风险评定...")

    # 高风险区1: 狗腿度峰值区
    K_threshold = trajectory['K_deg30m'].max() * 0.5
    high_K_zone = trajectory['depths'][trajectory['K_deg30m'] > K_threshold]
    if len(high_K_zone) > 0:
        print(f"  风险区1（狗腿度>50%峰值）: {high_K_zone[0]:.0f} - {high_K_zone[-1]:.0f} m")

    # 高风险区2: 中和点以下受压段
    if neutral_depth > 0:
        print(f"  风险区2（中和点以下）: {neutral_depth:.0f} - {params['pump_depth']:.0f} m")

    # 高风险区3: 支持力峰值区
    N_max = np.maximum(result['N_rt_up'], result['N_rt_down'])
    N_threshold = N_max.max() * 0.5
    high_N_zone = trajectory['depths'][N_max > N_threshold]
    if len(high_N_zone) > 0:
        print(f"  风险区3（支持力>50%峰值）: {high_N_zone[0]:.0f} - {high_N_zone[-1]:.0f} m")

    # ---- 最大应力 ----
    max_bend = result['sigma_bend'].max()
    max_bend_depth = trajectory['depths'][np.argmax(result['sigma_bend'])]
    print(f"\n  最大弯曲应力: {max_bend:.2f} MPa @ {max_bend_depth:.0f} m")

    # 应力比（用于疲劳评估）
    max_stress = np.maximum(np.abs(result['P_up']), np.abs(result['P_down']))
    # 粗略应力 = 轴向应力 + 弯曲应力
    total_stress = max_stress / pm.rod_cross_section(rod_diameters) / 1e6 + result['sigma_bend']
    print(f"  最大综合应力: {total_stress.max():.1f} MPa")

    # ---- 绘图 ----
    print("\n[Step 6] 生成图表...")
    vis.plot_well_curvature(trajectory, f'{output_dir}/curvature.png')
    vis.plot_axial_force(result, f'{output_dir}/axial_force.png')
    vis.plot_support_force(result, f'{output_dir}/support_force.png')
    vis.plot_friction_force(result, f'{output_dir}/friction_force.png')
    vis.plot_bending_stress(trajectory, result, f'{output_dir}/bending_stress.png')
    vis.plot_wear_risk(trajectory, result, f'{output_dir}/wear_risk.png')

    print(f"\n{'='*60}")
    print(f"  分析完成！图表已保存到 {output_dir}/ 目录")
    print(f"{'='*60}")

    return trajectory, result, rod_diameters


def run_sensitivity_pump_diameter():
    """泵径敏感性分析 — 参照论文[1]图3"""
    pump_dias = [0.028, 0.032, 0.038, 0.044, 0.056]  # m
    results = {}

    for dia in pump_dias:
        params = pm.SP10_9_PARAMS.copy()
        params['pump_diameter'] = dia

        trajectory = wt.create_sp10_9_trajectory(dl=5.0)
        rod_diameters = fm.build_rod_diameter_array(
            trajectory['depths'], params['pump_depth'], pm.ROD_COMBO)
        result = fm.solve_axial_forces(
            trajectory, rod_diameters,
            pump_diameter_m=dia,
            stroke=params['stroke'],
            stroke_rate=params['stroke_rate'],
            fluid_depth=params['fluid_level'],
            pump_efficiency=params['pump_efficiency'],
        )
        neutral = fm.find_neutral_point(trajectory['depths'], result['P_down'])
        result['neutral_depth'] = neutral

        key = f"{dia*1000:.0f}"
        results[key] = result
        print(f"  泵径 {dia*1000:.0f}mm: 中和点 @ {neutral:.0f}m")

    vis.plot_sensitivity_pump_diameter(results, 'output/sensitivity_pump.png')
    return results


if __name__ == '__main__':
    run_analysis()
    print("\n\n=== 泵径敏感性分析 ===")
    run_sensitivity_pump_diameter()
