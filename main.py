# main.py

import sys, math, os, pygame
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import *

from river3d.config import (
    WIDTH, HEIGHT, FPS, SHOW_MINIMAP, SHOW_PREDICT, USE_MOUSE_STEER,
    ENGINE_THRUST, BRAKE_THRUST, TURN_RATE_DEG, RIVER_WIDTH, RIVER_LENGTH,
    SECONDS_LIMIT, COIN_TIME_BONUS, PREDICT_STEPS, PREDICT_DT,
    BOAT_LEN, BOAT_WID, BOAT_HGT,
)
from river3d import config as cfg

from river3d.entities import Boat, boat_aabb, Obstacle, Coin, Dock
from river3d.lanes import (
    LANES, LANE_INFO, FLOW_SCALE, build_lanes_from_manning, randomize_lane_depths,
    get_lane_index, river_flow_vx, MIN_DEPTH, MAX_DEPTH
)
from river3d.physics import aabb_overlap, bounce_response
from river3d.glutils import (
    init_gl, begin_ortho, end_ortho, GLText, draw_box, draw_cylinder,
    load_texture_rgba, draw_textured_coin, depth_to_color
)
from river3d.scene import build_scene
from river3d.hud import (
    draw_minimap, draw_compass, draw_throttle_gauge, draw_top_timer, draw_help_strip,
    draw_lane_tune_prompt, draw_toast, draw_next_stage_tuner
)

# --- runtime state ---
PAUSED = False
TOAST_TIMER = 0.0
TOAST_TEXT = ""
lane_tune_timer = 0.0
current_lane_idx = None

# --- next-stage tuner state ---
NEXT_STAGE_MODE = False          # 튜너 패널 표시 여부
NEXT_SCALES = [1.0]*5            # 다음 스테이지에 적용할 레인별 배율
NEXT_ACTIVE = None               # 키로 선택한 레인 인덱스(하이라이트)

def show_toast(text, sec=1.2):
    global TOAST_TEXT, TOAST_TIMER
    TOAST_TEXT = text
    TOAST_TIMER = sec

def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return (c1[0]*(1-t)+c2[0]*t, c1[1]*(1-t)+c2[1]*t, c1[2]*(1-t)+c2[2]*t)

def set_camera(boat):
    glDisable(GL_BLEND); glEnable(GL_DEPTH_TEST); glDepthMask(GL_TRUE)
    glEnable(GL_CULL_FACE); glCullFace(GL_BACK); glLineWidth(1.0)
    f = boat.forward_vec()
    cam_dist, cam_height = 14.0, 10.0
    eye_x = boat.pos.x - f.x*cam_dist
    eye_y = cam_height
    eye_z = boat.pos.y - f.y*cam_dist
    center_x = boat.pos.x + f.x*8.0
    center_y = 0.0
    center_z = boat.pos.y + f.y*8.0
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    from OpenGL.GLU import gluLookAt
    gluLookAt(eye_x, eye_y, eye_z, center_x, center_y, center_z, 0, 1, 0)

def draw_river_ground():
    glDisable(GL_CULL_FACE)
    glColor3f(*lerp_color(cfg.SHALLOW_WATER, cfg.DEEP_WATER, 0.5))
    xL, xR = -RIVER_WIDTH/2, RIVER_WIDTH/2
    glBegin(GL_QUADS)
    glVertex3f(xL,0,0); glVertex3f(xR,0,0); glVertex3f(xR,0,RIVER_LENGTH); glVertex3f(xL,0,RIVER_LENGTH)
    glEnd()
    for i, ln in enumerate(LANES):
        y = cfg.WATER_EPS*(i+1)
        c = depth_to_color(ln.depth, MIN_DEPTH, MAX_DEPTH)
        glColor3f(*c)
        glBegin(GL_QUADS)
        glVertex3f(xL,y,ln.z0); glVertex3f(xR,y,ln.z0); glVertex3f(xR,y,ln.z1); glVertex3f(xL,y,ln.z1)
        glEnd()
    glEnable(GL_CULL_FACE)

def draw_banks():
    glPushMatrix(); glTranslatef(-RIVER_WIDTH/2-0.5, 1.0, RIVER_LENGTH/2)
    draw_box(0.5,1.0,RIVER_LENGTH/2,(0.2,0.45,0.25)); glPopMatrix()
    glPushMatrix(); glTranslatef(+RIVER_WIDTH/2+0.5, 1.0, RIVER_LENGTH/2)
    draw_box(0.5,1.0,RIVER_LENGTH/2,(0.2,0.45,0.25)); glPopMatrix()

def reset_round(state, reroll_lanes=True):
    """스테이지 시작 상태로 초기화"""
    global lane_tune_timer, current_lane_idx
    state["started"] = False
    state["time_left"] = cfg.SECONDS_LIMIT
    state["win"] = False
    state["lose"] = False
    state["boat"] = Boat(0.0, cfg.RIVER_LENGTH - 6.0)
    if reroll_lanes:
        randomize_lane_depths()
        globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()
    for i in range(len(FLOW_SCALE)):
        # NOTE: 라운드 시작시 현재 FLOW_SCALE은 그대로 유지 (스테이지 난이도 반영)
        FLOW_SCALE[i] = FLOW_SCALE[i]
    lane_tune_timer = 0.0
    current_lane_idx = get_lane_index(state["boat"].pos.y)
    state["obstacles"], state["coins"], state["dock"] = build_scene()

    # distance/score
    state["start_z"] = state["boat"].pos.y
    state["best_z"]  = state["boat"].pos.y
    state["score"]   = 0

    # stage counter (없으면 1로)
    state["stage"] = state.get("stage", 1)

def apply_next_stage_scales():
    """다음 스테이지 배율을 전역 FLOW_SCALE에 적용"""
    for i in range(min(len(FLOW_SCALE), len(NEXT_SCALES))):
        FLOW_SCALE[i] = NEXT_SCALES[i]

def load_texture_once(paths):
    for p in paths:
        if os.path.exists(p):
            return load_texture_rgba(p)
    return None

def main():
    global PAUSED, TOAST_TIMER, TOAST_TEXT, lane_tune_timer, current_lane_idx
    global NEXT_STAGE_MODE, NEXT_SCALES, NEXT_ACTIVE

    pygame.init()
    try:
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS,1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES,4)
    except Exception:
        pass

    pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("River Crossing 3D – Manning Scaling (Stage Tuner)")
    clock = pygame.time.Clock()
    gltext = GLText(size=18)
    init_gl()
    state = {}
    reset_round(state)

    # textures
    coin_tex = load_texture_once([
        os.path.join("assets", "coin.png"),
        os.path.join(os.path.dirname(__file__), "assets", "coin.png"),
        "coin.png",
    ])
    boat_tex = load_texture_once([
        os.path.join("assets", "boat2.png"),
        os.path.join(os.path.dirname(__file__), "assets", "boat2.png"),
        "boat2.png",
    ])

    # 초기 NEXT_SCALES는 현 FLOW_SCALE 복사
    NEXT_SCALES = list(FLOW_SCALE)
    NEXT_ACTIVE = None

    while True:
        dt = clock.tick(FPS) / 1000.0

        # ----- events -----
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)

            # -------- Next Stage Tuner 모드 입력 --------
            if NEXT_STAGE_MODE:
                if ev.type == pygame.KEYDOWN:
                    # 레인 선택(1..5)
                    if ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                        NEXT_ACTIVE = ev.key - pygame.K_1
                    # 선택 레인 값 미세 조정
                    elif ev.key in (pygame.K_LEFT, pygame.K_MINUS):
                        if NEXT_ACTIVE is not None:
                            NEXT_SCALES[NEXT_ACTIVE] = max(0.60, NEXT_SCALES[NEXT_ACTIVE] - 0.05)
                    elif ev.key in (pygame.K_RIGHT, pygame.K_EQUALS):
                        if NEXT_ACTIVE is not None:
                            NEXT_SCALES[NEXT_ACTIVE] = min(1.60, NEXT_SCALES[NEXT_ACTIVE] + 0.05)
                    # 전체 프리셋 키 (편의)
                    elif ev.key == pygame.K_a:  # 느리게
                        NEXT_SCALES = [0.85]*len(NEXT_SCALES)
                    elif ev.key == pygame.K_s:  # 기본
                        NEXT_SCALES = [1.00]*len(NEXT_SCALES)
                    elif ev.key == pygame.K_d:  # 빠르게
                        NEXT_SCALES = [1.15]*len(NEXT_SCALES)

                    # 적용 / 취소
                    elif ev.key == pygame.K_RETURN:
                        # 적용 후 다음 스테이지 시작
                        apply_next_stage_scales()
                        state["stage"] = state.get("stage", 1) + 1
                        # 다음 스테이지는 새 장애물/코인/도크 리롤
                        reset_round(state, reroll_lanes=True)
                        NEXT_STAGE_MODE = False
                        show_toast(f"Stage {state['stage']} start!")
                    elif ev.key == pygame.K_ESCAPE:
                        # 취소: 기본값(1.0)로 시작
                        NEXT_SCALES = [1.0]*len(NEXT_SCALES)
                        apply_next_stage_scales()
                        state["stage"] = state.get("stage", 1) + 1
                        reset_round(state, reroll_lanes=True)
                        NEXT_STAGE_MODE = False
                        show_toast(f"Stage {state['stage']} start!")
                # 튜너 모드에선 나머지 입력 무시
                continue

            # -------- 일반 모드 입력 --------
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    PAUSED = not PAUSED
                elif ev.key == pygame.K_q and PAUSED:
                    pygame.quit(); sys.exit(0)
                elif ev.key == pygame.K_r:
                    reset_round(state)
                elif ev.key == pygame.K_l:
                    randomize_lane_depths()
                    globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()
                    show_toast("Rerolled lanes")
                elif ev.key == pygame.K_m:
                    cfg.SHOW_MINIMAP = not cfg.SHOW_MINIMAP
                    show_toast(f"Minimap {'ON' if cfg.SHOW_MINIMAP else 'OFF'}")
                elif ev.key == pygame.K_p:
                    cfg.SHOW_PREDICT = not cfg.SHOW_PREDICT
                    show_toast(f"Predict {'ON' if cfg.SHOW_PREDICT else 'OFF'}")
                elif ev.key == pygame.K_t:
                    cfg.USE_MOUSE_STEER = not cfg.USE_MOUSE_STEER
                    show_toast(f"Mouse steer {'ON' if cfg.USE_MOUSE_STEER else 'OFF'}")
                elif ev.key == pygame.K_LEFTBRACKET:
                    cfg.TURN_RATE_DEG = max(40.0, cfg.TURN_RATE_DEG - 10.0)
                    show_toast(f"Turn {cfg.TURN_RATE_DEG:.0f}°/s")
                elif ev.key == pygame.K_RIGHTBRACKET:
                    cfg.TURN_RATE_DEG = min(240.0, cfg.TURN_RATE_DEG + 10.0)
                    show_toast(f"Turn {cfg.TURN_RATE_DEG:.0f}°/s")
                elif ev.key == pygame.K_SEMICOLON:
                    cfg.ENGINE_THRUST = max(6.0, cfg.ENGINE_THRUST - 1.0)
                    show_toast(f"Thrust {cfg.ENGINE_THRUST:.1f}")
                elif ev.key == pygame.K_QUOTE:
                    cfg.ENGINE_THRUST = min(28.0, cfg.ENGINE_THRUST + 1.0)
                    show_toast(f"Thrust {cfg.ENGINE_THRUST:.1f}")
                elif ev.key == pygame.K_RETURN:
                    if not state["started"]:
                        state["boat"].set_initial()
                        state["started"] = True
                elif lane_tune_timer > 0.0:
                    mapping = {
                        pygame.K_1: 0.70,  # -30%
                        pygame.K_2: 0.85,  # -15%
                        pygame.K_3: 1.00,  # base
                        pygame.K_4: 1.15,  # +15%
                        pygame.K_5: 1.30,  # +30%
                    }
                    if ev.key in mapping and current_lane_idx is not None:
                        FLOW_SCALE[current_lane_idx] = mapping[ev.key]
                        show_toast(f"Lane {current_lane_idx+1} speed x{FLOW_SCALE[current_lane_idx]:.2f}")
                        lane_tune_timer = 0.0

        if TOAST_TIMER > 0:
            TOAST_TIMER -= dt
            if TOAST_TIMER <= 0:
                TOAST_TEXT = ""

        keys = pygame.key.get_pressed()
        boat = state["boat"]

        if not NEXT_STAGE_MODE:
            if not state["started"] and not PAUSED:
                if keys[pygame.K_LEFT] or keys[pygame.K_RIGHT] or keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_RETURN]:
                    boat.set_initial(); state["started"] = True

            if not PAUSED and state["started"] and not (state["win"] or state["lose"]):
                # steering / throttle
                if cfg.USE_MOUSE_STEER:
                    mx,_ = pygame.mouse.get_pos()
                    centered = (mx - WIDTH/2) / (WIDTH/2)
                    boat.adjust_angle(centered * cfg.TURN_RATE_DEG * 0.6 * dt)
                else:
                    turn = 0.0
                    if keys[pygame.K_LEFT]:  turn -= 1.0
                    if keys[pygame.K_RIGHT]: turn += 1.0
                    if turn:
                        boat.adjust_angle(turn * cfg.TURN_RATE_DEG * dt)

                thrust = 0.0
                if keys[pygame.K_UP] or keys[pygame.K_w]:   thrust += cfg.ENGINE_THRUST
                if keys[pygame.K_DOWN] or keys[pygame.K_s]: thrust -= cfg.BRAKE_THRUST
                boat.last_throttle = 0.0 if thrust == 0 else max(-1.0, min(1.0, thrust / cfg.ENGINE_THRUST))
                if thrust: boat.apply_thrust(thrust, dt)

        # ----- world update -----
        coins = state["coins"]; obstacles = state["obstacles"]; dock = state["dock"]

        if not NEXT_STAGE_MODE and not PAUSED and state["started"] and not (state["win"] or state["lose"]):
            state["time_left"] -= dt
            boat.update(dt)

            # distance/score
            if boat.pos.y < state["best_z"]:
                state["best_z"] = boat.pos.y
            best_covered = max(0.0, state["start_z"] - state["best_z"])
            # 점수 규칙이 config 에 있을 경우만 사용, 없으면 0 유지
            if hasattr(cfg, "SCORE_PER_M"):
                state["score"] = int(best_covered * cfg.SCORE_PER_M)

            # 레인 진입 감지 → 튜닝창 오픈
            idx = get_lane_index(boat.pos.y)
            if idx is not None and idx != current_lane_idx:
                current_lane_idx = idx
                lane_tune_timer = getattr(cfg, "LANE_TUNE_WINDOW", 2.0)
                show_toast(f"Lane {idx+1} tuning: 1..5")

            if lane_tune_timer > 0.0:
                lane_tune_timer -= dt
                if lane_tune_timer < 0.0: lane_tune_timer = 0.0

            # 경계 이탈
            if abs(boat.pos.x) > cfg.RIVER_WIDTH*0.51 or boat.pos.y < -2 or boat.pos.y > cfg.RIVER_LENGTH + 2:
                state["lose"] = True

            # 코인
            for c in coins:
                if c.alive:
                    dx = boat.pos.x - c.x
                    dz = boat.pos.y - c.z
                    if dx*dx + dz*dz <= (max(cfg.BOAT_WID, cfg.BOAT_LEN)/2 + c.r)**2:
                        c.alive = False
                        state["time_left"] += cfg.COIN_TIME_BONUS
                        if hasattr(cfg, "TIME_LEFT_MAX"):
                            state["time_left"] = min(state["time_left"], cfg.TIME_LEFT_MAX)
                        show_toast("+5s")

            # 충돌
            ba = boat_aabb(boat)
            for ob in obstacles:
                if aabb_overlap(ba, ob.aabb()):
                    bounce_response(boat, ob)
                    break

            # 도크 도달 → 바로 튜너 모드로 전환
            if aabb_overlap(ba, dock.aabb()):
                state["win"] = True
                # 다음 스테이지 튜너 모드 ON
                NEXT_STAGE_MODE = True
                # 현재 FLOW_SCALE을 기본값으로 복사
                NEXT_SCALES = list(FLOW_SCALE)
                NEXT_ACTIVE = None
                show_toast("SUCCESS! Set next-stage river speeds (1..5 select, ←/→ adjust, Enter start)")

            # 시간 초과
            if state["time_left"] <= 0.0 and not state["win"]:
                state["lose"] = True

        # ----- render 3D -----
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        set_camera(boat)

        draw_river_ground()
        draw_banks()

        # dock
        glPushMatrix(); glTranslatef(0.0, 0.05, dock.z)
        draw_box(dock.w/2, 0.05, dock.l/2, (0.16, 0.70, 0.36)); glPopMatrix()

        # obstacles
        for ob in obstacles:
            glPushMatrix(); glTranslatef(ob.x, ob.h/2, ob.z)
            draw_box(ob.w/2, ob.h/2, ob.l/2, (0.15, 0.15, 0.18))
            glPopMatrix()

        # coins
        for c in coins:
            if not c.alive: continue
            glPushMatrix()
            # 세워진 동전 느낌
            glTranslatef(c.x, c.r, c.z)
            glRotatef(90.0, 1, 0, 0)
            spin = (pygame.time.get_ticks() * 0.18) % 360
            glRotatef(spin, 0, 0, 1)
            if coin_tex is not None:
                draw_textured_coin(radius=c.r, thickness=0.25, tex_id=coin_tex, slices=64, tex_scale=0.7)
            else:
                draw_cylinder(radius=c.r, height=0.25, color=(245/255,170/255,30/255))
            glPopMatrix()

        # boat decal (카메라 빌보드)
        if boat_tex is not None:
            f = boat.forward_vec()
            yaw = math.degrees(math.atan2(f.x, f.y))
            glPushMatrix()
            glTranslatef(boat.pos.x, BOAT_HGT + 0.02, boat.pos.y)
            glRotatef(yaw, 0, 1, 0)
            glDisable(GL_CULL_FACE)
            glEnable(GL_TEXTURE_2D)
            glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glBindTexture(GL_TEXTURE_2D, boat_tex)
            hw, hl = BOAT_WID * 1.2, BOAT_LEN * 0.8
            glColor4f(1,1,1,1)
            glBegin(GL_QUADS)
            glTexCoord2f(0,0); glVertex3f(-hw, 0.0, -hl)
            glTexCoord2f(1,0); glVertex3f( hw, 0.0, -hl)
            glTexCoord2f(1,1); glVertex3f( hw, 0.0,  hl)
            glTexCoord2f(0,1); glVertex3f(-hw, 0.0,  hl)
            glEnd()
            glBindTexture(GL_TEXTURE_2D, 0)
            glDisable(GL_TEXTURE_2D); glDisable(GL_BLEND)
            glEnable(GL_CULL_FACE)
            glPopMatrix()

        # predictive path
        if cfg.SHOW_PREDICT:
            pos = boat.pos.copy(); vel = boat.vel.copy(); pts = []
            for _ in range(cfg.PREDICT_STEPS):
                flow = river_flow_vx(pos.y)
                v_rel_x = vel.x - flow
                v_rel_z = vel.y
                vel.x -= v_rel_x * cfg.DRAG_X * cfg.PREDICT_DT
                vel.y -= v_rel_z * cfg.DRAG_Z * cfg.PREDICT_DT
                vel.x += flow * cfg.PREDICT_DT
                pos += vel * cfg.PREDICT_DT
                if abs(pos.x)>cfg.RIVER_WIDTH*0.51 or pos.y< -2 or pos.y>cfg.RIVER_LENGTH+2: break
                pts.append((pos.x, pos.y))
            if pts:
                glEnable(GL_DEPTH_TEST); glDisable(GL_BLEND); glLineWidth(2); glColor4f(0.1,0.1,0.1,0.7)
                glBegin(GL_LINE_STRIP)
                for x,z in pts: glVertex3f(x, 0.08, z)
                glEnd()

        # ----- HUD -----
        begin_ortho()
        total = len(coins); got = sum(1 for c in coins if not c.alive)
        progress_m = max(0.0, state["start_z"] - boat.pos.y)
        progress_total_m = max(0.0, state["start_z"] - dock.z)
        draw_top_timer(gltext,
                       max(0.0, state["time_left"]),
                       got, total,
                       progress_m,
                       stage=state.get("stage", 1),
                       progress_total_m=progress_total_m,
                       score=state["score"])

        draw_compass(gltext, boat)
        draw_throttle_gauge(gltext, boat)
        draw_minimap(gltext, boat, dock)
        draw_help_strip(gltext)

        if lane_tune_timer > 0.0:
            draw_lane_tune_prompt(gltext, current_lane_idx)

        if TOAST_TEXT:
            draw_toast(gltext, TOAST_TEXT)

        # 승패 배너 대신, 승리 시에는 다음 스테이지 튜너 표시
        if NEXT_STAGE_MODE:
            draw_next_stage_tuner(gltext, NEXT_SCALES, NEXT_ACTIVE)
        else:
            if state["lose"]:
                gltext.draw("FAIL", WIDTH//2-30, HEIGHT//2-10, (232,93,93,255))

        end_ortho()

        pygame.display.flip()

if __name__ == "__main__":
    main()
