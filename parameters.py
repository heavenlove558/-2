"""
抽油杆三维力学模型 — 物理常数与参数定义
"""

import numpy as np

# ============================================================
# 物理常数
# ============================================================
G = 9.81            # 重力加速度，m/s²
E_STEEL = 2.10e11   # 钢弹性模量，Pa（210 GPa）
RHO_R = 7850.0      # 抽油杆密度，kg/m³
# 流体单项物性
RHO_OIL = 850.0      # 原油密度，kg/m³
RHO_WATER = 1000.0   # 水密度，kg/m³
MU_OIL = 0.050       # 原油动力粘度，Pa·s（典型值）
MU_WATER = 0.001     # 水动力粘度，Pa·s
F_FRICTION = 0.15    # 杆管摩擦系数
DELTA = 0.053e-3     # 柱塞配合间隙，m（0.053 mm）
D_TUBE = 0.062       # 油管内径，m（62 mm）
TAIL_PIPE_LENGTH = 30.0  # 尾管长度，m（泵以下）

# ============================================================
# SP10-9 井生产参数（论文[1]基准案例）
# ============================================================
SP10_9_PARAMS = {
    'stroke': 3.0,           # 冲程，m
    'stroke_rate': 5.0,      # 冲次，min⁻¹
    'pump_diameter': 0.044,  # 泵径，m（44 mm）
    'pump_depth': 1631.0,    # 泵挂深度，m
    'fluid_level': 1465.0,   # 动液面深度，m
    'water_cut': 0.317,      # 含水率
    'pump_efficiency': 0.43, # 泵效
}

# 杆柱组合（从下到上）: (直径mm, 长度比例)
ROD_COMBO = [
    (0.022, 0.15),  # Φ22mm × 15%
    (0.019, 0.50),  # Φ19mm × 50%
    (0.022, 0.35),  # Φ22mm × 35%
]

# ============================================================
# SP10-9 井已知故障数据（论文[1]表1）
# ============================================================
BREAK_EVENTS = [
    {'date': '2020/7/18', 'liquid': 17.02, 'stroke': 3.0, 'rate': 4.8,
     'pump_dia': 56, 'efficiency': 33.34, 'pump_depth': 1498, 'fluid': 1285,
     'cycle_days': 352, 'break_pos': 977, 'neutral': 968, 'service_years': 0.96},
    {'date': '2021/3/15', 'liquid': 13.96, 'stroke': 2.9, 'rate': 5.1,
     'pump_dia': 44, 'efficiency': 43.13, 'pump_depth': 1648, 'fluid': 1452,
     'cycle_days': 239, 'break_pos': 1088, 'neutral': 1116, 'service_years': 1.62},
    {'date': '2021/6/17', 'liquid': 14.37, 'stroke': 2.9, 'rate': 5.9,
     'pump_dia': 44, 'efficiency': 38.38, 'pump_depth': 1631, 'fluid': 1465,
     'cycle_days': 92, 'break_pos': 1152, 'neutral': 1119, 'service_years': 1.30},
]


def rod_cross_section(diameter_m):
    """抽油杆截面积，m²"""
    return np.pi * diameter_m**2 / 4.0


def tubing_inner_area():
    """油管内圆面积，m²"""
    return np.pi * D_TUBE**2 / 4.0


def pump_plunger_area(diameter_m):
    """柱塞截面积，m²"""
    return np.pi * diameter_m**2 / 4.0


def deg_to_rad(deg):
    return np.array(deg) * np.pi / 180.0


def rad_to_deg(rad):
    return np.array(rad) * 180.0 / np.pi


def fluid_properties(water_cut):
    """
    根据含水率计算混合液密度和粘度。

    密度: ρ_mix = f_w × ρ_water + (1-f_w) × ρ_oil  (线性混合)
    粘度: 含水>50%时水为连续相(μ≈μ_water)，含水<50%时油为连续相(μ≈μ_oil)
          使用线性插值过渡避免不连续跳变。

    返回: (rho_mix kg/m³, mu_mix Pa·s)
    """
    fw = max(0.0, min(1.0, water_cut))
    rho_mix = fw * RHO_WATER + (1.0 - fw) * RHO_OIL
    # 粘度对数插值（油水混合粘度常用方法）
    import numpy as np
    mu_mix = np.exp(fw * np.log(MU_WATER) + (1.0 - fw) * np.log(MU_OIL))
    return rho_mix, mu_mix
