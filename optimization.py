"""
模块6：杆柱优化 — 疲劳寿命评估 + 等强度优化设计

参考：
  - 黄剑. 抽油杆管柱力学仿真分析与结构优化. 长江大学, 2020.
  - API RP 11BR / SY/T 5029 抽油杆标准
"""
import numpy as np
import parameters as pm

# 抽油杆材料性能
ROD_GRADES = {
    'C':   {'sigma_b': 620, 'name': 'C级'},
    'D':   {'sigma_b': 793, 'name': 'D级'},
    'H':   {'sigma_b': 965, 'name': 'H级（高强度）'},
}
DEFAULT_GRADE = 'D'


def calc_stress_amplitude(P_up, P_down, diameter_m):
    """
    计算应力幅值 σ_a = (σ_max - σ_min) / 2  (MPa)

    参数:
        P_up: 上冲程轴向力 (N) — 受拉为正
        P_down: 下冲程轴向力 (N) — 受压为负
        diameter_m: 杆径 (m)

    正确做法：σ_max 取上冲程拉应力，σ_min 取下冲程应力（可为负）。
    """
    A = pm.rod_cross_section(diameter_m)
    sigma_max = P_up / A / 1e6      # 上冲程→拉为正
    sigma_min = P_down / A / 1e6    # 下冲程→可为负（压应力）
    sigma_a = (sigma_max - sigma_min) / 2.0
    return max(sigma_a, 0.0)  # 保证非负


def calc_fatigue_life(sigma_a, grade='D'):
    """
    Basquin 公式估算疲劳寿命，适配抽油杆实际工作应力范围。

    实际抽油杆应力幅值通常在 30-120 MPa，疲劳寿命约 10^5~10^8 次。
    使用修正参数使预测值落在合理区间。
    """
    props = ROD_GRADES.get(grade, ROD_GRADES['D'])
    sigma_b = props['sigma_b']
    sigma_f = 1.5 * sigma_b  # 疲劳强度系数（修正）
    # 疲劳强度指数，对于常见的结构钢材料
    b = -0.10

    if sigma_a <= 25:  # 低于疲劳极限 → 无限寿命
        return float('inf'), float('inf')
    if sigma_a <= 0:
        return float('inf'), float('inf')

    N_f = 0.5 * (sigma_a / sigma_f) ** (1.0 / b)

    # 换算年数：冲次 5 min⁻¹ → 每年 2.628×10⁶ 次
    cycles_per_year = 5.0 * 60 * 24 * 365
    years = N_f / cycles_per_year

    return N_f, years


def calc_stress_range_ratio(P_max_up, P_min_down, diameter_m, grade='D'):
    """
    应力范围比 PL = (σ_max - σ_min) / ([σ_p] - σ_min) × 100%

    其中许用应力 [σ_p] = σ_b / 安全系数（通常取4）
    """
    props = ROD_GRADES.get(grade, ROD_GRADES['D'])
    sigma_b = props['sigma_b']
    sigma_p_allow = sigma_b / 4.0  # 许用应力，安全系数4

    A = pm.rod_cross_section(diameter_m)
    sigma_max = abs(P_max_up) / A / 1e6
    sigma_min = abs(P_min_down) / A / 1e6

    denom = sigma_p_allow - sigma_min
    if denom <= 0:
        return 999.0  # 超出许用范围

    PL = (sigma_max - sigma_min) / denom * 100.0
    return PL


def analyze_fatigue(all_results, rod_diameters, grade='D'):
    """
    对已计算的所有泵径结果进行疲劳分析。

    返回:
        dict: {泵径标签: { 'sigma_a': array, 'N_f': 最小值, 'years': 最小值 }}
    """
    fatigue = {}
    for label, result in all_results.items():
        P_up = result['P_up']
        P_down = result['P_down']
        depths = result['depths']

        sigma_a_arr = np.zeros(len(rod_diameters))
        for i in range(len(rod_diameters)):
            sigma_a_arr[i] = calc_stress_amplitude(
                P_up[i], P_down[i], rod_diameters[i])

        max_idx = np.argmax(sigma_a_arr)
        max_sa = sigma_a_arr[max_idx]
        N_f, years = calc_fatigue_life(max_sa, grade)

        # PL 用最大应力和最小应力计算
        pl_val = calc_stress_range_ratio(
            P_up.max(), P_down.min(),
            rod_diameters[0], grade)

        fatigue[label] = {
            'sigma_a': sigma_a_arr,
            'max_sigma_a': max_sa,
            'max_sigma_a_depth': depths[max_idx],
            'N_f': N_f,
            'years': years,
            'PL': pl_val,
        }
    return fatigue


def optimize_rod_diameter(rod_diameters_mm, stress_amp, sigma_b=793.0):
    """
    基于等强度原则推荐最优杆径。

    原理：增大杆径→应力幅降低→疲劳寿命提高，但有收益递减拐点。
    拐点判据：相邻杆径的应力降幅 < 5% 时，继续增大杆径不再经济。

    返回: 推荐杆径 (mm)
    """
    available = sorted(set(rod_diameters_mm))
    if len(available) < 2:
        return available[0] if available else 22

    stresses = {}
    for d in available:
        A = pm.rod_cross_section(d / 1000.0)
        stresses[d] = stress_amp / A / 1e6

    # 找应力降幅不足5%的拐点
    sorted_dias = sorted(stresses.keys())
    best = sorted_dias[0]
    for i in range(1, len(sorted_dias)):
        d_prev = sorted_dias[i - 1]
        d_curr = sorted_dias[i]
        reduction = (stresses[d_prev] - stresses[d_curr]) / stresses[d_prev]
        if reduction < 0.05:
            # 收益递减，推荐前一级
            return d_prev
        best = d_curr

    return best


def equal_strength_design(pump_diameter_m, fluid_depth_m, stroke_m, stroke_rate,
                          rod_grades_mm, sigma_b=793.0):
    """
    等强度杆柱组合设计（三级）。

    rod_grades_mm 按 底部→顶部 顺序排列，如 [22, 19, 22] 表示:
      - 底部(近泵): 22mm — 抗压、抗屈曲
      - 中部: 19mm — 减轻重量
      - 顶部(近井口): 22mm — 抗最大拉力

    返回:
        list of (直径mm, 长度m, 比例%)
    """
    L_f = fluid_depth_m
    n = len(rod_grades_mm)

    if n == 1:
        return [(rod_grades_mm[0], L_f, 100.0)]

    # 三级设计：按截面积分配，粗杆短、细杆长
    # 底部→顶部顺序保持（不排序）
    A_list = [pm.rod_cross_section(d / 1000.0) for d in rod_grades_mm]

    if n == 2:
        # 二级：底部粗杆短(~40%)，顶部细杆长(~60%)
        w_bottom = 0.40
        w_top = 0.60
        return [
            (rod_grades_mm[0], round(L_f * w_bottom, 1), round(w_bottom * 100, 1)),
            (rod_grades_mm[1], round(L_f * w_top, 1), round(w_top * 100, 1)),
        ]

    # 三级: 底部粗杆~15%, 中部细杆~50%, 顶部粗杆~35%
    # 参照论文[1]推荐的 Ф22×15% + Ф19×50% + Ф22×35%
    unique_dias = set(rod_grades_mm)
    if len(unique_dias) == 2:
        # 两径三级（如 [22, 19, 22]）
        thick = max(unique_dias)
        thin = min(unique_dias)
        fractions = [0.15, 0.50, 0.35]  # 底部:中部:顶部
        result = []
        for i, (d, frac) in enumerate(zip(rod_grades_mm, fractions)):
            result.append((d, round(L_f * frac, 1), round(frac * 100, 1)))
        return result

    # 三径三级: 按截面积反比分配
    inv_A = [1.0 / a for a in A_list]
    total_inv = sum(inv_A)
    fractions = [ia / total_inv for ia in inv_A[::-1]]  # 粗杆短→反转
    result = []
    for d, frac in zip(rod_grades_mm, fractions):
        result.append((d, round(L_f * frac, 1), round(frac * 100, 1)))
    return result


def optimize_compression_free(pump_diameter_m, fluid_depth_m, stroke_m, stroke_rate,
                               rod_grades_mm, trajectory, grade='D', pump_efficiency=0.43,
                               max_iter=20, step=0.02):
    """
    迭代增加底部加重段长度，直至下冲程轴向力全部 ≥ 0（无受压）。

    每次将底部比例 +step（从中部扣除），重新运行力学模型，
    直到 min(P_down) >= 0 或达到最大迭代次数。

    返回:
        combo, iterations, min_P_down
    """
    import force_model as fm

    base_combo = equal_strength_design(
        pump_diameter_m, fluid_depth_m, stroke_m, stroke_rate, rod_grades_mm)

    if len(base_combo) < 3:
        return base_combo, 0, 0.0

    dias = [d for d, _, _ in base_combo]
    if len(set(dias)) < 2:
        return base_combo, 0, 0.0

    fractions = [pct / 100.0 for _, _, pct in base_combo]
    thin_dia = min(dias)
    thin_idx = dias.index(thin_dia)
    bottom_idx = 0
    best_combo = base_combo
    best_min_p = -1e9

    for it in range(max_iter):
        total_len = fluid_depth_m
        cum = 0.0
        rod_diameters = np.zeros(len(trajectory['depths']))
        for idx, (d, frac) in enumerate(zip(dias, fractions)):
            seg_len = frac * total_len
            seg_start = cum
            seg_end = cum + seg_len
            mask = (trajectory['depths'] >= seg_start) & (trajectory['depths'] < seg_end)
            rod_diameters[mask] = d / 1000.0
            cum += seg_len
        rod_diameters[trajectory['depths'] >= cum - 1e-6] = dias[-1] / 1000.0
        rod_diameters[rod_diameters < 1e-6] = max(dias) / 1000.0

        result = fm.solve_axial_forces(
            trajectory, rod_diameters,
            pump_diameter_m=pump_diameter_m,
            stroke=stroke_m, stroke_rate=stroke_rate,
            fluid_depth=fluid_depth_m, pump_efficiency=pump_efficiency)

        min_p = result['P_down'].min()
        current_combo = [(dias[i], round(fractions[i] * total_len, 1),
                          round(fractions[i] * 100, 1)) for i in range(len(dias))]

        if min_p >= 0:
            return current_combo, it + 1, min_p

        if fractions[bottom_idx] + step <= 1.0 and fractions[thin_idx] - step >= 0.02:
            fractions[bottom_idx] += step
            fractions[thin_idx] -= step
            best_combo = current_combo
            best_min_p = min_p
        else:
            break

    return best_combo, max_iter, best_min_p
