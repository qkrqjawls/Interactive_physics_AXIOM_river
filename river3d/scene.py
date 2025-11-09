import random
from .config import RIVER_WIDTH, RIVER_LENGTH
from .entities import Obstacle, Coin, Dock

SAFE_CLEAR_M = 80.0  # 출발 후 80m는 장애물 금지

def random_positions_avoiding(avoid_boxes, margin=6.0, zmin=8.0, zmax=None):
    """
    기존 함수 확장:
    - z 범위를 지정해 안전 구간을 비워둠
    - margin으로 장애물/코인끼리 겹침 방지
    """
    if zmax is None:
        zmax = RIVER_LENGTH - 16.0
    tries = 0
    while True:
        tries += 1
        x = random.uniform(-RIVER_WIDTH*0.48, RIVER_WIDTH*0.48)
        z = random.uniform(zmin, zmax)
        ax0, az0, ax1, az1 = x-0.5, z-0.5, x+0.5, z+0.5
        ok = True
        for (x0, z0, x1, z1) in avoid_boxes:
            if not (ax1+margin < x0 or ax0-margin > x1 or az1+margin < z0 or az0-margin > z1):
                ok = False
                break
        if ok:
            return x, z
        if tries > 4000:
            # 최후의 탈출구: 강 중앙 어딘가
            return 0.0, (zmin + zmax) * 0.5

def build_scene():
    # --- 안전 구간 계산: 시작 z는 RIVER_LENGTH-6.0 이므로, 그 아래로 80m까지는 금지 ---
    start_z = RIVER_LENGTH - 6.0
    obstacle_zmax = max(8.0, start_z - SAFE_CLEAR_M)  # 장애물은 [8.0, obstacle_zmax] 범위에만 생성

    obstacles = []
    avoid = []

    # 장애물 무작위 생성 파라미터(원하면 조절)
    NUM_OBS = 6
    W_RANGE = (6.0, 12.0)   # 가로폭
    L_RANGE = (3.0, 6.0)    # 길이
    H = 1.2

    for _ in range(NUM_OBS):
        w = random.uniform(*W_RANGE)
        l = random.uniform(*L_RANGE)
        # 새 장애물의 AABB를 미리 고려해 margin을 넉넉히 주자(= w,l 기반)
        margin = max(6.0, 0.5*max(w, l) + 2.0)
        x, z = random_positions_avoiding(avoid, margin=margin, zmin=8.0, zmax=obstacle_zmax)
        ob = Obstacle(x, z, w, l, H)
        obstacles.append(ob)
        avoid.append(ob.aabb())

    # 코인: 기존처럼 랜덤 생성(장애물과 겹치지 않음)
    coins = []
    for _ in range(6):
        x, z = random_positions_avoiding(avoid, margin=6.0, zmin=8.0, zmax=RIVER_LENGTH-16.0)
        coins.append(Coin(x, z, 0.9))
        avoid.append((x-0.9, z-0.9, x+0.9, z+0.9))

    # 도크는 그대로
    dock = Dock(0.0, 3.0, 14.0, 3.0)

    return obstacles, coins, dock