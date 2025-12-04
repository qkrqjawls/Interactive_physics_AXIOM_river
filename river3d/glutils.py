import math
from OpenGL.GL import *
from OpenGL.GLU import *
import pygame
from .config import WIDTH, HEIGHT, GL_NEAR, GL_FAR, SKY_COLOR

# ---- basic GL ----
def init_gl():
    glViewport(0,0,WIDTH,HEIGHT)
    glDisable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS); glClearDepth(1.0); glDepthMask(GL_TRUE)
    glEnable(GL_CULL_FACE); glCullFace(GL_BACK)
    glClearColor(*SKY_COLOR,1.0)
    glMatrixMode(GL_PROJECTION); glLoadIdentity(); gluPerspective(60.0, WIDTH/HEIGHT, GL_NEAR, GL_FAR)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()

def begin_ortho():
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, WIDTH, HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glDisable(GL_CULL_FACE)
    glDisable(GL_DEPTH_TEST); glDepthMask(GL_FALSE)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def end_ortho():
    glDisable(GL_BLEND); glDepthMask(GL_TRUE)
    glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE)
    glMatrixMode(GL_MODELVIEW); glPopMatrix()
    glMatrixMode(GL_PROJECTION); glPopMatrix()

def quad2(x,y,w,h,color):
    glColor4f(*color); glBegin(GL_QUADS)
    glVertex2f(x,y); glVertex2f(x+w,y); glVertex2f(x+w,y+h); glVertex2f(x,y+h)
    glEnd()

# ---- text ----
class GLText:
    def __init__(self, font_name="malgungothic", size=18):
        pygame.font.init()
        try: self.font = pygame.font.SysFont(font_name, size)
        except: self.font = pygame.font.SysFont(None, size)

    def draw(self, text, x, y, color=(240,240,240,255)):
        surf = self.font.render(text, True, color[:3])
        w,h = surf.get_width(), surf.get_height()
        data = pygame.image.tostring(surf, "RGBA", False)  # no flip
        tex  = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glEnable(GL_TEXTURE_2D); glColor4f(1,1,1,1)
        glBegin(GL_QUADS)
        glTexCoord2f(0,0); glVertex2f(x,   y)
        glTexCoord2f(1,0); glVertex2f(x+w, y)
        glTexCoord2f(1,1); glVertex2f(x+w, y+h)
        glTexCoord2f(0,1); glVertex2f(x,   y+h)
        glEnd()
        glDisable(GL_TEXTURE_2D); glDeleteTextures([tex])

# ---- simple draw helpers ----
def draw_box(hw, hh, hd, color):
    glColor3f(*color)
    glBegin(GL_QUADS)

    # Front (+Z)
    glVertex3f(-hw, -hh,  hd)
    glVertex3f( hw, -hh,  hd)
    glVertex3f( hw,  hh,  hd)
    glVertex3f(-hw,  hh,  hd)

    # Back (-Z)
    glVertex3f( hw, -hh, -hd)
    glVertex3f(-hw, -hh, -hd)
    glVertex3f(-hw,  hh, -hd)
    glVertex3f( hw,  hh, -hd)

    # Left (-X)
    glVertex3f(-hw, -hh, -hd)
    glVertex3f(-hw, -hh,  hd)
    glVertex3f(-hw,  hh,  hd)
    glVertex3f(-hw,  hh, -hd)

    # Right (+X)
    glVertex3f( hw, -hh,  hd)
    glVertex3f( hw, -hh, -hd)
    glVertex3f( hw,  hh, -hd)
    glVertex3f( hw,  hh,  hd)

    # Top (+Y)
    glVertex3f(-hw,  hh,  hd)
    glVertex3f( hw,  hh,  hd)
    glVertex3f( hw,  hh, -hd)
    glVertex3f(-hw,  hh, -hd)

    # Bottom (-Y)
    glVertex3f(-hw, -hh, -hd)
    glVertex3f( hw, -hh, -hd)
    glVertex3f( hw, -hh,  hd)
    glVertex3f(-hw, -hh,  hd)

    glEnd()


def draw_cylinder(radius=0.5,height=0.2,color=(1,1,0),slices=24):
    glColor3f(*color)
    glBegin(GL_TRIANGLE_FAN); glVertex3f(0,height/2,0)
    for i in range(slices+1):
        th=2*3.1415926535*i/slices; glVertex3f(radius*math.cos(th),height/2,radius*math.sin(th))
    glEnd()
    glBegin(GL_TRIANGLE_FAN); glVertex3f(0,-height/2,0)
    for i in range(slices+1):
        th=2*3.1415926535*i/slices; glVertex3f(radius*math.cos(th),-height/2,radius*math.sin(th))
    glEnd()
    glBegin(GL_QUAD_STRIP)
    for i in range(slices+1):
        th=2*3.1415926535*i/slices; x=radius*math.cos(th); z=radius*math.sin(th)
        glVertex3f(x,-height/2,z); glVertex3f(x,height/2,z)
    glEnd()
# --- color helpers for water depth ---
def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        c1[0] * (1.0 - t) + c2[0] * t,
        c1[1] * (1.0 - t) + c2[1] * t,
        c1[2] * (1.0 - t) + c2[2] * t,
    )

# shallow↔deep palette
SHALLOW_WATER = (195/255.0, 225/255.0, 245/255.0)
DEEP_WATER    = ( 60/255.0, 120/255.0, 220/255.0)

def depth_to_color(depth: float, dmin: float, dmax: float):
    if dmax <= dmin:
        return SHALLOW_WATER
    t = (depth - dmin) / (dmax - dmin)
    return lerp_color(SHALLOW_WATER, DEEP_WATER, t)
   
   
#--- texture helpers ---
def load_texture_rgba(path: str) -> int:
    import pygame
    surf = pygame.image.load(path).convert_alpha()
    w, h = surf.get_width(), surf.get_height()
    data = pygame.image.tostring(surf, "RGBA", True)  # OpenGL용 상하반전
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex

def _read_modelview_16f():
    """환경에 따라 4, 9, 16 등으로 올 수 있어 16개짜리로 강제 확보"""
    try:
        mv = glGetFloatv(GL_MODELVIEW_MATRIX)
        if hasattr(mv, "__len__") and len(mv) == 16:
            return mv
    except Exception:
        pass
    # 강제 버퍼 경로
    from ctypes import c_float
    buf = (c_float * 16)()
    glGetFloatv(GL_MODELVIEW_MATRIX, buf)  # in-place 채움
    return [buf[i] for i in range(16)]

def draw_billboard_sprite(size: float, tex_id: int):
    """카메라를 향하는 스프라이트. 행렬 길이 4 문제 방지 및 알파블렌딩 포함"""
    mv = _read_modelview_16f()
    # OpenGL 고정 기능 파이프라인 기준: 열우선 저장
    # right = (m00, m10, m20), up = (m01, m11, m21)
    rx, ry, rz = mv[0], mv[4], mv[8]    # x축
    ux, uy, uz = mv[1], mv[5], mv[9]    # y축

    hs = size * 0.5
    # 카메라 공간의 right/up을 월드로 가져온 뒤 사각 정점 생성
    v0 = (-(rx*hs + ux*hs), -(ry*hs + uy*hs), -(rz*hs + uz*hs))
    v1 = ( +(rx*hs - ux*hs), +(ry*hs - uy*hs), +(rz*hs - uz*hs))
    v2 = ( +(rx*hs + ux*hs), +(ry*hs + uy*hs), +(rz*hs + uz*hs))
    v3 = ( -(rx*hs - ux*hs), -(ry*hs - uy*hs), -(rz*hs - uz*hs))

    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_CULL_FACE)  # 뒤집힘 방지(양면 표시)

    glColor4f(1,1,1,1)
    glBegin(GL_QUADS)
    glTexCoord2f(0,1); glVertex3f(*v0)
    glTexCoord2f(1,1); glVertex3f(*v1)
    glTexCoord2f(1,0); glVertex3f(*v2)
    glTexCoord2f(0,0); glVertex3f(*v3)
    glEnd()

    glEnable(GL_CULL_FACE)
    glDisable(GL_TEXTURE_2D)
    
#--- coin draw helper ---
def draw_textured_coin(radius: float, thickness: float, tex_id: int, slices: int = 64, tex_scale: float = 1.0):
    """앞/뒷면은 coin 텍스처, 옆면은 골드 림으로 그리는 3D 동전"""
    hs = thickness * 0.5

    # 공통 상태
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    
    # 텍스처가 경계 밖(>1, <0)로 나가도 테두리 깨짐 없게
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    
    glDisable(GL_CULL_FACE)  # 앞/뒤 모두 보이게

    # --- Top (y=+hs): TRIANGLE_FAN with radial UV (0.5+0.5*cos, 0.5+0.5*sin)
    glColor4f(1,1,1,1)
    glBegin(GL_TRIANGLE_FAN)
    glTexCoord2f(0.5, 0.5); glVertex3f(0, +hs, 0)
    for i in range(slices + 1):
        th = 2*math.pi * i / slices
        u = 0.5 + 0.5 * tex_scale * math.cos(th)   # << 확대 핵심
        v = 0.5 + 0.5 * tex_scale * math.sin(th)
        x = radius * math.cos(th)
        z = radius * math.sin(th)
        glTexCoord2f(u, v); glVertex3f(x, +hs, z)
    glEnd()

    # --- Bottom (y=-hs): 텍스처가 거울처럼 뒤집히지 않도록 v를 반대로
    glBegin(GL_TRIANGLE_FAN)
    glTexCoord2f(0.5, 0.5); glVertex3f(0, -hs, 0)
    for i in range(slices + 1):
        th = 2*math.pi * i / slices
        u = 0.5 + 0.5 * tex_scale * math.cos(th)
        v = 0.5 + 0.5 * tex_scale * math.sin(th)
        x = radius * math.cos(th)
        z = radius * math.sin(th)
        glTexCoord2f(u, v); glVertex3f(x, -hs, z)
    glEnd()

    # --- Rim (옆면): QUAD_STRIP, 금속 계열 컬러(텍스처 없음)
    glDisable(GL_TEXTURE_2D)
    glColor3f(0.95, 0.78, 0.25)
    glBegin(GL_QUAD_STRIP)
    for i in range(slices + 1):
        th = 2*math.pi * i / slices
        x = radius * math.cos(th)
        z = radius * math.sin(th)
        glVertex3f(x, -hs, z)
        glVertex3f(x, +hs, z)
    glEnd()

    # 상태 복구
    glEnable(GL_CULL_FACE)
    glDisable(GL_BLEND)