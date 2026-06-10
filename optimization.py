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
    等强度杆柱组合设计。

    基于论文(4-11)-(4-16)的等强度原则：各段应力范围比 PL 尽量接近。
    用简化算法推荐实用的杆柱组合。

    返回:
        list of (直径mm, 长度m, 比例%)
    """
    D_p = pump_diameter_m * 1000.0
    L_f = fluid_depth_m

    # 杆径从小到大
    dias = sorted(rod_grades_mm)
    n = len(dias)

    if n == 1:
        return [(dias[0], L_f, 100.0)]

    # 每段分配总长的 1/n 作为初始，然后按截面积反比调整
    # 原理：细杆用在上段（应力小），粗杆用在下段（应力大）
    A_list = [pm.rod_cross_section(d / 1000.0) for d in dias]
    inv_A = [1.0 / a for a in A_list]
    total_inv = sum(inv_A)
    fractions = [ia / total_inv for ia in inv_A]

    # 最粗的杆在泵端（比例最小），最细的在井口端
    fractions = fractions[::-1]  # 反转: 粗杆短, 细杆长

    result = []
    for d, frac in zip(sorted(dias), fractions):
        L = L_f * frac
        result.append((d, round(L, 1), round(frac * 100, 1)))

    return result
