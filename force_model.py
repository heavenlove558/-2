"""
模块2+3：抽油杆三维受力分析与支持力/摩擦力计算

实现内容：
  - 各力分量计算（重力、浮力、惯性力、摩擦力、液体阻力）
  - 上下冲程分段迭代轴向力
  - 双平面（狗腿平面 + 垂直平面）支持力分解
  - 杆管摩擦力、杆液摩擦力
  - 弯曲应力计算
"""
import numpy as np
import parameters as pm


# ============================================================
# 各力分量计算
# ============================================================

def calc_rod_weight(diameter_m, dl):
    """杆柱自重，N"""
    A = pm.rod_cross_section(diameter_m)
    return pm.RHO_R * A * pm.G * dl


def calc_rod_buoyancy(diameter_m, dl):
    """杆柱浮力，N"""
    A = pm.rod_cross_section(diameter_m)
    return pm.RHO_L * A * pm.G * dl


def calc_rod_net_weight(diameter_m, dl):
    """杆柱浮重 = 自重 - 浮力，N"""
    return calc_rod_weight(diameter_m, dl) - calc_rod_buoyancy(diameter_m, dl)


def calc_rod_inertia(diameter_m, dl, stroke, stroke_rate):
    """杆柱惯性力，N（简谐运动近似）"""
    A = pm.rod_cross_section(diameter_m)
    omega = 2.0 * np.pi * stroke_rate / 60.0  # rad/s
    a_max = omega**2 * stroke / 2.0            # 最大加速度，m/s²
    return pm.RHO_R * A * dl * a_max


def calc_liquid_load(pump_diameter_m, rod_diameter_m, fluid_depth):
    """液柱载荷（作用在柱塞上），N"""
    F_p = pm.pump_plunger_area(pump_diameter_m)
    A_r = pm.rod_cross_section(rod_diameter_m)
    return (F_p - A_r) * pm.RHO_L * pm.G * fluid_depth


def calc_liquid_inertia(pump_diameter_m, rod_diameter_m, fluid_depth,
                         stroke, stroke_rate):
    """液柱惯性力，N"""
    F_p = pm.pump_plunger_area(pump_diameter_m)
    A_r = pm.rod_cross_section(rod_diameter_m)
    F_t = pm.tubing_inner_area()

    omega = 2.0 * np.pi * stroke_rate / 60.0
    a_max = omega**2 * stroke / 2.0

    # 过流面积扩大系数
    eps = (F_t - A_r) / (F_t - F_p) if (F_t - F_p) > 1e-12 else 1.0

    return (F_p - A_r) * pm.RHO_L * a_max * eps * fluid_depth


def calc_plunger_friction(pump_diameter_mm):
    """柱塞与泵筒摩擦力（经验公式），N"""
    return 0.94 * pump_diameter_mm / (pm.DELTA * 1000.0) - 140.0


def calc_valve_resistance(pump_diameter_m, stroke, stroke_rate):
    """液体通过游动阀的阻力，N

    简化模型（论文[1]）：F_v = (1/729) * ρ_l * f_p^3 * (s*n)^2 / (ε^2 * f_o)
    """
    f_p = pm.pump_plunger_area(pump_diameter_m)
    s = stroke
    n = stroke_rate
    eps = 0.43  # 泵效（默认值）
    # 游动阀孔面积按泵径的15%估算
    f_o = f_p * 0.15

    if f_o < 1e-12:
        return 0.0
    return (1.0 / 729.0) * pm.RHO_L * (f_p**3) * (s * n)**2 / (eps**2 * f_o)


def calc_rod_fluid_friction(diameter_m, dl, viscosity, velocity):
    """杆液摩擦力，N

    公式：F_rl = 2π·μ·ΔL·v / [(m²+1)·ln(m) - (m²-1)]
    """
    m = pm.D_TUBE / diameter_m  # 油管内径与杆径之比
    if m <= 1.0:
        return 0.0
    denominator = (m**2 + 1.0) * np.log(m) - (m**2 - 1.0)
    if abs(denominator) < 1e-12:
        return 0.0
    return 2.0 * np.pi * viscosity * dl * abs(velocity) / denominator


def calc_rod_velocity(stroke, stroke_rate):
    """杆柱最大运动速度，m/s（简谐运动近似）"""
    omega = 2.0 * np.pi * stroke_rate / 60.0
    return omega * stroke / 2.0


def calc_bending_stress(diameter_m, curvature_radius):
    """井眼轨迹引起的弯曲应力，MPa

    σ_w = d_r * E / (2 * R)
    """
    if np.isinf(curvature_radius) or curvature_radius < 1e-12:
        return 0.0
    stress_pa = diameter_m * pm.E_STEEL / (2.0 * curvature_radius)
    return stress_pa / 1e6  # 转换为 MPa


# ============================================================
# 支持力计算（双平面分解）
# ============================================================

def calc_dogleg_angle(alpha1, phi1, alpha2, phi2):
    """计算狗腿角 β，rad"""
    cos_beta = (np.cos(alpha1) * np.cos(alpha2) +
                np.sin(alpha1) * np.sin(alpha2) * np.cos(phi2 - phi1))
    cos_beta = np.clip(cos_beta, -1.0, 1.0)
    return np.arccos(cos_beta)


def calc_support_force(P_i, P_next, F_net_weight, alpha1, phi1, alpha2, phi2):
    """计算油管对杆柱的支持力 N_rt，N

    双平面分解：
    - 狗腿平面内 N1（轴向力+重力引起）
    - 垂直狗腿平面 N2（仅重力引起）
    - 总支持力 N_rt = sqrt(N1² + N2²)

    返回
    ----
    N_rt, N1, N2, beta
    """
    beta = calc_dogleg_angle(alpha1, phi1, alpha2, phi2)

    if beta < 1e-12:
        # 直井段，支持力为0
        return 0.0, 0.0, 0.0, beta

    sin_half_beta = np.sin(beta / 2.0)
    avg_alpha = (alpha1 + alpha2) / 2.0
    dalpha = alpha1 - alpha2

    # 狗腿平面内支持力 N1
    # cos(γ_n) = sin(avg_α) * sin(Δα/2) / sin(β/2)
    cos_gamma_n = np.sin(avg_alpha) * np.sin(abs(dalpha) / 2.0) / sin_half_beta
    cos_gamma_n = np.clip(cos_gamma_n, -1.0, 1.0)

    N1 = (P_i + P_next) * sin_half_beta + F_net_weight * cos_gamma_n

    # 垂直狗腿平面的支持力 N2
    sin_beta = np.sin(beta)
    if sin_beta < 1e-12:
        N2 = 0.0
    else:
        N2 = (F_net_weight * np.sin(alpha1) * np.sin(alpha2) *
              abs(np.sin(phi2 - phi1)) / sin_beta)

    N_rt = np.sqrt(N1**2 + N2**2)
    return N_rt, N1, N2, beta


# ============================================================
# 轴向力分段迭代
# ============================================================

def solve_axial_forces(trajectory, rod_diameters, pump_diameter_m,
                       stroke, stroke_rate, fluid_depth,
                       pump_efficiency=0.43):
    """
    分段迭代计算上下冲程轴向力分布。

    策略（两遍扫描）：
      第一遍：不计杆管摩擦，仅用轴向力分量的粗略估计
      第二遍：基于第一遍轴向力计算支持力/摩擦力，重新迭代

    这是论文[1][2]使用的标准方法——先用简化力平衡估算轴向力，
    再代入求支持力和摩擦力。
    """
    depths = trajectory['depths']
    alpha = trajectory['alpha_rad']
    phi = trajectory['phi_rad']
    R_curv = trajectory['R_curvature']
    n_seg = len(depths)

    dl = depths[1] - depths[0] if n_seg > 1 else 5.0
    pump_diameter_mm = pump_diameter_m * 1000.0

    # ---- 边界条件 ----
    F_cp = calc_plunger_friction(pump_diameter_mm)
    liquid_load = calc_liquid_load(
        pump_diameter_m, rod_diameters[-1], fluid_depth)
    liquid_inertia = calc_liquid_inertia(
        pump_diameter_m, rod_diameters[-1], fluid_depth, stroke, stroke_rate)
    F_v = calc_valve_resistance(pump_diameter_m, stroke, stroke_rate)
    v_rod = calc_rod_velocity(stroke, stroke_rate)

    P_0_up = F_cp + liquid_load  # 上冲程底端（忽略液体惯性，量级小）
    P_0_down = -(F_cp + F_v)     # 下冲程底端

    # ====== 第一遍：不计杆管摩擦，粗略迭代 ======
    P_up_0 = np.zeros(n_seg)
    P_down_0 = np.zeros(n_seg)
    P_up_0[-1] = P_0_up
    P_down_0[-1] = P_0_down

    for i in range(n_seg - 2, -1, -1):
        di = rod_diameters[i]
        avg_cos = np.cos((alpha[i] + alpha[i+1]) / 2.0)

        F_r = calc_rod_weight(di, dl)
        F_b = calc_rod_buoyancy(di, dl)
        F_inertia = calc_rod_inertia(di, dl, stroke, stroke_rate)
        F_rl = calc_rod_fluid_friction(di, dl, pm.MU_OIL, v_rod)

        # 上冲程（只计重力、惯性力、杆液摩擦、柱塞摩擦）
        P_up_0[i] = (P_up_0[i+1]
                     + F_r * avg_cos
                     + F_inertia
                     + F_rl
                     + F_cp / n_seg)

        # 下冲程
        P_down_0[i] = (P_down_0[i+1]
                       + (F_r - F_b) * avg_cos   # 浮重轴向分量
                       - F_inertia
                       - F_rl
                       - F_cp / n_seg
                       - F_v / n_seg)

    # ====== 第二遍：基于粗略轴向力计算支持力/摩擦，精确迭代 ======
    P_up = np.zeros(n_seg)
    P_down = np.zeros(n_seg)
    N_rt_up = np.zeros(n_seg)
    N_rt_down = np.zeros(n_seg)
    F_fric_up = np.zeros(n_seg)
    F_fric_down = np.zeros(n_seg)
    sigma_bend = np.zeros(n_seg)

    P_up[-1] = P_0_up
    P_down[-1] = P_0_down

    for i in range(n_seg - 2, -1, -1):
        di = rod_diameters[i]
        avg_cos = np.cos((alpha[i] + alpha[i+1]) / 2.0)

        F_r = calc_rod_weight(di, dl)
        F_b = calc_rod_buoyancy(di, dl)
        F_net = F_r - F_b
        F_inertia = calc_rod_inertia(di, dl, stroke, stroke_rate)
        F_rl = calc_rod_fluid_friction(di, dl, pm.MU_OIL, v_rod)
        sigma_bend[i] = calc_bending_stress(di, R_curv[i])

        # 用第一遍的轴向力估算支持力
        N_up, _, _, _ = calc_support_force(
            P_up_0[i], P_up_0[i+1], F_net,
            alpha[i], phi[i], alpha[i+1], phi[i+1])
        N_down, _, _, _ = calc_support_force(
            P_down_0[i], P_down_0[i+1], F_net,
            alpha[i], phi[i], alpha[i+1], phi[i+1])

        F_rt_up = pm.F_FRICTION * abs(N_up)
        F_rt_down = pm.F_FRICTION * abs(N_down)

        # 上冲程（全部受力）
        P_up[i] = (P_up[i+1]
                   + F_r * avg_cos
                   + F_inertia
                   + F_rt_up
                   + F_rl
                   + F_cp / n_seg)

        # 下冲程（全部受力）
        P_down[i] = (P_down[i+1]
                     + (F_r - F_b) * avg_cos    # 浮重轴向分量
                     - F_inertia
                     - F_rt_down
                     - F_rl
                     - F_cp / n_seg
                     - F_v / n_seg)

        N_rt_up[i] = N_up
        N_rt_down[i] = N_down
        F_fric_up[i] = F_rt_up
        F_fric_down[i] = F_rt_down

    sigma_bend[-1] = calc_bending_stress(rod_diameters[-1], R_curv[-1])

    return {
        'depths': depths,
        'P_up': P_up,
        'P_down': P_down,
        'N_rt_up': N_rt_up,
        'N_rt_down': N_rt_down,
        'F_fric_up': F_fric_up,
        'F_fric_down': F_fric_down,
        'sigma_bend': sigma_bend,
    }


def find_neutral_point(depths, P_down):
    """
    找到中和点位置。

    中和点定义：下冲程中轴向力从受拉(P>0)变为受压(P<0)的位置。
    depths[0]=井口(浅), depths[-1]=泵挂(深)。
    井口→深部: P从正(拉)变为负(压)。
    """
    for i in range(len(P_down) - 1):
        # depths[i] 较浅, depths[i+1] 较深
        # 正常情况: P_down[i] >= 0 (受拉), P_down[i+1] < 0 (受压)
        if P_down[i] >= 0 and P_down[i+1] < 0:
            # 线性插值求零点
            if abs(P_down[i+1] - P_down[i]) > 1e-12:
                t = -P_down[i] / (P_down[i+1] - P_down[i])
                return depths[i] + t * (depths[i+1] - depths[i])

    # 全部受拉 → 中和点在井口以上
    if np.all(P_down >= 0):
        return 0.0
    # 全部受压 → 中和点在泵挂处
    return depths[-1]


def build_rod_diameter_array(depths, pump_depth, rod_combo):
    """
    根据杆柱组合构建每节点的杆径数组。

    参数
    ----
    rod_combo : list of (diameter_m, fraction)
        从下到上的杆柱组合，如 [(0.022, 0.15), (0.019, 0.50), (0.022, 0.35)]
    """
    n_seg = len(depths)
    rod_diameters = np.zeros(n_seg)

    cumulative = 0.0
    for idx, (dia, frac) in enumerate(rod_combo):
        cumulative += frac
        depth_top = pump_depth * cumulative
        depth_bottom = pump_depth * (cumulative - frac)
        mask = (depths >= depth_bottom) & (depths < depth_top)
        rod_diameters[mask] = dia

    # 边界处理
    rod_diameters[depths >= pump_depth * (1.0 - rod_combo[-1][0] * 0.01)] = rod_combo[-1][0]

    # 填补可能的零值（用最大杆径）
    rod_diameters[rod_diameters < 1e-6] = max(d[0] for d in rod_combo)

    return rod_diameters
