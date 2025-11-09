import math, pygame
from .config import (
    DRAG_X, DRAG_Z, MAX_SPEED_HARD, MAX_STEER_ACCEL, CURVE_TIME, CURVE_ACCEL,
    BOAT_LEN, BOAT_WID, BOAT_HGT
)
from .lanes import river_flow_vx

class Boat:
    def __init__(self, x, z):
        self.pos = pygame.Vector2(x, z)
        self.vel = pygame.Vector2(0, 0)
        self.heading = -90
        self.stun_timer = 0.0
        self.has_target = False
        self.vel_target = pygame.Vector2(0, 0)
        self.curve_timer = 0.0
        self.curve_dir = pygame.Vector2(0, 0)
        self.recovery_timer = 0.0
        self.started = False
        self.launch_speed = 12.0
        self.trace = []
        self.last_throttle = 0.0

    def forward_vec(self):
        th = math.radians(self.heading)
        return pygame.Vector2(math.cos(th), math.sin(th))

    def set_initial(self):
        self.vel = self.forward_vec() * self.launch_speed
        self.started = True

    def apply_thrust(self, thrust, dt):
        if abs(thrust) < 1e-6: return
        self.vel += self.forward_vec() * (thrust * dt)
        spd = self.vel.length()
        if spd > MAX_SPEED_HARD:
            self.vel.scale_to_length(MAX_SPEED_HARD)

    def update(self, dt):
        if self.recovery_timer > 0: self.recovery_timer = max(0, self.recovery_timer - dt)
        if self.stun_timer > 0: self.stun_timer = max(0, self.stun_timer - dt)

        if self.recovery_timer <= 0 and self.has_target:
            delta = self.vel_target - self.vel
            dlen = delta.length()
            if dlen > 1e-6:
                max_dv = MAX_STEER_ACCEL * dt
                if dlen > max_dv: delta.scale_to_length(max_dv)
                self.vel += delta
            if dlen < 0.2: self.has_target = False

        if self.curve_timer > 0:
            u = max(0, min(1, self.curve_timer / CURVE_TIME))
            ease = u*u
            self.vel += self.curve_dir * (CURVE_ACCEL * ease * dt)
            self.curve_timer = max(0, self.curve_timer - dt)

        flow = river_flow_vx(self.pos.y)
        v_rel_x = self.vel.x - flow
        v_rel_z = self.vel.y
        self.vel.x -= v_rel_x * DRAG_X * dt
        self.vel.y -= v_rel_z * DRAG_Z * dt
        self.vel.x += flow * dt

        self.pos += self.vel * dt

        if not self.trace or (self.trace[-1]-self.pos).length_squared()>1.5:
            self.trace.append(self.pos.copy())
            if len(self.trace)>300: self.trace.pop(0)

    def adjust_angle(self, delta_deg):
        self.heading += delta_deg
        if self.has_target and self.vel_target.length() > 1e-6:
            sp = self.vel_target.length()
            self.vel_target = self.forward_vec() * sp

def boat_aabb(boat: Boat):
    return (boat.pos.x-BOAT_WID/2, boat.pos.y-BOAT_LEN/2,
            boat.pos.x+BOAT_WID/2, boat.pos.y+BOAT_LEN/2)

class Obstacle:
    def __init__(self, x, z, w, l, h=1.2):
        self.x, self.z, self.w, self.l, self.h = x, z, w, l, h
    def aabb(self):
        return (self.x-self.w/2, self.z-self.l/2, self.x+self.w/2, self.z+self.l/2)

class Coin:
    def __init__(self, x, z, r=0.9):
        self.x, self.z, self.r = x, z, r
        self.alive = True

class Dock:
    def __init__(self, x, z, w, l):
        self.x, self.z, self.w, self.l = x, z, w, l
    def aabb(self):
        return (self.x-self.w/2, self.z-self.l/2, self.x+self.w/2, self.z+self.l/2)
