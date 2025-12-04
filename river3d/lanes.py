import random
from dataclasses import dataclass
from .config import LANE_COUNT, RIVER_LENGTH, DEFAULT_SLOPE
from .hydraulics import surface_velocity

# Default profiles
LANE_PROFILES = [
    {"depth":1.0,"section":"rect","b":8.0,"z":None,"roughness":"매우_부정확_잡초_나무많음","dir":-1},  # 1번 레인 (수정)
    {"depth":2.0,"section":"rect","b":8.0,"z":None,"roughness":"흙_직선","dir":+1},   # 2번 레인
    {"depth":1.6,"section":"rect","b":8.0,"z":None,"roughness":"흙_잡초","dir":-1},   # 3번 레인
    {"depth":1.4,"section":"trap","b":7.0,"z":1.5,"roughness":"돌_쌓임더미","dir":+1},  # 4번 레인
    {"depth":1.2,"section":"rect","b":8.0,"z":None,"roughness":"흙_직선","dir":-1},  # 5번 레인 (수정)
]

MIN_DEPTH, MAX_DEPTH = 0.9, 2.2

# per-lane flow scaling (user tuning)
FLOW_SCALE: list[float] = [1.0]*LANE_COUNT

@dataclass
class Lane:
    z0: float
    z1: float
    vx: float
    depth: float

def _lane_flow(p, S=DEFAULT_SLOPE):
    Vm, Vs, _ = surface_velocity(p["depth"], p["section"], p["b"], p["z"], p["roughness"], S)
    return p["dir"] * Vs, Vm, Vs

def build_lanes_from_manning():
    lanes = []  # 레인 목록 초기화
    info = []   # 레인 정보 초기화
    dz = RIVER_LENGTH / LANE_COUNT  # 각 레인의 높이 간격

    # LANES 배열을 1부터 5까지 순서대로 설정
    for i in range(LANE_COUNT):
        # LANE_PROFILES의 레인 순서를 1부터 5까지 맞추기
        p = LANE_PROFILES[i]
        
        # 레인 정보 계산
        vx, Vm, Vs = _lane_flow(p)
        
        # 각 레인의 구간 설정
        lanes.append(Lane(i * dz, (i + 1) * dz, vx, p["depth"]))
        info.append({"Vs_ms": Vs})
    
    return lanes, info


LANES, LANE_INFO = build_lanes_from_manning()

def randomize_lane_depths(seed=None, min_d=MIN_DEPTH, max_d=MAX_DEPTH, bias_center=True):
    if seed is not None:
        random.seed(seed)
    depths = [random.uniform(min_d, max_d) for _ in range(LANE_COUNT)]
    if bias_center:
        weights = [0.88, 0.96, 1.10, 0.96, 0.88]
        depths = [max(min_d, min(max_d, d*w)) for d,w in zip(depths,weights)]
    sm = depths[:]
    for i in range(1, LANE_COUNT-1):
        sm[i] = 0.2*depths[i-1] + 0.6*depths[i] + 0.2*depths[i+1]
    for p, d in zip(LANE_PROFILES, [max(min_d, min(max_d, s)) for s in sm]):
        p["depth"] = d

def get_lane_index(zpos: float):
    """
    배의 z(하류 위치)에 맞는 레인 번호를 반환
    레인 번호가 1부터 시작하도록 수정
    """
    for i, ln in enumerate(LANES):
        if ln.z0 <= zpos < ln.z1:
            return i + 1  # 레인 번호는 1부터 시작하도록 설정
    return None  # 해당하는 레인이 없으면 None 반환



def river_flow_vx(zpos: float) -> float:
    for i, ln in enumerate(LANES):
        if ln.z0 <= zpos < ln.z1:
            return ln.vx * FLOW_SCALE[i]
    return 0.0
