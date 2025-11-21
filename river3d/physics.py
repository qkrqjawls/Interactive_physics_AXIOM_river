import pygame
from .config import (
    SEPARATION_EPS, BOUNCE_RESTITUTION, FRICTION_STATIC, FRICTION_DYNAMIC,
    BOUNCE_DAMPING, TANGENT_BOOST, TARGET_SPEED_MIN, TARGET_SPEED_MAX,
    MAX_BACK_BOUNCE_VZ, FORWARD_SOFT_MIN_VZ, CURVE_TIME, STUN_TIME
)
from .entities import boat_aabb

def aabb_overlap(a,b):
    ax0,az0,ax1,az1=a; bx0,bz0,bx1,bz1=b
    return not (ax1<bx0 or ax0>bx1 or az1<bz0 or az0>bz1)

def bounce_response(boat, obst):
    bx0,bz0,bx1,bz1=boat_aabb(boat); ox0,oz0,ox1,oz1=obst.aabb()
    dx1=ox1-bx0; dx2=bx1-ox0; dz1=oz1-bz0; dz2=bz1-oz0
    pen_x=min(dx1,dx2); pen_z=min(dz1,dz2)

    if pen_x < pen_z:
        n = pygame.Vector2(1,0) if dx1 < dx2 else pygame.Vector2(-1,0)
        push = (pen_x + SEPARATION_EPS) * (1 if n.x<0 else -1)
        boat.pos.x += push
    else:
        n = pygame.Vector2(0,1) if dz1 < dz2 else pygame.Vector2(0,-1)
        push = (pen_z + SEPARATION_EPS) * (1 if n.y<0 else -1)
        boat.pos.y += push

    v_in=boat.vel
    vn=v_in.dot(n)
    vt_vec=v_in - vn*n
    vt_len=vt_vec.length()

    jn=-(1.0+BOUNCE_RESTITUTION)*vn
    jn=max(0.0, jn)
    v_after_n=v_in + jn*n

    if vt_len>1e-6 and jn>0.0:
        t_hat=vt_vec/vt_len
        if vt_len<=FRICTION_STATIC*jn: v_after_t=v_after_n - vt_vec
        else: v_after_t=v_after_n - (FRICTION_DYNAMIC*jn)*t_hat
    else:
        v_after_t=v_after_n

    v_reflect = v_after_t * BOUNCE_DAMPING
    if vt_len>1e-6: v_reflect += (TANGENT_BOOST-1.0)*vt_vec

    if v_reflect.dot(n) < 0:
        v_reflect -= n * v_reflect.dot(n) * 1.2

    if v_reflect.y > 0:
        v_reflect.y = min(v_reflect.y, MAX_BACK_BOUNCE_VZ)

    spd=v_reflect.length()
    if spd>1e-6:
        spd=max(TARGET_SPEED_MIN, min(TARGET_SPEED_MAX, spd))
        v_reflect.scale_to_length(spd)
    else:
        v_reflect=boat.forward_vec()*TARGET_SPEED_MIN

    boat.vel = v_reflect
    f=boat.forward_vec()
    boat.vel_target = pygame.Vector2(
        v_reflect.x*0.8 + f.x*0.2*TARGET_SPEED_MIN,
        min(v_reflect.y, -FORWARD_SOFT_MIN_VZ)
    )
    boat.has_target = True
    boat.recovery_timer = 0.80

    t=pygame.Vector2(-n.y, n.x)
    sign_t=1.0 if (vt_vec.dot(t) >= 0) else -1.0
    boat.curve_dir = t * sign_t
    boat.curve_timer = CURVE_TIME
    boat.stun_timer = min(STUN_TIME, 0.10)

# physics.py (추가)
import math
import pygame
from river3d.config import RIVER_WIDTH, BOAT_WID, BOAT_LEN, TARGET_SPEED_MIN, TARGET_SPEED_MAX
from river3d.config import BOUNCE_RESTITUTION, BOUNCE_DAMPING, FRICTION_STATIC, FRICTION_DYNAMIC, FORWARD_SOFT_MIN_VZ, MAX_BACK_BOUNCE_VZ, CURVE_TIME
from river3d.entities import Boat

SEPARATION_EPS = 0.05  # 살짝 더 밀어내기

def _reflect_with_normal(boat: Boat, n: pygame.Vector2):
    # 기존 bounce_response와 동일한 반사 로직(간소화)
    v_in = boat.vel
    vn = v_in.dot(n)
    vt_vec = v_in - vn * n
    vt_len = vt_vec.length()

    # 탄성 임펄스
    jn = -(1.0 + BOUNCE_RESTITUTION) * vn
    if jn < 0.0: jn = 0.0
    v_after_n = v_in + jn * n

    # 쿨롱 마찰
    if vt_len > 1e-6 and jn > 0.0:
        t_hat = vt_vec / vt_len
        if vt_len <= FRICTION_STATIC * jn:
            v_after_t = v_after_n - vt_vec
        else:
            v_after_t = v_after_n - (FRICTION_DYNAMIC * jn) * t_hat
    else:
        v_after_t = v_after_n

    v_reflect = v_after_t * BOUNCE_DAMPING

    # 뒤로 너무 많이 튀는거 제한
    if v_reflect.y > 0:
        v_reflect.y = min(v_reflect.y, MAX_BACK_BOUNCE_VZ)

    spd = v_reflect.length()
    if spd > 1e-6:
        spd = max(TARGET_SPEED_MIN, min(TARGET_SPEED_MAX, spd))
        v_reflect.scale_to_length(spd)
    else:
        f = boat.forward_vec()
        v_reflect = f * TARGET_SPEED_MIN

    boat.vel = v_reflect

    # 부드러운 커브 가속
    t = pygame.Vector2(-n.y, n.x)
    boat.curve_dir = t
    boat.curve_timer = CURVE_TIME


def wall_bounce(boat: Boat):
    """둔치(좌/우 벽)에서 튕겨 나오게 한다."""
    half = RIVER_WIDTH * 0.5
    # 보트 AABB
    left  = boat.pos.x - BOAT_WID/2
    right = boat.pos.x + BOAT_WID/2

    bounced = False

    # 좌측 벽
    if left < -half:
        boat.pos.x = -half + BOAT_WID/2 + SEPARATION_EPS
        _reflect_with_normal(boat, pygame.Vector2(1, 0))
        bounced = True

    # 우측 벽
    if right > half:
        boat.pos.x = half - BOAT_WID/2 - SEPARATION_EPS
        _reflect_with_normal(boat, pygame.Vector2(-1, 0))
        bounced = True

    return bounced
