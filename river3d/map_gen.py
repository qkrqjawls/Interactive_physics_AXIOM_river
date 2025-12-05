import math
import random
from .config import (
    RIVER_WIDTH, RIVER_LENGTH, 
    STAGE2_CURVE_AMP, STAGE2_CURVE_FREQ,
    ISLAND_WIDTH, ISLAND_LENGTH, TREE_COUNT,
    STAGE3_CURVE_AMP, STAGE3_CURVE_FREQ, MONSTER_COUNT
)

def get_river_center(z: float, stage: int) -> float:
    """
    주어진 z 위치에서 강의 중심 x 좌표를 반환.
    Stage 1: 직선 (0.0)
    Stage 2: 곡선 (Sine wave)
    Stage 3: 더 심한 곡선 (Sine wave + Noise?)
    """
    if stage < 2:
        return 0.0
    
    amp = STAGE2_CURVE_AMP if stage == 2 else STAGE3_CURVE_AMP
    freq = STAGE2_CURVE_FREQ if stage == 2 else STAGE3_CURVE_FREQ
    
    # Stage 3는 약간의 불규칙성을 더할 수 있음 (여기선 단순 진폭/빈도 증가)
    return math.sin(z * freq) * amp

def get_river_width(z: float, stage: int) -> float:
    """강의 폭 반환 (현재는 일정)"""
    return RIVER_WIDTH

def get_island_bounds(z: float, stage: int):
    """
    해당 z 위치에 섬이 있으면 (x_min, x_max) 반환, 없으면 None
    Stage 3에는 섬이 없을 수도 있고, 더 많을 수도 있음. (일단 Stage 2만)
    """
    if stage != 2: # Stage 3는 섬 대신 몬스터
        return None
    
    # 강 중간 지점에 섬 배치
    island_z_center = RIVER_LENGTH * 0.5
    
    # 섬의 범위 안에 있는지 확인
    if abs(z - island_z_center) < ISLAND_LENGTH / 2:
        center_x = get_river_center(z, stage)
        # 섬은 강 중심에 위치
        return (center_x - ISLAND_WIDTH / 2, center_x + ISLAND_WIDTH / 2)
    
    return None

def generate_trees(stage: int):
    """
    강둑에 배치할 나무 위치 생성 (x, y, z) 리스트 반환
    Stage 3는 나무 대신 돌이나 다른 장식일 수 있음 (일단 나무 유지 or 제거)
    """
    trees = []
    if stage != 2: # Stage 3는 나무 없음 (용암지대)
        return trees
    
    for _ in range(TREE_COUNT):
        z = random.uniform(0, RIVER_LENGTH)
        
        # 왼쪽(-1) 또는 오른쪽(1) 둑
        side = random.choice([-1, 1])
        
        center_x = get_river_center(z, stage)
        river_w = get_river_width(z, stage)
        
        # 강둑에서 약간 떨어진 곳에 배치
        dist_from_edge = random.uniform(1.0, 15.0)
        x = center_x + side * (river_w / 2 + dist_from_edge)
        
        # y는 지면 높이
        y = random.uniform(0.0, 0.5)
        
        trees.append((x, y, z))
        
    return trees

def generate_monsters(stage: int):
    """
    Stage 3 몬스터 위치 생성 (x, y, z, speed_factor)
    """
    monsters = []
    if stage != 3:
        return monsters
        
    for _ in range(MONSTER_COUNT):
        z = random.uniform(50, RIVER_LENGTH - 50) # 시작과 끝 제외
        center_x = get_river_center(z, stage)
        river_w = get_river_width(z, stage)
        
        # 강폭 내 랜덤 위치
        x = center_x + random.uniform(-river_w/2 + 2, river_w/2 - 2)
        y = 0.0 # 물 표면
        
        # 속도 계수 (1.0 = 기본)
        speed_factor = random.uniform(0.8, 1.2)
        
        monsters.append({"pos": [x, y, z], "speed": speed_factor, "anim_offset": random.random() * 10})
        
    return monsters
