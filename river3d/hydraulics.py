import math
from typing import Tuple

MANNING_N = {
    "흙_직선": 0.022,
    "흙_잡초": 0.027,
    "돌_쌓임더미": 0.025,
    "매우_부정확_잡초_나무많음": 0.100,
}

def rect_AP(d: float, b: float) -> Tuple[float, float]:
    return b*d, b + 2*d

def trap_AP(d: float, b: float, z: float) -> Tuple[float, float]:
    A = d * (b + z*d)
    sl = math.sqrt(1 + z*z)
    P = b + 2 * sl * d
    return A, P

def manning_Vmean(n: float, R: float, S: float) -> float:
    return (R ** (2/3)) * math.sqrt(S) / n

def surface_velocity(
    depth: float,
    section: str = "rect",
    b: float = 8.0,
    z: float | None = None,
    roughness: str = "흙_직선",
    S: float = 0.001,
) -> tuple[float, float, float]:
    if depth <= 0: raise ValueError("depth>0 필요")
    if S <= 0: raise ValueError("S>0 필요")
    if roughness not in MANNING_N: raise KeyError(f"unknown roughness: {roughness}")
    n = MANNING_N[roughness]
    if section == "rect":
        A, P = rect_AP(depth, b)
    elif section == "trap":
        if z is None: raise ValueError("사다리꼴은 z 필요")
        A, P = trap_AP(depth, b, z)
    else:
        raise ValueError("section must be 'rect' or 'trap'")
    R = A / P
    V_mean = manning_Vmean(n, R, S)
    V_surface = V_mean / 0.85
    Q = A * V_mean
    return V_mean, V_surface, Q
