import sys, math, os, pygame
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import *

from river3d.config import (
    WIDTH, HEIGHT, FPS, SHOW_MINIMAP, SHOW_PREDICT, USE_MOUSE_STEER,
    ENGINE_THRUST, BRAKE_THRUST, TURN_RATE_DEG, RIVER_WIDTH, RIVER_LENGTH,
    SECONDS_LIMIT, COIN_TIME_BONUS, PREDICT_STEPS, PREDICT_DT,
    BOAT_LEN, BOAT_WID, BOAT_HGT,
    UI_BG_DARK, DOCK_COLOR, BANK_COLOR, SHALLOW_WATER, DEEP_WATER,
    MARKERS, WATER_EPS,
    DRAG_X, DRAG_Z, TIME_LEFT_MAX, SCORE_PER_M, LANE_TUNE_WINDOW
)
from river3d import config as cfg

from river3d.entities import Boat, boat_aabb, Obstacle, Coin, Dock
from river3d.lanes import (
    LANES, LANE_INFO, FLOW_SCALE, build_lanes_from_manning,
    randomize_lane_depths, get_lane_index, river_flow_vx, MIN_DEPTH, MAX_DEPTH
)
from river3d.physics import aabb_overlap, bounce_response

from river3d.glutils import (
    init_gl, begin_ortho, end_ortho, GLText,
    draw_box, draw_cylinder, load_texture_rgba,
    draw_textured_coin, depth_to_color
)
from river3d.scene import build_scene
from river3d.hud import (
    draw_minimap, draw_compass, draw_throttle_gauge, draw_top_timer,
    draw_help_strip, draw_lane_tune_prompt, draw_toast
)

# ---------- 런치 UI(초기속력) 오버레이 ----------
LAUNCH_RADIUS = 70
LAUNCH_SPEED_MAX = 22.0  # m/s 기준 속력 캡
LAUNCH_CENTER = (140, HEIGHT - 140)

def draw_launch_overlay(gltext: GLText, vec_screen):
    # 반투명 배경
    from OpenGL.GL import glColor4f, glBegin, glEnd, glVertex2f, GL_QUADS
    begin_ortho()
    # 배경
    def quad2(x,y,w,h,rgba):
        glColor4f(*rgba)
        glBegin(GL_QUADS)
        glVertex2f(x,y); glVertex2f(x+w,y)
        glVertex2f(x+w,y+h); glVertex2f(x,y+h)
        glEnd()
    quad2(0,0, WIDTH,HEIGHT, (0,0,0,0.35))

    # 패드
    cx, cy = LAUNCH_CENTER
    # 원 테두리
    import math as _m
    glColor4f(0.2,0.24,0.3,0.95)
    glBegin(GL_QUADS); glEnd()
    # 외곽 원은 pygame 없이 간단히 라인으로
    # 대신 안쪽은 사각으로 그림자
    quad2(cx-LAUNCH_RADIUS-10, cy-LAUNCH_RADIUS-10, 2*(LAUNCH_RADIUS+10), 2*(LAUNCH_RADIUS+10), (0.1,0.1,0.12,0.55))
    quad2(cx-LAUNCH_RADIUS, cy-LAUNCH_RADIUS, 2*LAUNCH_RADIUS, 2*LAUNCH_RADIUS, (0.16,0.18,0.22,0.95))

    # 벡터 화살표(위로 드래그= -Z 로 직진)
    vx_s, vy_s = vec_screen  # 화면 기준
    tipx, tipy = cx + vx_s, cy + vy_s
    # 선
    glColor4f(0.35,0.75,1.0,1.0)
    glBegin(GL_LINES)
    glVertex2f(cx, cy); glVertex2f(tipx, tipy)
    glEnd()
    # 화살표 머리(간단 삼각)
    hx, hy = tipx, tipy
    side = 8
    glBegin(GL_TRIANGLES)
    glVertex2f(hx, hy)
    glVertex2f(hx- side, hy+ side)
    glVertex2f(hx+ side, hy+ side)
    glEnd()

    # 텍스트
    gltext.draw("Launch Vector (Drag)  |  ENTER to start, R to reroll", cx+90, cy-16, (230,230,235,255))
    gltext.draw("↑ up = go forward (toward dock)", cx+90, cy+10, (200,210,220,255))
    end_ortho()

def clamp_launch_vec(screen_dx, screen_dy):
    # 화면 공간 드래그를 반경 제한 + 속력 스케일로 변환
    import math as _m
    r = _m.hypot(screen_dx, screen_dy)
    if r < 1e-6:
        return (0.0,0.0), 0.0
    if r > LAUNCH_RADIUS:
        scale = LAUNCH_RADIUS / r
        screen_dx *= scale; screen_dy *= scale
        r = LAUNCH_RADIUS
    speed = (r/LAUNCH_RADIUS) * LAUNCH_SPEED_MAX
    return (screen_dx, screen_dy), speed

def screenvec_to_worldvel(screen_dx, screen_dy, speed_mag):
    """
    화면 기준: +x=오른쪽, +y=아래.
    월드 기준: x=좌우, z=앞뒤. '위로 드래그'는 -z(도크 쪽)이어야 직진.
    """
    import math as _m
    if speed_mag < 1e-6: return 0.0, 0.0
    # 방향 단위벡터(화면)
    ux = screen_dx / (max(1e-6, (screen_dx**2 + screen_dy**2)**0.5))
    uy = screen_dy / (max(1e-6, (screen_dx**2 + screen_dy**2)**0.5))
    # 화면 +y(아래) -> 월드 +z(아래방향) 이므로: 월드 z성분 = +uy
    # 하지만 '위로' 드래그하면 uy<0 → 월드 z 음수(앞쪽) = 정상
    wx = ux * speed_mag
    wz = uy * speed_mag
    return wx, wz

# ---------- 토스트 ----------
PAUSED = False
TOAST_TIMER = 0.0
TOAST_TEXT = ""
lane_tune_timer = 0.0
current_lane_idx = None

def show_toast(text, sec=1.2):
    global TOAST_TEXT, TOAST_TIMER
    TOAST_TEXT = text
    TOAST_TIMER = sec

def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return (
        c1[0] * (1 - t) + c2[0] * t,
        c1[1] * (1 - t) + c2[1] * t,
        c1[2] * (1 - t) + c2[2] * t,
    )

def set_camera(boat: Boat):
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glDepthMask(GL_TRUE)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)
    glLineWidth(1.0)

    f = boat.forward_vec()
    cam_dist, cam_height = 14.0, 10.0
    eye_x = boat.pos.x - f.x * cam_dist
    eye_y = cam_height
    eye_z = boat.pos.y - f.y * cam_dist
    center_x = boat.pos.x + f.x * 8.0
    center_y = 0.0
    center_z = boat.pos.y + f.y * 8.0

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    from OpenGL.GLU import gluLookAt
    gluLookAt(eye_x, eye_y, eye_z, center_x, center_y, center_z, 0, 1, 0)



def draw_river_ground():
    glDisable(GL_CULL_FACE)
    glColor3f(*lerp_color(SHALLOW_WATER, DEEP_WATER, 0.5))
    xL, xR = -RIVER_WIDTH / 2, RIVER_WIDTH / 2
    glBegin(GL_QUADS)
    glVertex3f(xL, 0, 0)
    glVertex3f(xR, 0, 0)
    glVertex3f(xR, 0, RIVER_LENGTH)
    glVertex3f(xL, 0, RIVER_LENGTH)
    glEnd()

    for i, ln in enumerate(LANES):
        y = WATER_EPS * (i + 1)
        c = depth_to_color(ln.depth, MIN_DEPTH, MAX_DEPTH)
        glColor3f(*c)
        glBegin(GL_QUADS)
        glVertex3f(xL, y, ln.z0)
        glVertex3f(xR, y, ln.z0)
        glVertex3f(xR, y, ln.z1)
        glVertex3f(xL, y, ln.z1)
        glEnd()
    glEnable(GL_CULL_FACE)

def draw_banks():
    glPushMatrix()
    glTranslatef(-RIVER_WIDTH / 2 - 0.5, 1.0, RIVER_LENGTH / 2)
    draw_box(0.5, 1.0, RIVER_LENGTH / 2, BANK_COLOR)
    glPopMatrix()

    glPushMatrix()
    glTranslatef(+RIVER_WIDTH / 2 + 0.5, 1.0, RIVER_LENGTH / 2)
    draw_box(0.5, 1.0, RIVER_LENGTH / 2, BANK_COLOR)
    glPopMatrix()

# ---------- 보트 렌더링(수정) ----------
def draw_boat_mesh(boat: Boat):
    """
    텍스처 없이 보트 본체 렌더링:
    - 모델뷰 행렬을 항상 push/pop으로 감싼다.
    - 변환 순서를 명확히 하고, 잔여 스케일이 있으면 제거한다.
    - draw_box(half_w, half_h, half_l, color) 를 그대로 사용하되
      내부 행렬 상태가 오염되는 것을 방지한다.
    """
    glEnable(GL_NORMALIZE)  # 노멀 정규화 활성화 (회전시 조명 문제 해결)

    glPushMatrix()
    try:
        # 모델의 위치를 이동 (x, y, z) 좌표로 이동
        glTranslatef(boat.pos.x, BOAT_HGT / 2.0, boat.pos.y)

        # 회전 처리: 배의 회전은 y축을 기준으로 해야 한다.
        # 회전 순서를 잘못 설정하면 배가 찌그러질 수 있다.
        glRotatef(-boat.heading, 0.0, 1.0, 0.0)  # y축 기준으로 회전

        # 크기 고정: 배의 크기 변형을 방지하기 위해 고정 크기로 설정
        glScalef(1.0, 1.0, 1.0)

        # 보트 그리기: 텍스처를 제외한 모델만 렌더링
        draw_box(BOAT_WID / 2.0, BOAT_HGT / 2.0, BOAT_LEN / 2.0, (0.85, 0.28, 0.28))

    finally:
        glPopMatrix()
        glDisable(GL_NORMALIZE)

def draw_boat_decal(boat: Boat, boat_tex=None):
    """
    텍스처 없이 보트 상면 그리기.
    텍스처 매핑 부분을 제거하고, 단색으로 그리도록 처리.
    """
    # 텍스처가 없으면 텍스처 관련 처리하지 않음
    if boat_tex is None:
        # 텍스처 없이 색상으로 그리기
        glPushMatrix()
        glTranslatef(boat.pos.x, BOAT_HGT + 0.02, boat.pos.y)

        # 회전 처리: 배의 회전은 y축을 기준으로 해야 한다.
        glRotatef(-boat.heading, 0.0, 1.0, 0.0)  # y축 기준으로 회전

        # 색상 설정 (회색으로 보트 상면 그리기)
        glColor3f(0.7, 0.7, 0.7)  # 예시로 회색으로 지정

        # 보트 상면 그리기
        hw, hl = BOAT_WID * 0.95, BOAT_LEN * 1.10
        glBegin(GL_QUADS)
        glVertex3f(-hw, 0.0, -hl)
        glVertex3f(hw, 0.0, -hl)
        glVertex3f(hw, 0.0, hl)
        glVertex3f(-hw, 0.0, hl)
        glEnd()

        glPopMatrix()


# ---------- 라운드/상태 ----------
def reset_round(state, reroll_lanes=True):
    global lane_tune_timer, current_lane_idx
    state["started"] = False
    state["show_launch"] = True            # 런치 오버레이 표시
    state["launch_vec_screen"] = (0.0, -LAUNCH_RADIUS * 0.6)  # 기본 위쪽
    state["time_left"] = cfg.SECONDS_LIMIT
    state["win"] = False
    state["lose"] = False

    # 보트 초기화: 위치는 기존대로, 속도는 0으로(정지), heading은 왼쪽으로 90도 회전
    state["boat"] = Boat(0.0, cfg.RIVER_LENGTH - 6.0)
    b = state["boat"]
    # 정지 상태로 강제
    try:
        b.vel.x = 0.0
        b.vel.y = 0.0
    except Exception:
        # Boat 클래스에 vel 필드가 없을 경우 안전하게 무시
        pass

    # 왼쪽 90도 회전: (필요하면 +90으로 바꿔 테스트)

    if reroll_lanes:
        randomize_lane_depths()
        globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()

    for i in range(len(FLOW_SCALE)):
        FLOW_SCALE[i] = 1.0

    lane_tune_timer = 0.0
    current_lane_idx = get_lane_index(state["boat"].pos.y)
    state["obstacles"], state["coins"], state["dock"] = build_scene()

    # distance / score
    state["start_z"] = state["boat"].pos.y
    state["best_z"] = state["boat"].pos.y
    state["score"] = 0

def main():
    global PAUSED, TOAST_TIMER, TOAST_TEXT, lane_tune_timer, current_lane_idx

    pygame.init()
    try:
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)
    except Exception:
        pass

    pygame.display.set_mode((WIDTH, HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("River Crossing 3D – Launch UI + Boat Fix")
    clock = pygame.time.Clock()
    gltext = GLText(size=18)
    init_gl()
    state = {}
    reset_round(state)

    # --- textures (coin / boat) ---
    coin_tex = None
    for p in [
        os.path.join("assets", "coin.png"),
        os.path.join(os.path.dirname(__file__), "assets", "coin.png"),
        "coin.png",
    ]:
        if os.path.exists(p):
            coin_tex = load_texture_rgba(p)
            break

    boat_tex = None
    for p in [
        os.path.join("assets", "boat2.png"),
        os.path.join(os.path.dirname(__file__), "assets", "boat2.png"),
        "boat2.png",
    ]:
        if os.path.exists(p):
            boat_tex = load_texture_rgba(p)
            break

    dragging = False  # 런치 벡터 드래그 중?

    while True:
        dt = clock.tick(FPS) / 1000.0

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)

            # -------- 런치 오버레이 입력 --------
            if state["show_launch"]:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    # 패드 안에서만 드래그 시작
                    mx, my = ev.pos
                    cx, cy = LAUNCH_CENTER
                    if (mx - cx) ** 2 + (my - cy) ** 2 <= (LAUNCH_RADIUS + 14) ** 2:
                        dragging = True
                elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    dragging = False
                elif ev.type == pygame.MOUSEMOTION and dragging:
                    mx, my = ev.pos
                    cx, cy = LAUNCH_CENTER
                    dx = mx - cx
                    dy = my - cy
                    (dx, dy), _ = clamp_launch_vec(dx, dy)
                    state["launch_vec_screen"] = (dx, dy)
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_RETURN:
                        # 화면 벡터 → 월드 초기 속력
                        dx, dy = state["launch_vec_screen"]
                        (dx, dy), sp = clamp_launch_vec(dx, dy)
                        wx, wz = screenvec_to_worldvel(dx, dy, sp)
                        b = state["boat"]
                        b.vel.x = wx
                        b.vel.y = wz
                        state["show_launch"] = False
                        state["started"] = True
                    elif ev.key == pygame.K_r:
                        randomize_lane_depths()
                        globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()
                        reset_round(state)
                # 런치 상태면 여기서 더 처리 안 하고 다음 루프로
                continue

            # -------- 게임 입력 --------
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

        if TOAST_TIMER > 0:
            TOAST_TIMER -= dt
        if TOAST_TIMER <= 0:
            TOAST_TEXT = ""

        keys = pygame.key.get_pressed()
        boat = state["boat"]

        # 입력/물리
        if not PAUSED and state["started"] and not (state["win"] or state["lose"]):
            if cfg.USE_MOUSE_STEER:
                mx, _ = pygame.mouse.get_pos()
                centered = (mx - WIDTH / 2) / (WIDTH / 2)
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
            if thrust:
                boat.apply_thrust(thrust, dt)

        # 월드 업데이트
        coins = state["coins"]
        obstacles = state["obstacles"]
        dock = state["dock"]

        if not PAUSED and state["started"] and not (state["win"] or state["lose"]):
            state["time_left"] -= dt
            boat.update(dt)

            # 거리/점수
            if boat.pos.y < state["best_z"]:
                state["best_z"] = boat.pos.y
            best_covered = max(0.0, state["start_z"] - state["best_z"])
            state["score"] = int(best_covered * cfg.SCORE_PER_M)

            # 레인 튜닝 안내
            idx = get_lane_index(boat.pos.y)
            if idx is not None and idx != current_lane_idx:
                current_lane_idx = idx
                lane_tune_timer = LANE_TUNE_WINDOW
                show_toast(f"Lane {idx+1} tuning: 1..5")

            if lane_tune_timer > 0.0:
                lane_tune_timer -= dt
                if lane_tune_timer < 0.0:
                    lane_tune_timer = 0.0

            # 경계 이탈
            if abs(boat.pos.x) > cfg.RIVER_WIDTH * 0.51 or boat.pos.y < -2 or boat.pos.y > cfg.RIVER_LENGTH + 2:
                state["lose"] = True

            # 코인
            for c in coins:
                if c.alive:
                    dx = boat.pos.x - c.x
                    dz = boat.pos.y - c.z
                    if dx * dx + dz * dz <= (max(cfg.BOAT_WID, cfg.BOAT_LEN) / 2 + c.r) ** 2:
                        c.alive = False
                        state["time_left"] += cfg.COIN_TIME_BONUS
                        state["time_left"] = min(state["time_left"], TIME_LEFT_MAX)
                        show_toast("+5s")

            # 장애물
            ba = boat_aabb(boat)
            for ob in obstacles:
                if aabb_overlap(ba, ob.aabb()):
                    bounce_response(boat, ob)
                    break

            # 도크
            if aabb_overlap(ba, dock.aabb()):
                state["win"] = True

            # 시간초과
            if state["time_left"] <= 0.0 and not state["win"]:
                state["lose"] = True

        # -------- 렌더 --------
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        set_camera(boat)

        draw_river_ground()
        draw_banks()

        # 도크
        glPushMatrix()
        glTranslatef(dock.x, 0.05, dock.z)
        draw_box(dock.w / 2, 0.05, dock.l / 2, DOCK_COLOR)
        glPopMatrix()

        # 장애물
        for ob in obstacles:
            glPushMatrix()
            glTranslatef(ob.x, ob.h / 2, ob.z)
            draw_box(ob.w / 2, ob.h / 2, ob.l / 2, (0.15, 0.15, 0.18))
            glPopMatrix()

        # 코인
        for c in coins:
            if c.alive:
                glPushMatrix()
                glTranslatef(c.x, c.r, c.z)
                glRotatef(90.0, 1, 0, 0)
                spin = (pygame.time.get_ticks() * 0.18) % 360
                glRotatef(spin, 0, 0, 1)
                if coin_tex is not None:
                    draw_textured_coin(radius=c.r, thickness=0.25, tex_id=coin_tex, slices=64, tex_scale=0.7)
                else:
                    draw_cylinder(radius=c.r, height=0.25, color=(245 / 255, 170 / 255, 30 / 255))
                glPopMatrix()

        # 보트
        draw_boat_mesh(boat)          # 본체
        draw_boat_decal(boat, boat_tex)  # 텍스처(있으면)

        # 예측 경로
        if cfg.SHOW_PREDICT and not state["show_launch"]:
            pos = boat.pos.copy()
            vel = boat.vel.copy()
            pts = []
            for _ in range(PREDICT_STEPS):
                flow = river_flow_vx(pos.y)
                v_rel_x = vel.x - flow
                v_rel_z = vel.y
                vel.x -= v_rel_x * DRAG_X * PREDICT_DT
                vel.y -= v_rel_z * DRAG_Z * PREDICT_DT
                vel.x += flow * PREDICT_DT
                pos += vel * PREDICT_DT
                if abs(pos.x) > RIVER_WIDTH * 0.51 or pos.y < -2 or pos.y > RIVER_LENGTH + 2:
                    break
                pts.append((pos.x, pos.y))
            if pts:
                glEnable(GL_DEPTH_TEST)
                glDisable(GL_BLEND)
                glLineWidth(2)
                glColor4f(0.1, 0.1, 0.1, 0.7)
                glBegin(GL_LINE_STRIP)
                for x, z in pts:
                    glVertex3f(x, 0.08, z)
                glEnd()

        # HUD
        begin_ortho()
        total = len(coins)
        got = sum(1 for c in coins if not c.alive)

        progress_m = max(0.0, state["start_z"] - boat.pos.y)
        progress_total_m = max(0.0, state["start_z"] - dock.z)

        draw_top_timer(
            gltext,
            max(0.0, state["time_left"]),
            got,
            total,
            progress_m,
            stage=1,
            progress_total_m=progress_total_m,
            score=state["score"]
        )
        draw_compass(gltext, boat)
        draw_throttle_gauge(gltext, boat)
        draw_minimap(gltext, boat, dock)
        draw_help_strip(gltext)

        if lane_tune_timer > 0.0:
            draw_lane_tune_prompt(gltext, current_lane_idx)

        if TOAST_TEXT:
            draw_toast(gltext, TOAST_TEXT)

        if state["win"]:
            gltext.draw("SUCCESS!", WIDTH // 2 - 70, HEIGHT // 2 - 10, (76, 201, 128, 255))
        elif state["lose"]:
            gltext.draw("FAIL", WIDTH // 2 - 30, HEIGHT // 2 - 10, (232, 93, 93, 255))
        end_ortho()

        # 런치 오버레이는 최후단에 그리기 (HUD 위)
        if state["show_launch"]:
            draw_launch_overlay(gltext, state["launch_vec_screen"])

        pygame.display.flip()

        

if __name__ == "__main__":
    main()
