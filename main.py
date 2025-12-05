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
    DRAG_X, DRAG_Z, TIME_LEFT_MAX, SCORE_PER_M, LANE_TUNE_WINDOW,
    ISLAND_LENGTH, ISLAND_WIDTH,
    LAVA_COLOR, OBSIDIAN_COLOR, MONSTER_COUNT, MONSTER_SPEED
)
from river3d import config as cfg

from river3d.entities import Boat, boat_aabb, Obstacle, Coin, Dock
from river3d.lanes import (
    LANES, LANE_INFO, FLOW_SCALE, build_lanes_from_manning,
    randomize_lane_depths, get_lane_index, river_flow_vx, MIN_DEPTH, MAX_DEPTH
)
from river3d.physics import aabb_overlap, bounce_response, wall_bounce, boat_aabb
from river3d.map_gen import get_river_center, get_river_width, get_island_bounds, generate_trees, generate_monsters

from river3d.glutils import (
    init_gl, begin_ortho, end_ortho, GLText,
    draw_box, draw_cylinder, load_texture_rgba,
    draw_textured_coin, depth_to_color,
    get_text_texture, draw_textured_quad_3d
)
from river3d.scene import build_scene
from river3d.hud import (
    draw_minimap, draw_compass, draw_throttle_gauge, draw_top_timer,
    draw_help_strip, draw_lane_tune_prompt, draw_toast, project_point,
    draw_lane_flow_popup
)

# ---------- 런치 UI(초기속력) 오버레이 ----------
LAUNCH_RADIUS = 70
LAUNCH_SPEED_MAX = 35.0  # m/s 기준 속력 캡 (User requested 35)
LAUNCH_CENTER = (140, HEIGHT - 140)

def quad2(x,y,w,h,rgba):
    glColor4f(*rgba)
    glBegin(GL_QUADS)
    glVertex2f(x,y); glVertex2f(x+w,y)
    glVertex2f(x+w,y+h); glVertex2f(x,y+h)
    glEnd()

def draw_launch_overlay(gltext: GLText, vec_screen):
    import math as _m
    from OpenGL.GL import glColor4f, glBegin, glEnd, glVertex2f, GL_QUADS, GL_LINES, GL_TRIANGLES, GL_LINE_STRIP, GL_TRIANGLE_FAN, glLineWidth
    begin_ortho()
    
    # 배경 (반투명)
    quad2(0,0, WIDTH,HEIGHT, (0,0,0,0.35))

    cx, cy = LAUNCH_CENTER
    vx_s, vy_s = vec_screen
    
    # 속력과 각도 계산
    vec_length = _m.hypot(vx_s, vy_s)
    speed = (vec_length / LAUNCH_RADIUS) * LAUNCH_SPEED_MAX
    speed_ratio = min(1.0, speed / LAUNCH_SPEED_MAX)
    
    # 색상 계산 (속력에 따라 파란색 → 빨간색)
    r = 0.3 + speed_ratio * 0.7
    g = 0.7 - speed_ratio * 0.4
    b = 1.0 - speed_ratio * 0.5
    
    # 각도 계산 (위쪽이 0도, 시계방향이 양수)
    if vec_length > 0.1:
        angle_rad = _m.atan2(vx_s, -vy_s)  # 위쪽 기준
        angle_deg = _m.degrees(angle_rad)
    else:
        angle_deg = 0
    
    # 패드 배경 (원형 느낌)
    # 외곽 그림자
    quad2(cx-LAUNCH_RADIUS-15, cy-LAUNCH_RADIUS-15, 2*(LAUNCH_RADIUS+15), 2*(LAUNCH_RADIUS+15), (0.05,0.05,0.08,0.7))
    
    # 원형 배경 (다각형으로 근사)
    glColor4f(0.12, 0.14, 0.18, 0.95)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx, cy)
    for i in range(33):
        theta = 2 * _m.pi * i / 32
        glVertex2f(cx + (LAUNCH_RADIUS+5) * _m.cos(theta), cy + (LAUNCH_RADIUS+5) * _m.sin(theta))
    glEnd()
    
    # 원형 테두리
    glColor4f(0.3, 0.5, 0.7, 0.8)
    glLineWidth(2)
    glBegin(GL_LINE_STRIP)
    for i in range(33):
        theta = 2 * _m.pi * i / 32
        glVertex2f(cx + LAUNCH_RADIUS * _m.cos(theta), cy + LAUNCH_RADIUS * _m.sin(theta))
    glEnd()
    
    # 십자선 가이드
    glColor4f(0.25, 0.3, 0.4, 0.5)
    glBegin(GL_LINES)
    glVertex2f(cx - LAUNCH_RADIUS, cy); glVertex2f(cx + LAUNCH_RADIUS, cy)
    glVertex2f(cx, cy - LAUNCH_RADIUS); glVertex2f(cx, cy + LAUNCH_RADIUS)
    glEnd()
    
    # 벡터 화살표 (그라데이션 효과)
    tipx, tipy = cx + vx_s, cy + vy_s
    
    if vec_length > 5:
        # 화살표 몸통 (두꺼운 선)
        glLineWidth(4)
        # 색상: 속력에 따라 파란색 → 빨간색
        speed_ratio = min(1.0, speed / LAUNCH_SPEED_MAX)
        r = 0.3 + speed_ratio * 0.7
        g = 0.7 - speed_ratio * 0.4
        b = 1.0 - speed_ratio * 0.5
        glColor4f(r, g, b, 1.0)
        glBegin(GL_LINES)
        glVertex2f(cx, cy)
        glVertex2f(tipx, tipy)
        glEnd()
        
        # 화살표 머리 (삼각형)
        head_size = 12 + speed_ratio * 8  # 속력에 따라 크기 변화
        if vec_length > 1:
            # 방향 벡터 정규화
            dx = vx_s / vec_length
            dy = vy_s / vec_length
            # 수직 벡터
            px, py = -dy, dx
            
            glBegin(GL_TRIANGLES)
            glVertex2f(tipx + dx * 5, tipy + dy * 5)  # 꼭지점
            glVertex2f(tipx - dx * head_size + px * head_size * 0.5, tipy - dy * head_size + py * head_size * 0.5)
            glVertex2f(tipx - dx * head_size - px * head_size * 0.5, tipy - dy * head_size - py * head_size * 0.5)
            glEnd()
    
    # 중심점
    glColor4f(1.0, 1.0, 1.0, 0.9)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx, cy)
    for i in range(17):
        theta = 2 * _m.pi * i / 16
        glVertex2f(cx + 5 * _m.cos(theta), cy + 5 * _m.sin(theta))
    glEnd()
    
    glLineWidth(1)
    
    # 속력 및 방향 정보 패널
    info_x, info_y = cx + LAUNCH_RADIUS + 20, cy - 60
    panel_w, panel_h = 180, 120
    quad2(info_x, info_y, panel_w, panel_h, (0.1, 0.12, 0.18, 0.9))
    
    # 테두리
    glColor4f(0.4, 0.6, 0.8, 0.8)
    glBegin(GL_LINE_STRIP)
    glVertex2f(info_x, info_y)
    glVertex2f(info_x + panel_w, info_y)
    glVertex2f(info_x + panel_w, info_y + panel_h)
    glVertex2f(info_x, info_y + panel_h)
    glVertex2f(info_x, info_y)
    glEnd()
    
    # 속력 표시
    gltext.draw("SPEED", info_x + 10, info_y + 10, (150, 180, 200, 255))
    speed_color = (100 + int(155 * speed_ratio), 200 - int(100 * speed_ratio), 255 - int(155 * speed_ratio), 255) if vec_length > 0.1 else (100, 100, 100, 255)
    gltext.draw(f"{speed:.1f} m/s", info_x + 10, info_y + 30, speed_color)
    
    # 방향 표시
    gltext.draw("DIRECTION", info_x + 10, info_y + 55, (150, 180, 200, 255))
    if vec_length > 5:
        if abs(angle_deg) < 15:
            dir_text = "Forward"
        elif angle_deg > 0:
            dir_text = f"Right {abs(angle_deg):.0f}°"
        else:
            dir_text = f"Left {abs(angle_deg):.0f}°"
    else:
        dir_text = "---"
    gltext.draw(dir_text, info_x + 10, info_y + 75, (255, 255, 200, 255))
    
    # 파워 게이지 (텍스트 아래에 바 표시)
    gltext.draw("POWER", info_x + 10, info_y + 95, (150, 180, 200, 255))
    gauge_w = int((panel_w - 30) * speed_ratio)
    # 배경 바
    quad2(info_x + 10, info_y + 115, panel_w - 30, 10, (0.2, 0.2, 0.25, 1.0))
    # 채워진 바
    if gauge_w > 0:
        quad2(info_x + 10, info_y + 115, gauge_w, 10, (r, g, b, 1.0))
    
    # 조작 안내
    gltext.draw("Drag to aim | ENTER to launch | R to reroll", cx - 40, cy + LAUNCH_RADIUS + 25, (200, 210, 220, 255))
    
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

# ---------- 레인 유속 팝업 ----------
lane_popup_timer = 0.0
lane_popup_duration = 2.0  # 2초간 표시
lane_popup_info = {"lane_num": 0, "flow_speed": 0.0, "flow_dir": 0}

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

def set_camera(boat: Boat, fall_offset=0.0, waterfall_mode=False):
    """
    카메라 설정.
    waterfall_mode=True이면 보트가 폭포로 떨어지는 것을 위에서 관찰.
    """
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glDepthMask(GL_TRUE)
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)
    glLineWidth(1.0)

    if waterfall_mode:
        # 폭포 전환: 카메라는 고정, 보트가 떨어지는 것을 관찰
        eye_x = boat.pos.x
        eye_y = 25.0  # 높은 위치에서 관찰
        eye_z = boat.pos.y + 20.0  # 뒤에서 관찰
        center_x = boat.pos.x
        center_y = -fall_offset  # 떨어지는 보트를 쳐다봄
        center_z = boat.pos.y - 10.0  # 폭포 방향
    else:
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



def draw_river_ground(stage=1):
    glDisable(GL_CULL_FACE)
    glColor3f(*lerp_color(SHALLOW_WATER, DEEP_WATER, 0.5))
    
    step = 2.0
    z = 0.0
    while z < RIVER_LENGTH:
        z_next = min(z + step, RIVER_LENGTH)
        
        cx = get_river_center(z, stage)
        cx_next = get_river_center(z_next, stage)
        w = get_river_width(z, stage)
        w_next = get_river_width(z_next, stage)
        
        xL = cx - w/2
        xR = cx + w/2
        xL_next = cx_next - w_next/2
        xR_next = cx_next + w_next/2
        
        glBegin(GL_QUADS)
        glVertex3f(xL, 0, z)
        glVertex3f(xR, 0, z)
        glVertex3f(xR_next, 0, z_next)
        glVertex3f(xL_next, 0, z_next)
        glEnd()
        
        z = z_next

    for i, ln in enumerate(LANES):
        y = WATER_EPS * (i + 1)
        c = depth_to_color(ln.depth, MIN_DEPTH, MAX_DEPTH)
        glColor3f(*c)
        
        lz = ln.z0
        while lz < ln.z1:
            lz_next = min(lz + step, ln.z1)
            
            cx = get_river_center(lz, stage)
            cx_next = get_river_center(lz_next, stage)
            w = get_river_width(lz, stage)
            w_next = get_river_width(lz_next, stage)
            
            xL = cx - w/2
            xR = cx + w/2
            xL_next = cx_next - w_next/2
            xR_next = cx_next + w_next/2
            
            glBegin(GL_QUADS)
            glVertex3f(xL, y, lz)
            glVertex3f(xR, y, lz)
            glVertex3f(xR_next, y, lz_next)
            glVertex3f(xL_next, y, lz_next)
            glEnd()
            
            lz = lz_next
            
    glEnable(GL_CULL_FACE)

def draw_water_flow(game_time, stage=1):
    """
    각 레인에 물 흐름을 시각화하는 애니메이션 라인을 그린다.
    흐르는 방향과 속도에 따라 움직이는 선으로 표현.
    """
    import math
    
    glDisable(GL_CULL_FACE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    for i, ln in enumerate(LANES):
        flow_vx = river_flow_vx((ln.z0 + ln.z1) / 2)
        flow_dir = 1 if flow_vx > 0 else -1
        flow_speed = abs(flow_vx)
        
        y = WATER_EPS * (i + 1) + 0.02
        
        num_lines = 8
        line_spacing = (ln.z1 - ln.z0) / num_lines
        
        for j in range(num_lines):
            anim_offset = (game_time * flow_speed * 3.0 * flow_dir) % (RIVER_WIDTH * 0.8)
            z_pos = ln.z0 + j * line_spacing + line_spacing / 2
            
            # 현재 z 위치에서의 강 중심과 폭
            cx = get_river_center(z_pos, stage)
            w = get_river_width(z_pos, stage)
            xL = cx - w/2
            xR = cx + w/2
            
            for k in range(5):
                base_x = xL + (xR - xL) * (k + 0.5) / 5
                x_start = base_x + anim_offset - RIVER_WIDTH * 0.4
                
                while x_start < xL: x_start += RIVER_WIDTH * 0.8
                while x_start > xR: x_start -= RIVER_WIDTH * 0.8
                
                line_len = 2.0 + flow_speed * 0.5
                x_end = x_start + line_len * flow_dir
                
                if x_end < xL: x_end = xL
                if x_end > xR: x_end = xR
                
                dist_from_center = abs((x_start + x_end) / 2 - cx)
                alpha = 0.3 - dist_from_center / RIVER_WIDTH * 0.2
                alpha = max(0.1, min(0.4, alpha))
                
                glColor4f(0, 0, 0, alpha)
                glLineWidth(1.5)
                glBegin(GL_LINES)
                glVertex3f(x_start, y, z_pos)
                glVertex3f(x_end, y, z_pos)
                glEnd()
                
                if abs(x_end - x_start) > 0.5:
                    arrow_size = 0.3
                    glBegin(GL_TRIANGLES)
                    glVertex3f(x_end, y, z_pos)
                    glVertex3f(x_end - arrow_size * flow_dir, y, z_pos + arrow_size * 0.5)
                    glVertex3f(x_end - arrow_size * flow_dir, y, z_pos - arrow_size * 0.5)
                    glEnd()
    
    glDisable(GL_BLEND)
    glEnable(GL_CULL_FACE)
    glLineWidth(1)

def draw_banks(stage=1):
    if stage < 2:
        glPushMatrix()
        glTranslatef(-RIVER_WIDTH / 2 - 0.5, 1.0, RIVER_LENGTH / 2)
        draw_box(0.5, 1.0, RIVER_LENGTH / 2, BANK_COLOR)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(+RIVER_WIDTH / 2 + 0.5, 1.0, RIVER_LENGTH / 2)
        draw_box(0.5, 1.0, RIVER_LENGTH / 2, BANK_COLOR)
        glPopMatrix()
        return

    # Stage 2: Curved banks (Grass)
    step = 2.0
    z = 0.0
    
    # Bank color
    if stage == 3:
        glColor3f(*OBSIDIAN_COLOR)
    else:
        glColor3f(0.15, 0.55, 0.25) # Grass
    
    while z < RIVER_LENGTH:
        z_next = min(z + step, RIVER_LENGTH)
        
        cx = get_river_center(z, stage)
        cx_next = get_river_center(z_next, stage)
        w = get_river_width(z, stage)
        w_next = get_river_width(z_next, stage)
        
        # Left Bank
        xL_in = cx - w/2
        xL_out = xL_in - 30.0
        xL_in_next = cx_next - w_next/2
        xL_out_next = xL_in_next - 30.0
        
        glBegin(GL_QUADS)
        glVertex3f(xL_out, 0, z)
        glVertex3f(xL_in, 0, z)
        glVertex3f(xL_in_next, 0, z_next)
        glVertex3f(xL_out_next, 0, z_next)
        glEnd()
        
        # Right Bank
        xR_in = cx + w/2
        xR_out = xR_in + 30.0
        xR_in_next = cx_next + w_next/2
        xR_out_next = xR_in_next + 30.0
        
        glBegin(GL_QUADS)
        glVertex3f(xR_in, 0, z)
        glVertex3f(xR_out, 0, z)
        glVertex3f(xR_out_next, 0, z_next)
        glVertex3f(xR_in_next, 0, z_next)
        glEnd()
        
        z = z_next

def draw_trees(trees):
    if not trees:
        return
        
    for x, y, z in trees:
        glPushMatrix()
        glTranslatef(x, y, z)
        
        # Trunk
        draw_cylinder(0.3, 1.5, (0.4, 0.3, 0.2)) # Brown
        
        # Leaves (Low poly style)
        glPushMatrix()
        glTranslatef(0, 1.5, 0)
        draw_box(1.2, 2.0, 1.2, (0.1, 0.6, 0.2))
        glTranslatef(0, 1.5, 0)
        draw_box(0.8, 1.5, 0.8, (0.15, 0.7, 0.25))
        glPopMatrix()
        
        glPopMatrix()

def draw_island(stage=1):
    if stage < 2:
        return

    # Island geometry
    z_center = RIVER_LENGTH * 0.5
    z_start = z_center - ISLAND_LENGTH / 2
    z_end = z_center + ISLAND_LENGTH / 2
    
    step = 2.0
    z = z_start
    
    while z < z_end:
        z_next = min(z + step, z_end)
        
        # Island width is constant ISLAND_WIDTH
        # Center follows river center
        cx = get_river_center(z, stage)
        cx_next = get_river_center(z_next, stage)
        
        w = ISLAND_WIDTH
        
        xL = cx - w/2
        xR = cx + w/2
        xL_next = cx_next - w/2
        xR_next = cx_next + w/2
        
        # Top surface (Grass)
        glColor3f(0.15, 0.55, 0.25)
        glBegin(GL_QUADS)
        glVertex3f(xL, 0.3, z) # Slightly elevated
        glVertex3f(xR, 0.3, z)
        glVertex3f(xR_next, 0.3, z_next)
        glVertex3f(xL_next, 0.3, z_next)
        glEnd()
        
        # Side walls (Dirt)
        glColor3f(0.4, 0.3, 0.2)
        glBegin(GL_QUADS)
        # Left side
        glVertex3f(xL, 0, z)
        glVertex3f(xL, 0.3, z)
        glVertex3f(xL_next, 0.3, z_next)
        glVertex3f(xL_next, 0, z_next)
        # Right side
        glVertex3f(xR, 0, z)
        glVertex3f(xR, 0.3, z)
        glVertex3f(xR_next, 0.3, z_next)
        glVertex3f(xR_next, 0, z_next)
        glEnd()
        
        z = z_next

        z = z_next

def draw_lava_river(stage=3, game_time=0.0):
    """
    Stage 3: 용암 강 렌더링 (Animated & Bright)
    """
    step = 5.0
    z = 0.0
    
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_CULL_FACE) # Ensure lava is visible from top
    
    # 1. Base Magma (Bright Orange/Yellow Flow)
    glBegin(GL_TRIANGLE_STRIP)
    while z <= RIVER_LENGTH:
        z_next = z + step
        
        cx = get_river_center(z, stage)
        cx_next = get_river_center(z_next, stage)
        w = RIVER_WIDTH
        
        # Flow animation
        flow_offset = math.sin(z * 0.05 - game_time * 2.0) * 2.0
        
        # Color pulsing
        pulse = (math.sin(z * 0.1 + game_time * 3.0) + 1.0) * 0.5 # 0~1
        
        # Bright center (Yellow/Orange)
        r = 1.0
        g = 0.3 + 0.4 * pulse # 0.3 ~ 0.7 (Red to Yellow)
        b = 0.0
        
        glColor3f(r, g, b)
        glVertex3f(cx - w/2 + flow_offset, 0, z)
        glVertex3f(cx + w/2 + flow_offset, 0, z)
        
        z = z_next
    glEnd()
    
    # 2. Dark Crust / Edges (Dark Red/Black)
    # Render strips on sides to simulate cooling rock
    glBegin(GL_TRIANGLE_STRIP)
    z = 0.0
    while z <= RIVER_LENGTH:
        z_next = z + step
        cx = get_river_center(z, stage)
        w = RIVER_WIDTH
        
        # Left Edge (Dark)
        glColor3f(0.2, 0.05, 0.05)
        glVertex3f(cx - w/2, 0.02, z)
        glColor3f(0.8, 0.2, 0.0) # Fade to lava
        glVertex3f(cx - w/2 + 5.0, 0.02, z)
        
        z = z_next
    glEnd()
    
    glBegin(GL_TRIANGLE_STRIP)
    z = 0.0
    while z <= RIVER_LENGTH:
        z_next = z + step
        cx = get_river_center(z, stage)
        w = RIVER_WIDTH
        
        # Right Edge (Dark)
        glColor3f(0.8, 0.2, 0.0) # Fade from lava
        glVertex3f(cx + w/2 - 5.0, 0.02, z)
        glColor3f(0.2, 0.05, 0.05)
        glVertex3f(cx + w/2, 0.02, z)
        
        z = z_next
    glEnd()
    
    # 3. Floating Debris / Hot Spots (Random glowing patches)
    # Simplified as a central bright stream for now
    glBegin(GL_TRIANGLE_STRIP)
    z = 0.0
    while z <= RIVER_LENGTH:
        z_next = z + step
        cx = get_river_center(z, stage)
        
        # Wobbly center stream
        off = math.sin(z * 0.1 - game_time * 4.0) * 3.0
        
        glColor3f(1.0, 0.8, 0.2) # Very bright yellow
        glVertex3f(cx + off - 2.0, 0.05, z)
        glVertex3f(cx + off + 2.0, 0.05, z)
        
        z = z_next
    glEnd()
    
    glEnable(GL_CULL_FACE)

def draw_monsters(monsters, game_time):
    """
    Stage 3: 몬스터 렌더링
    """
    for m in monsters:
        pos = m["pos"]
        # 애니메이션: 위아래로 둥둥 떠다님
        bob = math.sin(game_time * 3.0 + m["anim_offset"]) * 0.2
        
        glPushMatrix()
        glTranslatef(pos[0], pos[1] + 0.5 + bob, pos[2])
        
        # 몬스터 몸체 (검은색 구체/박스)
        draw_box(0.8, 0.8, 0.8, (0.1, 0.1, 0.1))
        
        # 눈 (빨간색)
        glPushMatrix()
        glTranslatef(0.4, 0.2, -0.4)
        draw_box(0.15, 0.15, 0.1, (1.0, 0.0, 0.0))
        glPopMatrix()
        
        glPushMatrix()
        glTranslatef(-0.4, 0.2, -0.4)
        draw_box(0.15, 0.15, 0.1, (1.0, 0.0, 0.0))
        glPopMatrix()
        
        glPopMatrix()

def draw_waterfall(dock_z, anim_time=0.0):
    """
    도크 앞에 폭포를 그린다.
    anim_time: 물 흐름 애니메이션용 시간값
    """
    waterfall_z = dock_z - 8.0  # 도크 앞쪽에 위치
    waterfall_height = 25.0      # 폭포 높이
    waterfall_width = RIVER_WIDTH * 0.9
    
    # 폭포 절벽 (양쪽)
    cliff_color = (0.35, 0.30, 0.25)
    glPushMatrix()
    glTranslatef(-RIVER_WIDTH / 2 - 2, -waterfall_height / 2, waterfall_z)
    draw_box(3.0, waterfall_height / 2, 4.0, cliff_color)
    glPopMatrix()
    
    glPushMatrix()
    glTranslatef(+RIVER_WIDTH / 2 + 2, -waterfall_height / 2, waterfall_z)
    draw_box(3.0, waterfall_height / 2, 4.0, cliff_color)
    glPopMatrix()
    
    # 폭포 물 (여러 층으로 애니메이션 효과)
    glDisable(GL_CULL_FACE)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    for layer in range(5):
        # 각 층마다 약간 다른 위치와 색상
        offset = (anim_time * 3.0 + layer * 5.0) % 25.0
        alpha = 0.4 + layer * 0.1
        
        # 물 색상 (파란색 계열, 층마다 약간 다름)
        water_r = 0.3 + layer * 0.05
        water_g = 0.5 + layer * 0.08
        water_b = 0.85 + layer * 0.03
        
        glColor4f(water_r, water_g, water_b, alpha)
        
        y_start = 0.0 - offset
        y_end = -waterfall_height + 5.0 - offset
        
        # 폭포 물줄기 (사각형으로 표현)
        glBegin(GL_QUADS)
        glVertex3f(-waterfall_width / 2 + layer * 2, y_start, waterfall_z - layer * 0.3)
        glVertex3f(+waterfall_width / 2 - layer * 2, y_start, waterfall_z - layer * 0.3)
        glVertex3f(+waterfall_width / 2 - layer * 2, y_end, waterfall_z - layer * 0.3 - 3.0)
        glVertex3f(-waterfall_width / 2 + layer * 2, y_end, waterfall_z - layer * 0.3 - 3.0)
        glEnd()
    
    # 물보라/안개 효과 (폭포 아래)
    mist_color = (0.7, 0.8, 0.95, 0.3)
    glColor4f(*mist_color)
    for i in range(3):
        mist_y = -waterfall_height + 3.0 + i * 2.0
        mist_size = 8.0 + i * 3.0
        glBegin(GL_QUADS)
        glVertex3f(-mist_size, mist_y, waterfall_z - 5.0 - i)
        glVertex3f(+mist_size, mist_y, waterfall_z - 5.0 - i)
        glVertex3f(+mist_size, mist_y - 3.0, waterfall_z - 8.0 - i)
        glVertex3f(-mist_size, mist_y - 3.0, waterfall_z - 8.0 - i)
        glEnd()
    
    glDisable(GL_BLEND)
    glEnable(GL_CULL_FACE)
    
    # 하류 물 (폭포 아래)
    glColor3f(0.2, 0.45, 0.75)
    lower_y = -waterfall_height
    glBegin(GL_QUADS)
    glVertex3f(-RIVER_WIDTH / 2, lower_y, waterfall_z - 5.0)
    glVertex3f(+RIVER_WIDTH / 2, lower_y, waterfall_z - 5.0)
    glVertex3f(+RIVER_WIDTH / 2, lower_y, waterfall_z - 50.0)
    glVertex3f(-RIVER_WIDTH / 2, lower_y, waterfall_z - 50.0)
    glEnd()

def draw_distance_markers():
    """
    강 양옆 제방에 100m 간격으로 거리 푯말을 그린다.
    시작점(z=RIVER_LENGTH)에서 도크(z=0) 방향으로 누적 거리 표시.
    푯말에 숫자 느낌의 색상 패널을 직접 렌더링.
    """
    marker_color = (0.92, 0.88, 0.78)  # 밝은 나무색 푯말
    post_color = (0.30, 0.20, 0.10)    # 어두운 기둥색
    text_panel_color = (0.15, 0.12, 0.08)  # 어두운 텍스트 패널 색상
    
    marker_positions = []  # (world_x, world_y, world_z, distance_m) 저장
    
    # 푯말 크기 파라미터 (매우 크게!)
    post_height = 5.0       # 기둥 높이
    post_thickness = 0.4    # 기둥 두께
    sign_width = 6.0        # 표지판 가로
    sign_height = 3.0       # 표지판 세로
    sign_thickness = 0.2    # 표지판 두께
    sign_y = post_height + sign_height / 2 + 0.2  # 표지판 중심 Y좌표
    
    for marker_z in MARKERS:
        # 월드 z 좌표: 시작점에서 marker_z 미터 전진한 위치
        world_z = cfg.RIVER_LENGTH - marker_z
        
        # 거리에 따른 색상 (100m 단위로 색상 변화)
        hue_shift = (marker_z // 100) * 0.15
        panel_r = min(1.0, 0.2 + hue_shift * 0.3)
        panel_g = min(1.0, 0.15 + hue_shift * 0.1)
        panel_b = max(0.05, 0.1 - hue_shift * 0.02)
        text_panel_color = (panel_r, panel_g, panel_b)
        
        # 왼쪽 제방에 푯말
        left_x = -RIVER_WIDTH / 2 - 5.0
        glPushMatrix()
        glTranslatef(left_x, 0.0, world_z)
        # 기둥
        glPushMatrix()
        glTranslatef(0, post_height / 2, 0)
        draw_box(post_thickness, post_height / 2, post_thickness, post_color)
        glPopMatrix()
        # 표지판 배경
        glPushMatrix()
        glTranslatef(0, sign_y, 0)
        draw_box(sign_width / 2, sign_height / 2, sign_thickness, marker_color)
        glPopMatrix()
        # 숫자 패널 (표지판 위에 올라간 느낌)
        glPushMatrix()
        glTranslatef(0, sign_y, sign_thickness + 0.02)
        draw_box(sign_width / 2 - 0.5, sign_height / 2 - 0.4, 0.05, text_panel_color)
        glPopMatrix()
        glPopMatrix()
        
        # 오른쪽 제방에 푯말
        right_x = +RIVER_WIDTH / 2 + 5.0
        glPushMatrix()
        glTranslatef(right_x, 0.0, world_z)
        # 기둥
        glPushMatrix()
        glTranslatef(0, post_height / 2, 0)
        draw_box(post_thickness, post_height / 2, post_thickness, post_color)
        glPopMatrix()
        # 표지판 배경
        glPushMatrix()
        glTranslatef(0, sign_y, 0)
        draw_box(sign_width / 2, sign_height / 2, sign_thickness, marker_color)
        glPopMatrix()
        # 숫자 패널
        glPushMatrix()
        glTranslatef(0, sign_y, -sign_thickness - 0.02)
        draw_box(sign_width / 2 - 0.5, sign_height / 2 - 0.4, 0.05, text_panel_color)
        glPopMatrix()
        glPopMatrix()
        
        # 텍스트 렌더링을 위해 표지판 중심 위치 저장 (가까운 것만 표시용)
        marker_positions.append((left_x, sign_y, world_z, marker_z))
        marker_positions.append((right_x, sign_y, world_z, marker_z))
    
    return marker_positions

# ---------- 보트 렌더링(수정) ----------
# ---------- 홈 화면 ----------
def draw_home_screen(gltext: GLText, state):
    begin_ortho()
    
    # 배경 (약간의 그라데이션 느낌을 위해 여러 겹 칠하기 가능하지만, 일단 단색 유지)
    quad2(0, 0, WIDTH, HEIGHT, (0.08, 0.10, 0.13, 1.0))
    
    # 타이틀 (중앙 정렬, 큰 폰트 텍스처 사용 권장되지만 GLText로 최대한 크게)
    # GLText는 폰트 크기 변경이 동적으로 어려우므로, 위치를 잘 잡아야 함.
    # 텍스처 텍스트를 사용하여 크게 그림
    title_text = "INFINITE RIVER"
    tex_id, tw, th, aspect = get_text_texture(title_text, font_size=80, color=(100, 200, 255, 255))
    
    # 타이틀 위치 (화면 중앙 상단)
    title_w = 600
    title_h = title_w / aspect
    title_x = WIDTH // 2
    title_y = 120
    
    glPushMatrix()
    glTranslatef(title_x, title_y, 0)
    glScalef(1, -1, 1) # Ortho is Y-down, so flip Y to make text upright
    draw_textured_quad_3d(tex_id, title_w, title_h)
    glPopMatrix()
    
    # 스테이지 선택
    stages = [1, 2, 3]
    btn_w, btn_h = 220, 60  # 버튼 크기 키움
    gap = 30
    total_w = len(stages) * btn_w + (len(stages) - 1) * gap
    start_x = (WIDTH - total_w) // 2
    y = 300
    
    for i, s in enumerate(stages):
        x = start_x + i * (btn_w + gap)
        
        # 잠금 확인
        locked = False
        if s == 2 and 1 not in state["cleared_stages"]: locked = True
        if s == 3 and 2 not in state["cleared_stages"]: locked = True
        
        # 버튼 그리기
        if not locked:
            # Active Stage Color (Greenish Blue)
            color = (0.2, 0.6, 0.5, 1.0)
            hover_color = (0.3, 0.7, 0.6, 1.0) # 마우스 오버 효과는 복잡하니 생략
        else:
            # Locked Color (Dark Gray)
            color = (0.25, 0.25, 0.25, 1.0)
            
        quad2(x, y, btn_w, btn_h, color)
        
        # 텍스트 (중앙 정렬)
        label = f"STAGE {s}"
        if locked: label = "LOCKED"
        
        # 텍스트 너비 대략 계산 (GLText는 get_width가 없으므로 추정)
        # 폰트 크기가 작으므로 적당히 오프셋
        text_offset = len(label) * 5
        gltext.draw(label, x + btn_w//2 - text_offset, y + btn_h//2 - 8, (255, 255, 255, 255))
        
        state[f"btn_stage_{s}"] = (x, y, btn_w, btn_h)

    # 보트 스킨 선택
    y_boat = 450
    # 섹션 타이틀
    tex_id, tw, th, aspect = get_text_texture("SELECT BOAT", font_size=40, color=(200, 200, 200, 255))
    glPushMatrix()
    glTranslatef(WIDTH//2, y_boat, 0)
    glScalef(1, -1, 1) # Ortho is Y-down
    draw_textured_quad_3d(tex_id, 300, 300/aspect)
    glPopMatrix()
    
    # Red Box
    bx = WIDTH//2 - 180
    by = y_boat + 50
    sel = state["selected_boat"] == "RED_BOX"
    col = (0.8, 0.3, 0.3, 1.0) if sel else (0.4, 0.2, 0.2, 1.0)
    quad2(bx, by, 160, 60, col)
    gltext.draw("Red Box", bx + 50, by + 20, (255, 255, 255, 255))
    state["btn_boat_red"] = (bx, by, 160, 60)
    
    # New Boat (Unlockable)
    bx2 = WIDTH//2 + 20
    locked_boat = not state["unlocked_boat"]
    sel2 = state["selected_boat"] == "NEW_BOAT"
    col2 = (0.3, 0.3, 0.8, 1.0) if sel2 else (0.2, 0.2, 0.4, 1.0)
    if locked_boat: col2 = (0.25, 0.25, 0.25, 1.0)
    
    quad2(bx2, by, 160, 60, col2)
    label2 = "New Boat" if not locked_boat else "Locked"
    gltext.draw(label2, bx2 + 45, by + 20, (255, 255, 255, 255))
    state["btn_boat_new"] = (bx2, by, 160, 60)
    
    if locked_boat:
        gltext.draw("Clear Stage 3 to unlock!", WIDTH//2 - 90, by + 80, (255, 100, 100, 255))

    # Cheat Code Input
    cheat_y = HEIGHT - 50
    gltext.draw("Cheat Code:", 30, cheat_y + 10, (150, 150, 150, 255))
    
    # Input Box
    box_x = 140
    box_w = 250
    quad2(box_x, cheat_y, box_w, 40, (0.15, 0.15, 0.15, 1.0))
    
    buf = state.get("cheat_buffer", "")
    if buf:
        gltext.draw(buf, box_x + 10, cheat_y + 10, (255, 255, 0, 255))
    else:
        gltext.draw("Type here...", box_x + 10, cheat_y + 10, (80, 80, 80, 255))

    end_ortho()

INTRO_TEXTS = [
    "당신은 배를 타고 한강을 제 시간안에 건너야 합니다! 제한 시간 안에 화면 상단의 초록 Finish 구역에 있는 선착장(Dock)에 도달해야 합니다. 시간 초과나 화면 밖 이탈은 실패입니다.",
    "오른쪽 패널의 원형 패드를 드래그하여 보트의 출발 각도와 속도를 설정합니다. 파란색 화살표가 방향/세기를 나타냅니다. 각도는 ±90°까지, 속도는 0~35 m/s 범위입니다.",
    "강은 5개의 레인으로 나뉘며 유속 방향이 교차합니다. 중앙일수록 깊어 빨라집니다. 코인을 먹으면 +5초, 장애물에 부딪히면 반사/감속됩니다.",
    "성공 조건: 선착장 영역 안에 정확히 들어가야 합니다.",
]

def draw_intro_overlay(gltext: GLText, state):
    """게임 설명 인트로 오버레이"""
    begin_ortho()
    
    # 반투명 배경
    quad2(0, 0, WIDTH, HEIGHT, (0, 0, 0, 0.85))
    
    # 박스
    box_w, box_h = 900, 400
    bx = (WIDTH - box_w) // 2
    by = (HEIGHT - box_h) // 2
    quad2(bx, by, box_w, box_h, (0.95, 0.95, 0.95, 1.0)) # Off-white bg
    
    # 타이틀 (텍스처 텍스트 사용)
    tex_id, tw, th, aspect = get_text_texture("게임 설명", font_size=50, color=(60, 120, 220, 255))
    glPushMatrix()
    glTranslatef(WIDTH//2, by + 50, 0)
    glScalef(1, -1, 1) # Ortho Y-down flip
    draw_textured_quad_3d(tex_id, 200, 200/aspect)
    glPopMatrix()
    
    # 텍스트 내용 (줄바꿈 처리 개선)
    idx = state.get("intro_index", 0)
    text = INTRO_TEXTS[idx]
    
    # 한글 폰트 크기가 작으므로 한 줄에 들어갈 글자 수 넉넉하게
    max_chars = 55
    lines = []
    current_line = ""
    for word in text.split(' '):
        if len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            if current_line: current_line += " "
            current_line += word
    if current_line: lines.append(current_line)
    
    y = by + 120
    for line in lines:
        # 좌측 정렬 (박스 내부 마진)
        x = bx + 50
        gltext.draw(line, x, y, (40, 40, 40, 255))
        y += 35
        
    # Next 버튼
    btn_w, btn_h = 150, 50
    btn_x = WIDTH//2 - btn_w//2
    btn_y = by + box_h - 80
    
    # Button Hover Effect (Simple)
    mx, my = pygame.mouse.get_pos()
    hover = btn_x <= mx <= btn_x + btn_w and btn_y <= my <= btn_y + btn_h
    col = (0.3, 0.8, 0.5, 1.0) if not hover else (0.4, 0.9, 0.6, 1.0)
    
    quad2(btn_x, btn_y, btn_w, btn_h, col)
    gltext.draw("Next", btn_x + 55, btn_y + 15, (255, 255, 255, 255))
    
    # 버튼 영역 저장
    state["btn_intro_next"] = (btn_x, btn_y, btn_w, btn_h)
    
    end_ortho()

def draw_pause_menu(gltext: GLText, state):
    """일시정지 메뉴"""
    begin_ortho()
    
    # Darken background
    quad2(0, 0, WIDTH, HEIGHT, (0, 0, 0, 0.6))
    
    # Menu Box
    box_w, box_h = 300, 220
    bx = (WIDTH - box_w) // 2
    by = (HEIGHT - box_h) // 2
    quad2(bx, by, box_w, box_h, (0.15, 0.15, 0.18, 1.0))
    
    # Title
    gltext.draw("PAUSED", WIDTH//2 - 40, by + 30, (255, 255, 255, 255))
    
    # Resume Button
    btn_w, btn_h = 200, 50
    btn_x = (WIDTH - btn_w) // 2
    btn_y1 = by + 80
    quad2(btn_x, btn_y1, btn_w, btn_h, (0.3, 0.6, 0.3, 1.0))
    gltext.draw("Resume", btn_x + 60, btn_y1 + 15, (255, 255, 255, 255))
    state["btn_pause_resume"] = (btn_x, btn_y1, btn_w, btn_h)
    
    # Home Button
    btn_y2 = by + 150
    quad2(btn_x, btn_y2, btn_w, btn_h, (0.6, 0.3, 0.3, 1.0))
    gltext.draw("Go to Home", btn_x + 50, btn_y2 + 15, (255, 255, 255, 255))
    state["btn_pause_home"] = (btn_x, btn_y2, btn_w, btn_h)
    
    end_ortho()

def draw_manning_tuning_overlay(gltext: GLText, state):
    """
    매닝 공식 튜닝 콘솔 오버레이
    각 레인의 조도계수, 경사, 유향을 조절
    """
    begin_ortho()
    
    # 배경
    panel_w, panel_h = 600, 400
    panel_x, panel_y = (WIDTH - panel_w) // 2, (HEIGHT - panel_h) // 2
    quad2(panel_x, panel_y, panel_w, panel_h, (30/255, 35/255, 40/255, 0.95))
    
    # 제목
    gltext.draw("RIVER TUNING CONSOLE", panel_x + 20, panel_y + 20, (255, 255, 255, 255))
    gltext.draw("Adjust parameters for each lane before starting", panel_x + 20, panel_y + 45, (180, 180, 180, 255))
    
    # 레인 목록
    from river3d.lanes import LANE_PROFILES, LANE_COUNT
    from river3d.hydraulics import surface_velocity
    
    start_y = panel_y + 80
    row_h = 40
     
    # 헤더
    gltext.draw("Lane", panel_x + 20, start_y, (150, 200, 255, 255))
    gltext.draw("Roughness", panel_x + 80, start_y, (150, 200, 255, 255))
    gltext.draw("Slope", panel_x + 280, start_y, (150, 200, 255, 255))
    gltext.draw("Dir", panel_x + 380, start_y, (150, 200, 255, 255))
    gltext.draw("Velocity", panel_x + 450, start_y, (100, 255, 100, 255))
    
    sel_lane = state.get("tuning_selected_lane", 0)
    sel_param = state.get("tuning_selected_param", 0)
    
    for i in range(LANE_COUNT):
        # 역순으로 표시 (Lane 1이 위쪽)
        lane_idx = LANE_COUNT - 1 - i
        
        p = LANE_PROFILES[i]
        y = start_y + 30 + i * row_h
        
        # 선택된 행 하이라이트
        if i == sel_lane:
            quad2(panel_x + 10, y - 5, panel_w - 20, row_h - 2, (60/255, 70/255, 80/255, 0.8))
        
        # Lane 번호 (역순 표시)
        lane_num = LANE_COUNT - i
        gltext.draw(f"Lane {lane_num}", panel_x + 20, y + 5, (255, 255, 255, 255))
        
        # Roughness
        r_color = (255, 255, 0, 255) if i == sel_lane and sel_param == 0 else (200, 200, 200, 255)
        gltext.draw(f"{p['roughness']}", panel_x + 80, y + 5, r_color)
        
        # Slope
        slope = p.get("slope", cfg.DEFAULT_SLOPE)
        s_color = (255, 255, 0, 255) if i == sel_lane and sel_param == 1 else (200, 200, 200, 255)
        gltext.draw(f"{slope:.4f}", panel_x + 280, y + 5, s_color)
        
        # Direction
        d_str = "L" if p["dir"] == -1 else "R"
        d_color = (255, 255, 0, 255) if i == sel_lane and sel_param == 2 else (200, 200, 200, 255)
        gltext.draw(d_str, panel_x + 390, y + 5, d_color)
        
        # Calculated Velocity
        # Manning formula calculation
        Vm, Vs, _ = surface_velocity(p["depth"], p["section"], p["b"], p["z"], p["roughness"], slope)
        v_str = f"{Vs:.2f} m/s"
        gltext.draw(v_str, panel_x + 450, y + 5, (100, 255, 100, 255))

    # 조작 안내
    guide_y = panel_y + panel_h - 40
    gltext.draw("UP/DOWN: Select Lane  |  LEFT/RIGHT: Select Param", panel_x + 20, guide_y - 20, (150, 150, 150, 255))
    gltext.draw("SPACE: Change Value   |  ENTER: Start Stage", panel_x + 20, guide_y, (255, 200, 100, 255))
    
    end_ortho()

def handle_tuning_input(ev, state):
    """튜닝 콘솔 입력 처리"""
    from river3d.lanes import LANE_PROFILES, LANE_COUNT, build_lanes_from_manning
    
    if ev.type == pygame.KEYDOWN:
        if ev.key == pygame.K_RETURN:
            # 설정 완료 및 스테이지 시작
            state["tuning_mode"] = False
            # 변경된 설정으로 유속 재계산
            globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()
            return
            
        elif ev.key == pygame.K_UP:
            state["tuning_selected_lane"] = (state["tuning_selected_lane"] - 1) % LANE_COUNT
        elif ev.key == pygame.K_DOWN:
            state["tuning_selected_lane"] = (state["tuning_selected_lane"] + 1) % LANE_COUNT
        elif ev.key == pygame.K_LEFT:
            state["tuning_selected_param"] = (state["tuning_selected_param"] - 1) % 3
        elif ev.key == pygame.K_RIGHT:
            state["tuning_selected_param"] = (state["tuning_selected_param"] + 1) % 3
            
        elif ev.key == pygame.K_SPACE:
            lane = state["tuning_selected_lane"]
            param = state["tuning_selected_param"]
            p = LANE_PROFILES[lane]
            
            if param == 0: # Roughness
                # 조도계수 순환
                opts = ["매우 부정확_잡초", "흙_직선", "흙_잡초", "자갈_바닥", "콘크리트_매끈"]
                try:
                    curr_idx = opts.index(p["roughness"])
                except ValueError:
                    curr_idx = 0
                p["roughness"] = opts[(curr_idx + 1) % len(opts)]
                
            elif param == 1: # Slope
                # 경사 증가 (순환)
                curr = p.get("slope", cfg.DEFAULT_SLOPE)
                curr += 0.0005
                if curr > 0.005: curr = 0.0005
                p["slope"] = curr
                
            elif param == 2: # Direction
                p["dir"] *= -1

def draw_boat_mesh(boat: Boat, skin="RED_BOX"):
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
        if skin == "NEW_BOAT":
            # Blue sleek boat (New Skin)
            draw_box(BOAT_WID / 2.0, BOAT_HGT / 2.0, BOAT_LEN / 2.0, (0.2, 0.4, 0.9))
            # Add a stripe
            glPushMatrix()
            glTranslatef(0, 0.1, 0)
            draw_box(BOAT_WID / 2.1, BOAT_HGT / 4.0, BOAT_LEN / 1.8, (0.9, 0.9, 0.9))
            glPopMatrix()
        else:
            # Red Box (Default)
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
def reset_round(state, reroll_lanes=True, next_stage=False):
    global lane_tune_timer, current_lane_idx
    
    # 스테이지 관리
    if "stage" not in state:
        state["stage"] = 1
    if next_stage:
        state["stage"] += 1
    
    state["started"] = False
    state["show_launch"] = True            # 런치 오버레이 표시
    state["launch_vec_screen"] = (0.0, -LAUNCH_RADIUS * 0.6)  # 기본 위쪽
    
    # 시간 제한 설정 (Stage 3는 15초 추가)
    if state["stage"] == 3:
        state["time_left"] = cfg.SECONDS_LIMIT + 15.0
    else:
        state["time_left"] = cfg.SECONDS_LIMIT
        
    state["win"] = False
    state["lose"] = False
    
    # 폭포 전환 상태
    state["waterfall_transition"] = False
    state["waterfall_timer"] = 0.0
    state["boat_fall_y"] = 0.0

    # 보트 초기화: 위치는 기존대로, 속도는 0으로(정지)
    state["boat"] = Boat(0.0, cfg.RIVER_LENGTH - 6.0)
    b = state["boat"]
    # 정지 상태로 강제
    try:
        b.vel.x = 0.0
        b.vel.y = 0.0
    except Exception:
        pass

    if reroll_lanes:
        randomize_lane_depths()
        globals()["LANES"], globals()["LANE_INFO"] = build_lanes_from_manning()

    # 나무 생성 (Stage 2 이상)
    state["trees"] = generate_trees(state["stage"])
    
    # 몬스터 생성 (Stage 3)
    state["monsters"] = generate_monsters(state["stage"])

    # Stage 2 이상이면 튜닝 모드 활성화
    if state["stage"] >= 2:
        state["tuning_mode"] = True
        state["tuning_selected_lane"] = 0
        state["tuning_selected_param"] = 0
    else:
        state["tuning_mode"] = False

    for i in range(len(FLOW_SCALE)):
        FLOW_SCALE[i] = 1.0

    lane_tune_timer = 0.0
    current_lane_idx = get_lane_index(state["boat"].pos.y)
    state["obstacles"], state["coins"], state["dock"] = build_scene()

    # distance / score
    state["start_z"] = state["boat"].pos.y
    state["best_z"] = state["boat"].pos.y
    if not next_stage:
        state["score"] = 0
        state["total_score"] = 0
    else:
        # 다음 스테이지로 넘어갈 때 점수 누적
        state["total_score"] = state.get("total_score", 0) + state.get("score", 0)
        state["score"] = 0

def main():
    global PAUSED, TOAST_TIMER, TOAST_TEXT, lane_tune_timer, current_lane_idx
    global lane_popup_timer, lane_popup_info

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
    state["scene"] = "HOME"
    state["cleared_stages"] = set()
    state["unlocked_boat"] = False
    state["selected_boat"] = "RED_BOX"
    state["cheat_buffer"] = ""
    
    # Intro State
    state["scene"] = "HOME" # Start with Home
    state["intro_index"] = 0
    
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

            # 인트로 화면 입력 처리
            if state.get("scene") == "INTRO":
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    btn = state.get("btn_intro_next")
                    if btn:
                        bx, by, bw, bh = btn
                        if bx <= mx <= bx+bw and by <= my <= by+bh:
                            # Next 클릭
                            state["intro_index"] += 1
                            if state["intro_index"] >= len(INTRO_TEXTS):
                                # 인트로 끝나면 게임 시작 (Stage 1)
                                state["scene"] = "GAME"
                                reset_round(state, reroll_lanes=True, next_stage=False)
                continue

            # 홈 화면 입력 처리
            if state.get("scene") == "HOME":
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    # 스테이지 선택
                    for s in [1, 2, 3]:
                        btn = state.get(f"btn_stage_{s}")
                        if btn:
                            bx, by, bw, bh = btn
                            if bx <= mx <= bx+bw and by <= my <= by+bh:
                                # 잠금 확인
                                if s == 2 and 1 not in state["cleared_stages"]: continue
                                if s == 3 and 2 not in state["cleared_stages"]: continue
                                
                                state["stage"] = s
                                
                                # Stage 1 선택 시 인트로 보여주기 (이미 본 적 있어도 매번 보여달라는 요청으로 해석)
                                if s == 1:
                                    state["scene"] = "INTRO"
                                    state["intro_index"] = 0
                                else:
                                    state["scene"] = "GAME"
                                    reset_round(state, reroll_lanes=True, next_stage=False)
                                break
                    
                    # 보트 선택
                    btn_red = state.get("btn_boat_red")
                    if btn_red:
                        bx, by, bw, bh = btn_red
                        if bx <= mx <= bx+bw and by <= my <= by+bh:
                            state["selected_boat"] = "RED_BOX"
                            
                    btn_new = state.get("btn_boat_new")
                    if btn_new:
                        bx, by, bw, bh = btn_new
                        if bx <= mx <= bx+bw and by <= my <= by+bh:
                            if state["unlocked_boat"]:
                                state["selected_boat"] = "NEW_BOAT"
                
                elif ev.type == pygame.KEYDOWN:
                    # 치트 코드 입력 처리
                    if ev.key == pygame.K_BACKSPACE:
                        state["cheat_buffer"] = state["cheat_buffer"][:-1]
                    else:
                        char = ev.unicode
                        if char.isalpha():
                            state["cheat_buffer"] += char.lower()
                            # 버퍼 길이 제한 (최근 20자)
                            if len(state["cheat_buffer"]) > 20:
                                state["cheat_buffer"] = state["cheat_buffer"][-20:]
                            
                            # 치트 확인: "axiom"
                            if state["cheat_buffer"].endswith("axiom"):
                                state["cleared_stages"] = {1, 2, 3}
                                state["unlocked_boat"] = True
                                show_toast("CHEAT ACTIVATED: All Unlocked!")
                                state["cheat_buffer"] = "" # 리셋
                continue

            # 튜닝 모드 입력 처리
            if state.get("tuning_mode", False):
                handle_tuning_input(ev, state)
                continue

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
            # 일시정지 메뉴 입력 처리
            if PAUSED:
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    
                    # Resume
                    btn = state.get("btn_pause_resume")
                    if btn:
                        bx, by, bw, bh = btn
                        if bx <= mx <= bx+bw and by <= my <= by+bh:
                            PAUSED = False
                            
                    # Home
                    btn = state.get("btn_pause_home")
                    if btn:
                        bx, by, bw, bh = btn
                        if bx <= mx <= bx+bw and by <= my <= by+bh:
                            PAUSED = False
                            state["scene"] = "HOME"
                            reset_round(state)
                
                # Allow ESC to unpause
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    PAUSED = False
                
                continue # Skip other game inputs

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    PAUSED = not PAUSED
                elif ev.key == pygame.K_q and PAUSED:
                    pygame.quit(); sys.exit(0)
                elif ev.key == pygame.K_r:
                    reset_round(state)
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
        
        # 레인 유속 팝업 타이머 업데이트
        if lane_popup_timer > 0:
            lane_popup_timer -= dt

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

            # 레인 변경 감지 및 유속 팝업 표시
            idx = get_lane_index(boat.pos.y)
            if idx is not None and idx != current_lane_idx:
                current_lane_idx = idx
                lane_tune_timer = LANE_TUNE_WINDOW
                
                # 현재 레인의 유속 정보 가져오기
                flow_vx = river_flow_vx(boat.pos.y)
                flow_dir = 1 if flow_vx > 0 else -1
                lane_popup_info["lane_num"] = idx
                lane_popup_info["flow_speed"] = abs(flow_vx)
                lane_popup_info["flow_dir"] = flow_dir
                lane_popup_timer = lane_popup_duration

            # 몬스터 업데이트 (Stage 3)
            if state["stage"] == 3:
                monsters = state.get("monsters", [])
                ba = boat_aabb(boat)
                for m in monsters:
                    # 몬스터 이동 (강을 따라 내려오거나 올라감)
                    # 여기서는 플레이어를 향해 천천히 다가오게 하거나, 단순히 강을 따라 흐르게 함
                    # 일단 강을 거슬러 올라오게 (더 어렵게)
                    m["pos"][2] += dt * MONSTER_SPEED * m["speed"]
                    
                    # 범위 벗어나면 리스폰? 일단은 그냥 둠
                    
                    # 충돌 체크 (단순 거리 기반)
                    mx, my, mz = m["pos"]
                    dx = boat.pos.x - mx
                    dz = boat.pos.y - mz
                    dist_sq = dx*dx + dz*dz
                    if dist_sq < (1.0 + 0.8)**2: # 보트 반지름 + 몬스터 반지름
                        # 충돌!
                        state["lose"] = True
                        show_toast("Killed by Lava Monster!")

            if lane_tune_timer > 0.0:
                lane_tune_timer -= dt
                if lane_tune_timer < 0.0:
                    lane_tune_timer = 0.0

            # 벽/섬 충돌
            wall_bounce(boat, state["stage"])

            # 경계 이탈 (안전장치)
            if abs(boat.pos.x) > cfg.RIVER_WIDTH * 0.8 or boat.pos.y < -2 or boat.pos.y > cfg.RIVER_LENGTH + 2:
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

            # 장애물 (충돌 쿨다운으로 진동 방지)
            ba = boat_aabb(boat)
            collision_cooldown = getattr(boat, 'collision_cooldown', 0)
            if collision_cooldown > 0:
                boat.collision_cooldown = collision_cooldown - dt
            else:
                for ob in obstacles:
                    if aabb_overlap(ba, ob.aabb()):
                        bounce_response(boat, ob)
                        boat.collision_cooldown = 0.3  # 0.3초간 충돌 무시
                        break

            # 도크 도착 -> 폭포 전환 시작
            if aabb_overlap(ba, dock.aabb()) and not state.get("waterfall_transition", False):
                state["win"] = True
                state["waterfall_transition"] = True
                state["waterfall_timer"] = 0.0
                state["boat_fall_y"] = 0.0

            # 시간초과
            if state["time_left"] <= 0.0 and not state["win"]:
                state["lose"] = True
        
        # 폭포 전환 애니메이션 업데이트
        if state.get("waterfall_transition", False):
            state["waterfall_timer"] += dt
            # 가속도가 있는 낙하 (더 극적인 효과)
            fall_speed = 8.0 + state["waterfall_timer"] * 12.0  # 시간에 따라 빨라짐
            state["boat_fall_y"] += dt * fall_speed
            
            # 4초 후 다음 스테이지로 이동
            # 4초 후 다음 스테이지로 이동
            if state["waterfall_timer"] > 4.0:
                # 현재 스테이지 클리어 처리
                state["cleared_stages"].add(state["stage"])
                
                # 스테이지 3 클리어 시 보트 잠금 해제
                if state["stage"] == 3:
                    state["unlocked_boat"] = True
                    show_toast("New Boat Unlocked!")
                
                # 홈 화면으로 이동
                state["scene"] = "HOME"
                state["waterfall_transition"] = False

        # -------- 렌더 --------
        # 배경색 설정
        if state.get("stage") == 3:
            # Slightly brighter dark red/purple atmosphere
            glClearColor(0.2, 0.05, 0.05, 1.0) 
        else:
            glClearColor(*cfg.SKY_COLOR, 1.0)
            
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 인트로 화면 렌더링
        if state.get("scene") == "INTRO":
            draw_intro_overlay(gltext, state)
            pygame.display.flip()
            continue

        # 홈 화면 렌더링
        if state.get("scene") == "HOME":
            draw_home_screen(gltext, state)
            pygame.display.flip()
            continue

        # 튜닝 모드이면 오버레이만 그리고 스킵
        if state.get("tuning_mode", False):
            draw_manning_tuning_overlay(gltext, state)
            pygame.display.flip()
            continue
            
        # 일시정지 메뉴 렌더링
        if PAUSED:
            draw_pause_menu(gltext, state)
            pygame.display.flip()
            continue
        
        # 폭포 전환 모드 체크
        waterfall_active = state.get("waterfall_transition", False)
        fall_offset = state.get("boat_fall_y", 0.0) if waterfall_active else 0.0
        set_camera(boat, fall_offset, waterfall_mode=waterfall_active)
        
        game_time = pygame.time.get_ticks() / 1000.0  # 물 흐름 및 폭포 애니메이션용
        
        if state["stage"] == 3:
            draw_lava_river(state["stage"], game_time)
        else:
            draw_river_ground(state["stage"])
        
        if state["stage"] != 3:
            draw_water_flow(game_time, state["stage"])  # 물 흐름 애니메이션

        draw_banks(state["stage"])
        draw_trees(state.get("trees", []))
        draw_island(state["stage"])
        
        if state["stage"] == 3:
            draw_monsters(state.get("monsters", []), game_time)
        marker_positions = draw_distance_markers()  # 거리 푯말 렌더링 및 위치 저장

        # 도크 (폭포 전환 시 같이 내려감)
        glPushMatrix()
        glTranslatef(dock.x, 0.05, dock.z)
        draw_box(dock.w / 2, 0.05, dock.l / 2, DOCK_COLOR)
        glPopMatrix()
        
        # 폭포 렌더링 (도크 앞에)
        draw_waterfall(dock.z, game_time)

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

        # 보트 (폭포 전환 중이면 수직으로 떨어짐)
        if waterfall_active:
            timer = state.get("waterfall_timer", 0)
            fall_y = state.get("boat_fall_y", 0.0)
            # 보트가 실제로 아래로 떨어지는 효과
            glPushMatrix()
            glTranslatef(boat.pos.x, -fall_y, boat.pos.y)  # Y축으로 떨어짐
            glRotatef(timer * 30, 0, 1, 0)  # 회전하면서 떨어짐
            glRotatef(timer * 10, 1, 0, 0)  # 앞으로 기울어짐
            # 보트 모델을 원점 기준으로 그림
            glTranslatef(-boat.pos.x, 0, -boat.pos.y)
            draw_boat_mesh(boat, state.get("selected_boat", "RED_BOX"))
            draw_boat_decal(boat, boat_tex)
            glPopMatrix()
        else:
            draw_boat_mesh(boat, state.get("selected_boat", "RED_BOX"))          # 본체
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

        # (씬 행렬 복원 - 폭포 전환에서 더 이상 사용 안함)

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
            stage=state["stage"],
            progress_total_m=progress_total_m,
            score=state["score"]
        )
        draw_compass(gltext, boat)
        draw_throttle_gauge(gltext, boat)
        draw_minimap(gltext, boat, dock, lanes=LANES)
        draw_help_strip(gltext)
        
        # 거리 푯말에 텍스트 렌더링 (가까운 마커만, 푯말 위에 표시)
        end_ortho()  # 투영 행렬을 가져오기 위해 3D 모드로 전환
        boat_z = boat.pos.y
        for wx, wy, wz, dist_m in marker_positions:
            # 보트와의 거리 계산 (Z축 기준)
            marker_world_z = cfg.RIVER_LENGTH - dist_m
            dist_from_boat = abs(boat_z - marker_world_z)
            
            # 가까운 마커만 텍스트 표시 (150m 이내)
            if dist_from_boat > 150:
                continue
                
            screen_pos = project_point(wx, wy, wz)
            if screen_pos is not None:
                sx, sy = screen_pos
                # 화면 범위 내에 있을 때만 렌더링
                if 50 < sx < WIDTH - 50 and 50 < sy < HEIGHT - 50:
                    begin_ortho()
                    # 거리 텍스트 (예: "100m") - 큰 글씨 느낌으로 중앙 정렬
                    text = f"{int(dist_m)}m"
                    # 텍스트 길이에 따른 오프셋 조정
                    text_offset_x = len(text) * 5
                    gltext.draw(text, int(sx) - text_offset_x, int(sy) - 10, (255, 250, 240, 255))
                    end_ortho()

        begin_ortho()

        if lane_tune_timer > 0.0:
            draw_lane_tune_prompt(gltext, current_lane_idx)

        if TOAST_TEXT:
            draw_toast(gltext, TOAST_TEXT)
        
        # 레인 유속 팝업 렌더링
        if lane_popup_timer > 0:
            anim_progress = 1.0 - (lane_popup_timer / lane_popup_duration)
            draw_lane_flow_popup(
                gltext,
                lane_popup_info["lane_num"],
                lane_popup_info["flow_speed"],
                lane_popup_info["flow_dir"],
                anim_progress
            )

        if state["win"]:
            if state.get("waterfall_transition", False):
                # 폭포 전환 중 메시지
                timer = state.get("waterfall_timer", 0)
                alpha = min(255, int(timer * 100))
                next_stage = state.get("stage", 1) + 1
                
                # 페이드 효과
                from river3d.glutils import quad2
                fade_alpha = min(0.8, timer * 0.3)
                quad2(0, 0, WIDTH, HEIGHT, (0, 0, 0, fade_alpha))
                
                gltext.draw("SUCCESS!", WIDTH // 2 - 70, HEIGHT // 2 - 60, (76, 201, 128, alpha))
                gltext.draw("Falling down the waterfall...", WIDTH // 2 - 130, HEIGHT // 2 - 20, (200, 220, 255, alpha))
                gltext.draw(f"Next: Stage {next_stage}", WIDTH // 2 - 70, HEIGHT // 2 + 20, (255, 255, 150, alpha))
            else:
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
