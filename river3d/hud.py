from OpenGL.GL import *
from OpenGL.GLU import *
from .config import (
    WIDTH, HEIGHT, UI_BG_DARK, DOCK_COLOR, SHALLOW_WATER, DEEP_WATER,
    RIVER_LENGTH, RIVER_WIDTH, MARKERS, SHOW_MINIMAP,
    PREDICT_STEPS, PREDICT_DT, SECONDS_LIMIT
)
from .glutils import quad2
from .lanes import LANES, MIN_DEPTH, MAX_DEPTH, FLOW_SCALE, get_lane_index

def lerp_color(c1,c2,t):
    t=max(0,min(1,t)); return (c1[0]*(1-t)+c2[0]*t, c1[1]*(1-t)+c2[1]*t, c1[2]*(1-t)+c2[2]*t)

def depth_to_color(d, dmin, dmax):
    if dmax<=dmin: return SHALLOW_WATER
    return lerp_color(SHALLOW_WATER, DEEP_WATER, (d-dmin)/(dmax-dmin))

def timer_color(elapsed_ratio):
    if elapsed_ratio>0.5: t=(elapsed_ratio-0.5)/0.5; c0=(255,212,96); c1=(232,93,93)
    else: t=elapsed_ratio/0.5; c0=(76,201,128); c1=(255,212,96)
    return ((c0[0]*(1-t)+c1[0]*t)/255.0,(c0[1]*(1-t)+c1[1]*t)/255.0,(c0[2]*(1-t)+c1[2]*t)/255.0,1.0)

def project_point(x,y,z):
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    proj  = glGetDoublev(GL_PROJECTION_MATRIX)
    view  = glGetIntegerv(GL_VIEWPORT)
    win = gluProject(x,y,z, model, proj, view)
    if win is None: return None
    sx, sy, _ = win
    return (sx, sy)

def collect_marker_screens():
    pts=[]
    for m in MARKERS:
        p = project_point(RIVER_WIDTH/2 + 0.4, 0.6, m)
        if p: pts.append((p[0], HEIGHT - p[1], f"{m} m"))
    return pts

def draw_minimap(gltext, boat, dock):
    if not SHOW_MINIMAP: return
    mm_w,mm_h=200,130; mm_x,mm_y=WIDTH-20-mm_w,20
    quad2(mm_x,mm_y,mm_w,mm_h,UI_BG_DARK)
    glBegin(GL_QUADS)
    for ln in LANES:
        c=depth_to_color(ln.depth, MIN_DEPTH, MAX_DEPTH); glColor4f(c[0],c[1],c[2],0.9)
        z0=ln.z0/RIVER_LENGTH; z1=ln.z1/RIVER_LENGTH
        y0=mm_y+(1.0-z1)*mm_h; y1=mm_y+(1.0-z0)*mm_h
        glVertex2f(mm_x,y0); glVertex2f(mm_x+mm_w,y0); glVertex2f(mm_x+mm_w,y1); glVertex2f(mm_x,y1)
    glEnd()
    glColor4f(*DOCK_COLOR,1.0); dz=dock.z/RIVER_LENGTH; y0=mm_y+(1.0-dz)*mm_h
    glBegin(GL_LINES); glVertex2f(mm_x,y0); glVertex2f(mm_x+mm_w,y0); glEnd()

    glColor4f(0.2,0.2,0.2,0.9)
    if len(boat.trace)>1:
        glBegin(GL_LINE_STRIP)
        for p in boat.trace:
            u=(p.x+RIVER_WIDTH/2)/RIVER_WIDTH; v=1.0-(p.y/RIVER_LENGTH)
            glVertex2f(mm_x+u*mm_w, mm_y+v*mm_h)
        glEnd()
    glPointSize(6); glBegin(GL_POINTS); glColor4f(0.95,0.25,0.25,1.0)
    u=(boat.pos.x+RIVER_WIDTH/2)/RIVER_WIDTH; v=1.0-(boat.pos.y/RIVER_LENGTH)
    glVertex2f(mm_x+u*mm_w, mm_y+v*mm_h); glEnd()

    idx = get_lane_index(boat.pos.y)
    if idx is not None:
        gltext.draw(f"Lane {idx+1} speed x{FLOW_SCALE[idx]:.2f}", mm_x+8, mm_y+mm_h+6, (220,220,230,255))

def draw_throttle_gauge(gltext, boat):
    gx,gy,gw,gh=20,HEIGHT-220,22,180
    quad2(gx-2,gy-2,gw+4,gh+4,(1,1,1,0.05)); quad2(gx,gy,gw,gh,UI_BG_DARK)
    t=max(-1.0,min(1.0,boat.last_throttle)); mid=gy+gh/2
    if t>=0: h=(gh/2)*t; quad2(gx+2,mid-h,gw-4,h,(76/255,201/255,128/255,0.95))
    else:   h=(gh/2)*(-t); quad2(gx+2,mid,gw-4,h,(90/255,200/255,255/255,0.95))
    glColor4f(1,1,1,0.5); glBegin(GL_LINES); glVertex2f(gx,mid); glVertex2f(gx+gw,mid); glEnd()
    spd=boat.vel.length(); gltext.draw(f"SPD {spd:04.1f} m/s", gx+34, gy+gh-18, (235,235,240,255))
    gltext.draw("Throttle", gx+34, gy-2, (200,200,210,255))

def draw_compass(gltext,boat):
    cx,cy,cw,ch = WIDTH//2-160, 48, 320, 26
    quad2(cx,cy,cw,ch,UI_BG_DARK)
    hdg=(boat.heading%360+360)%360
    gltext.draw(f"HDG {hdg:06.2f}°", cx+6, cy+4, (235,235,240,255))

def draw_top_timer(gltext, time_left, coins_got, coins_total, progress_m):
    bar_w,bar_h=520,22; bar_x=(WIDTH-bar_w)//2; bar_y=10
    quad2(bar_x,bar_y,bar_w,bar_h,(24/255,28/255,34/255,0.85))
    ratio=max(0.0,min(1.0,time_left/SECONDS_LIMIT))
    col=timer_color(1.0-ratio)
    quad2(bar_x,bar_y,int(bar_w*ratio),bar_h,col)
    gltext.draw(f"Time {time_left:05.2f}s  |  Coins {coins_got}/{coins_total}  |  Progress {progress_m:.1f} m",
                bar_x+6, bar_y+bar_h+6, (235,235,240,255))

def draw_help_strip(gltext):
    help_w,help_h=900,28; help_x,help_y=(WIDTH-help_w)//2, HEIGHT-40
    quad2(help_x,help_y,help_w,help_h,(46/255,50/255,60/255,0.95))
    gltext.draw("←/→ turn | ↑/W throttle | ↓/S brake | T mouse-steer | 1..5 tune lane | R restart | L reroll | M minimap | P path | ESC pause",
                help_x+8, help_y+6, (240,240,240,255))

def draw_lane_tune_prompt(gltext, idx):
    if idx is None: return
    txt = f"Lane {idx+1}: set flow  1:-30%  2:-15%  3:base  4:+15%  5:+30%"
    tw,th = 620, 34; x,y=(WIDTH-tw)//2, 84
    quad2(x,y,tw,th,(0,0,0,0.60)); gltext.draw(txt, x+10, y+6, (255,255,255,255))

def draw_toast(gltext,text):
    if not text: return
    tw,th=420,36; tx,ty=(WIDTH-tw)//2, HEIGHT-80
    quad2(tx,ty,tw,th,(0,0,0,0.55)); gltext.draw(text, tx+10, ty+8, (255,255,255,255))
