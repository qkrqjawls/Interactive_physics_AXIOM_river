# river3d/hud.py
from typing import Optional

# OpenGL (2D HUD 그리기용)
from OpenGL.GL import (
    glBegin, glEnd, glVertex2f, glColor4f,
    GL_QUADS, GL_LINES, GL_LINE_STRIP, GL_LINE_LOOP, GL_POINTS, glPointSize
)
from OpenGL.GL import glGetDoublev, glGetIntegerv, GL_MODELVIEW_MATRIX, GL_PROJECTION_MATRIX, GL_VIEWPORT
from OpenGL.GLU import gluProject

from .config import (
    WIDTH, HEIGHT, SECONDS_LIMIT, RIVER_LENGTH, RIVER_WIDTH
)
from .lanes import LANES, MIN_DEPTH, MAX_DEPTH
from .glutils import quad2, GLText, depth_to_color

# --------- UI color helpers ---------
def timer_color(elapsed_ratio: float):
    """
    elapsed_ratio: 0.0(남은시간 최대) -> 1.0(시간 소진)
    Green -> Yellow -> Red 로 보간
    """
    if elapsed_ratio > 0.5:
        t = (elapsed_ratio - 0.5) / 0.5
        c0 = (255, 212, 96)  # yellow
        c1 = (232, 93, 93)   # red
    else:
        t = elapsed_ratio / 0.5
        c0 = (76, 201, 128)  # green
        c1 = (255, 212, 96)  # yellow
    return (
        (c0[0]*(1-t)+c1[0]*t)/255.0,
        (c0[1]*(1-t)+c1[1]*t)/255.0,
        (c0[2]*(1-t)+c1[2]*t)/255.0,
        1.0
    )

# --------- HUD pieces ---------
def draw_minimap(gltext: GLText, boat, dock, lanes=None, show_trail: bool = True):
    """
    오른쪽 상단 미니맵 (정상 방향)
    - z(하류) 증가할수록 미니맵 y도 증가하도록 매핑 (반전 제거)
    """
    if lanes is None:
        from .lanes import LANES as lanes

    mm_w, mm_h = 200, 130
    mm_x, mm_y = WIDTH - 20 - mm_w, 20

    # 배경 패널
    quad2(mm_x, mm_y, mm_w, mm_h, (22/255, 26/255, 32/255, 0.90))

    # 레인 띠 (수심색)
    glBegin(GL_QUADS)
    for ln in lanes:
        c = depth_to_color(ln.depth, MIN_DEPTH, MAX_DEPTH)
        glColor4f(c[0], c[1], c[2], 0.9)
        # 정방향 매핑: v = z / RIVER_LENGTH   (반전 없이)
        z0 = ln.z0 / RIVER_LENGTH
        z1 = ln.z1 / RIVER_LENGTH
        y0 = mm_y + z0 * mm_h
        y1 = mm_y + z1 * mm_h
        glVertex2f(mm_x,        y0)
        glVertex2f(mm_x+mm_w,   y0)
        glVertex2f(mm_x+mm_w,   y1)
        glVertex2f(mm_x,        y1)
    glEnd()
    
    # 각 레인의 깊이 표시 (h= 형식)
    from .config import LANE_COUNT
    for i, ln in enumerate(lanes):
        z_center = (ln.z0 + ln.z1) / 2 / RIVER_LENGTH
        y_center = mm_y + z_center * mm_h
        depth_text = f"h={ln.depth:.1f}m"
        # 속도 표시 (L값 대신)
        speed_text = f"{abs(ln.vx):.1f}m/s"
        gltext.draw(f"{speed_text} {depth_text}", mm_x + 5, int(y_center) - 8, (255, 255, 255, 200))

    # 도크 위치를 직사각형 타일로 표시
    glColor4f(0.16, 0.70, 0.36, 0.95)
    dock_z0 = dock.z / RIVER_LENGTH
    dock_z1 = (dock.z + dock.l) / RIVER_LENGTH  # 도크 길이만큼
    dock_x0 = (dock.x - dock.w/2 + RIVER_WIDTH/2) / RIVER_WIDTH
    dock_x1 = (dock.x + dock.w/2 + RIVER_WIDTH/2) / RIVER_WIDTH
    
    y0_dock = mm_y + dock_z0 * mm_h
    y1_dock = mm_y + dock_z1 * mm_h
    x0_dock = mm_x + dock_x0 * mm_w
    x1_dock = mm_x + dock_x1 * mm_w
    
    glBegin(GL_QUADS)
    glVertex2f(x0_dock, y0_dock)
    glVertex2f(x1_dock, y0_dock)
    glVertex2f(x1_dock, y1_dock)
    glVertex2f(x0_dock, y1_dock)
    glEnd()
    
    # 도크 테두리 강조
    glColor4f(0.1, 0.5, 0.25, 1.0)
    glBegin(GL_LINE_LOOP)
    glVertex2f(x0_dock, y0_dock)
    glVertex2f(x1_dock, y0_dock)
    glVertex2f(x1_dock, y1_dock)
    glVertex2f(x0_dock, y1_dock)
    glEnd()

    # 궤적
    if show_trail and len(boat.trace) > 1:
        glColor4f(0.2, 0.2, 0.2, 0.9)
        glBegin(GL_LINE_STRIP)
        for p in boat.trace:
            u = (p.x + RIVER_WIDTH/2) / RIVER_WIDTH
            v = p.y / RIVER_LENGTH               # <- 정방향
            glVertex2f(mm_x + u*mm_w, mm_y + v*mm_h)
        glEnd()

    # 현재 위치 점
    glPointSize(6)
    glBegin(GL_POINTS)
    glColor4f(0.95, 0.25, 0.25, 1.0)
    u = (boat.pos.x + RIVER_WIDTH/2) / RIVER_WIDTH
    v = boat.pos.y / RIVER_LENGTH               # <- 정방향
    glVertex2f(mm_x + u*mm_w, mm_y + v*mm_h)
    glEnd()

    # 현재 레인 간단 표기 (get_lane_index는 이미 뒤집힌 번호를 반환)
    from .lanes import get_lane_index
    lane_num = get_lane_index(boat.pos.y)
    if lane_num is not None:
        gltext.draw(f"Lane {lane_num}", mm_x+8, mm_y+mm_h+6, (220, 220, 230, 255))


def draw_top_timer(
    gltext: GLText,
    time_left: float,
    coins_got: int,
    coins_total: int,
    progress_m: float,
    stage: int = 1,
    progress_total_m: Optional[float] = None,
    score: int = 0,
):
    # 상단 타이머 + 진행도
    bar_w, bar_h = 520, 22
    bar_x, bar_y = (WIDTH - bar_w) // 2, 10

    quad2(bar_x, bar_y, bar_w, bar_h, (24/255, 28/255, 34/255, 0.85))
    ratio = max(0.0, min(1.0, time_left / SECONDS_LIMIT))
    col = timer_color(1.0 - ratio)
    quad2(bar_x, bar_y, int(bar_w * ratio), bar_h, col)

    # 요청에 맞춰 간단 표기(Score 중심)
    text = (
        f"Time {time_left:05.2f}s  |  "
        f"Stage {stage}  |  "
        f"Score {score}"
    )
    # Stage 3는 배경이 어두우므로 흰색 텍스트
    text_color = (255, 255, 255, 255) if stage == 3 else (0, 0, 0, 255)
    gltext.draw(text, bar_x + 120, bar_y + bar_h + 6, text_color)


def draw_compass(gltext: GLText, boat):
    cx, cy, cw, ch = WIDTH // 2 - 160, 68, 320, 26
    quad2(cx, cy, cw, ch, (22/255, 26/255, 32/255, 0.90))
    # 시각상 전방을 0°로 보고 ±180° 범위로 표현
    hdg = ((boat.heading + 270) % 360) - 180
    gltext.draw(f"HDG {hdg:06.2f}°", cx+6, cy+4, (235, 235, 240, 255))


def draw_throttle_gauge(gltext: GLText, boat):
    gx, gy, gw, gh = 20, HEIGHT - 220, 22, 180
    quad2(gx-2, gy-2, gw+4, gh+4, (1, 1, 1, 0.05))
    quad2(gx, gy, gw, gh, (22/255, 26/255, 32/255, 0.90))

    t = max(-1.0, min(1.0, getattr(boat, "last_throttle", 0.0)))
    mid = gy + gh/2
    if t >= 0:
        h = (gh/2) * t
        quad2(gx+2, mid - h, gw-4, h, (76/255, 201/255, 128/255, 0.95))
    else:
        h = (gh/2) * (-t)
        quad2(gx+2, mid, gw-4, h, (90/255, 200/255, 255/255, 0.95))

    # 중앙선
    glColor4f(1, 1, 1, 0.5)
    glBegin(GL_LINES); glVertex2f(gx, mid); glVertex2f(gx+gw, mid); glEnd()

    spd = boat.vel.length()
    gltext.draw(f"SPD {spd:04.1f} m/s", gx+34, gy+gh-18, (235, 235, 240, 255))
    gltext.draw("Throttle", gx+34, gy-2, (200, 200, 210, 255))


def draw_help_strip(gltext: GLText):
    help_w, help_h = 900, 28
    help_x, help_y = (WIDTH - help_w)//2, HEIGHT - 40
    quad2(help_x, help_y, help_w, help_h, (46/255, 50/255, 60/255, 0.95))
    gltext.draw(
        "←/→ turn | ↑/W throttle | ↓/S brake | T mouse-steer | R restart | P path | ESC pause",
        help_x + 8, help_y + 6, (240, 240, 240, 255)
    )


def draw_lane_tune_prompt(gltext: GLText, idx: Optional[int]):
    if idx is None:
        return
    txt = f"Lane {idx}: set flow  1:-30%  2:-15%  3:base  4:+15%  5:+30%"
    tw, th = 620, 34
    x, y = (WIDTH - tw)//2, 98
    quad2(x, y, tw, th, (0, 0, 0, 0.60))
    gltext.draw(txt, x+10, y+6, (255, 255, 255, 255))


def draw_toast(gltext: GLText, text: str):
    if not text:
        return
    tw, th = 420, 36
    tx, ty = (WIDTH - tw)//2, HEIGHT - 80
    quad2(tx, ty, tw, th, (0, 0, 0, 0.55))
    gltext.draw(text, tx+10, ty+8, (255, 255, 255, 255))


def draw_lane_flow_popup(gltext: GLText, lane_num: int, flow_speed: float, flow_dir: int, anim_progress: float):
    """
    새 구간 진입 시 유속과 방향을 팝업으로 보여준다.
    flow_dir: -1 = 왼쪽, +1 = 오른쪽
    anim_progress: 0.0~1.0 (애니메이션 진행도, 1.0이면 완전히 표시)
    """
    if anim_progress <= 0:
        return
    
    # 애니메이션 효과 (뿅 하고 나타나는 느낌)
    scale = min(1.0, anim_progress * 2.0)  # 빠르게 커짐
    alpha = min(1.0, anim_progress * 1.5) if anim_progress < 0.8 else max(0.0, (1.0 - anim_progress) * 5.0)
    
    pw, ph = int(320 * scale), int(100 * scale)
    px, py = (WIDTH - pw)//2, (HEIGHT - ph)//2 - 50
    
    # 배경 (반투명, 그라데이션 느낌)
    bg_color = (0.1, 0.15, 0.25, 0.85 * alpha)
    quad2(px, py, pw, ph, bg_color)
    
    # 테두리
    border_color = (0.3, 0.6, 0.9, alpha)
    glColor4f(*border_color)
    glBegin(GL_LINE_LOOP)
    glVertex2f(px, py)
    glVertex2f(px + pw, py)
    glVertex2f(px + pw, py + ph)
    glVertex2f(px, py + ph)
    glEnd()
    
    if scale < 0.5:
        return  # 너무 작으면 텍스트 안 그림
    
    # 레인 번호
    lane_text = f"Lane {lane_num}"
    text_alpha = int(255 * alpha)
    gltext.draw(lane_text, px + pw//2 - 30, py + 12, (255, 255, 255, text_alpha))
    
    # 화살표 방향
    arrow = "←" if flow_dir < 0 else "→"
    arrow_color = (100, 200, 255, text_alpha) if flow_dir < 0 else (255, 180, 100, text_alpha)
    gltext.draw(arrow, px + pw//2 - 60, py + 45, arrow_color)
    gltext.draw(arrow, px + pw//2 + 45, py + 45, arrow_color)
    
    # 유속 숫자
    speed_text = f"{abs(flow_speed):.1f} m/s"
    gltext.draw(speed_text, px + pw//2 - 35, py + 45, (255, 255, 100, text_alpha))
    
    # 설명
    dir_text = "왼쪽으로 흐름" if flow_dir < 0 else "오른쪽으로 흐름"
    gltext.draw(dir_text, px + pw//2 - 50, py + 75, (200, 200, 220, text_alpha))


def draw_pause_menu(gltext: GLText):
    quad2(0, 0, WIDTH, HEIGHT, (0, 0, 0, 0.45))
    pw, ph = 560, 320
    px, py = (WIDTH - pw)//2, (HEIGHT - ph)//2
    quad2(px, py, pw, ph, (1, 1, 1, 0.96))
    gltext.draw("PAUSED", px+230, py+24, (30, 30, 30, 255))
    gltext.draw(
        "Resume: ESC   |   Restart: R   |   Reroll lanes: L   |   Quit: Q",
        px+24, py+80, (40, 40, 40, 255)
    )


def draw_banner(gltext: GLText, text_main: str, sub: str = "Press R to restart", color=(76, 201, 128, 255)):
    bw, bh = 360, 120
    bx, by = (WIDTH - bw)//2, (HEIGHT - bh)//2
    quad2(bx, by, bw, bh, (1, 1, 1, 0.96))

    # 테두리
    glColor4f(color[0]/255, color[1]/255, color[2]/255, 1.0)
    glBegin(GL_LINES)
    glVertex2f(bx, by);         glVertex2f(bx+bw, by)
    glVertex2f(bx+bw, by);      glVertex2f(bx+bw, by+bh)
    glVertex2f(bx+bw, by+bh);   glVertex2f(bx, by+bh)
    glVertex2f(bx, by+bh);      glVertex2f(bx, by)
    glEnd()

    gltext.draw(text_main, bx+120, by+28, color)
    gltext.draw(sub, bx+96, by+72, (20, 20, 20, 255))


# --------- 3D→2D label projection (선택 사용) ---------
def project_point(x: float, y: float, z: float):
    """3D 좌표를 화면 픽셀 좌표로 투영 (HUD 라벨 등 용도)"""
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    proj  = glGetDoublev(GL_PROJECTION_MATRIX)
    view  = glGetIntegerv(GL_VIEWPORT)
    win = gluProject(x, y, z, model, proj, view)
    if win is None:
        return None
    sx, sy, _ = win
    # OpenGL 원점은 왼쪽-아래, HUD는 왼쪽-위 기준이므로 y 반전하려면 여기서 처리
    return (sx, HEIGHT - sy)


# --------- Next Stage Tuner ---------
def draw_next_stage_tuner(gltext: GLText, scales, active_lane: Optional[int] = None):
    """
    SUCCESS 이후 다음 스테이지 시작 전에 레인별 유속 배율(0.60~1.60) 조절 패널
    - 마우스로 막대 클릭/드래그
    - 숫자키 1..5로 해당 레인에 포커스(메인에서 처리)
    - Enter 적용 / ESC 기본값
    """
    quad2(0, 0, WIDTH, HEIGHT, (0, 0, 0, 0.50))
    panel_w, panel_h = 720, 360
    px, py = (WIDTH - panel_w)//2, (HEIGHT - panel_h)//2
    quad2(px, py, panel_w, panel_h, (1, 1, 1, 0.96))
    gltext.draw("Next Stage Setup", px+24, py+18, (30, 30, 30, 255))
    gltext.draw("Adjust lane flow multipliers (0.60~1.60). Click bars or use 1..5 to snap. Enter=Start, ESC=Cancel",
                px+24, py+52, (60, 60, 60, 255))

    left = px + 36
    top  = py + 96
    w_bar = panel_w - 72
    h_bar = 18
    gap  = 42

    from .config import LANE_COUNT
    for i, val in enumerate(scales):
        y = top + i*gap
        # 뒤집힌 레인 번호 (시작이 1, 도크가 5)
        display_lane = LANE_COUNT - i
        gltext.draw(f"Lane {display_lane}", left, y-18, (40, 40, 40, 255))
        # 바 배경
        quad2(left, y, w_bar, h_bar, (0.90, 0.93, 0.96, 1.0))
        # 값 → 0..1 정규화
        t = (val - 0.60) / (1.60 - 0.60)
        t = max(0.0, min(1.0, t))
        fill_w = int(w_bar * t)
        quad2(left, y, fill_w, h_bar, (76/255, 201/255, 128/255, 0.95 if active_lane == i else 0.85))
        gltext.draw(f"x{val:.2f}", left + w_bar + 12, y-4, (30, 30, 30, 255))

    gltext.draw("Enter: start next stage   |   ESC: cancel (defaults)   |   Click/drag bars",
                px+24, py+panel_h-40, (60, 60, 60, 255))

