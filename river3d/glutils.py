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
def draw_box(hw,hh,hd,color):
    glColor3f(*color); glBegin(GL_QUADS)
    glVertex3f(hw,-hh,-hd); glVertex3f(hw,hh,-hd); glVertex3f(hw,hh,hd); glVertex3f(hw,-hh,hd)
    glVertex3f(-hw,-hh,hd); glVertex3f(-hw,hh,hd); glVertex3f(-hw,hh,-hd); glVertex3f(-hw,-hh,-hd)
    glVertex3f(-hw,hh,-hd); glVertex3f(hw,hh,-hd); glVertex3f(hw,hh,hd); glVertex3f(-hw,hh,hd)
    glVertex3f(-hw,-hh,hd); glVertex3f(hw,-hh,hd); glVertex3f(hw,-hh,-hd); glVertex3f(-hw,-hh,-hd)
    glVertex3f(-hw,-hh,hd); glVertex3f(-hw,hh,hd); glVertex3f(hw,hh,hd); glVertex3f(hw,-hh,hd)
    glVertex3f(hw,-hh,-hd); glVertex3f(hw,hh,-hd); glVertex3f(-hw,hh,-hd); glVertex3f(-hw,-hh,-hd)
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
