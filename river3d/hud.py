# river3d/hud.py
from typing import Optional

# OpenGL (2D HUD 그리기용)
from OpenGL.GL import (
    glBegin, glEnd, glVertex2f, glColor4f,
    GL_QUADS, GL_LINES, GL_LINE_STRIP, GL_POINTS, glPointSize
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
def draw_minimap(gltext: GLText, boat, dock, show_trail: bool = True):
    """
    오른쪽 상단 미니맵 (정상 방향)
    - z(하류) 증가할수록 미니맵 y도 증가하도록 매핑 (반전 제거)
    """
    mm_w, mm_h = 200, 130
    mm_x, mm_y = WIDTH - 20 - mm_w, 20

    # 배경 패널
    quad2(mm_x, mm_y, mm_w, mm_h, (22/255, 26/255, 32/255, 0.90))

    # 레인 띠 (수심색)
    glBegin(GL_QUADS)
    for ln in LANES:
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

    # 도크 위치 라인 (정방향)
    glColor4f(0.16, 0.70, 0.36, 1.0)
    dz = dock.z / RIVER_LENGTH
    y_dock = mm_y + dz * mm_h
    glBegin(GL_LINES)
    glVertex2f(mm_x,        y_dock)
    glVertex2f(mm_x+mm_w,   y_dock)
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

    # 현재 레인 간단 표기
    for i, ln in enumerate(LANES):
        if ln.z0 <= boat.pos.y < ln.z1:
            # 레인 번호를 1번부터 시작하여 표시
            gltext.draw(f"Lane {i+1}", mm_x+8, mm_y+mm_h+6, (220, 220, 230, 255))
            break


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

    # 요청에 맞춰 간단 표기(Score 중심), 필요 시 주석 풀어서 확장 가능
    text = (
        f"Time {min(time_left, 20.00):05.2f}s  |  "
        f"Stage {stage}  |  "
        f"Score {score}"
    )
    gltext.draw(text, bar_x + 120, bar_y + bar_h + 6, (0, 0, 0, 255))


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
        "←/→ turn | ↑/W throttle | ↓/S brake | T mouse-steer | 1..5 tune lane | R restart | L reroll | M minimap | P path | ESC pause",
        help_x + 8, help_y + 6, (240, 240, 240, 255)
    )


def draw_lane_tune_prompt(gltext: GLText, idx: Optional[int]):
    if idx is None:
        return
    txt = f"Lane {idx+1}: set flow  1:-30%  2:-15%  3:base  4:+15%  5:+30%"
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

    for i, val in enumerate(scales):
        y = top + i*gap
        gltext.draw(f"Lane {i+1}", left, y-18, (40, 40, 40, 255))
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

