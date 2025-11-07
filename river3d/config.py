import math
# 수정수정

# ---- Window / timing ----
WIDTH, HEIGHT = 1280, 720
FPS = 60
STUN_TIME = 0.20  # 벽 충돌 후 잠깐 컨트롤 지연(초)

# ---- World ----
RIVER_LENGTH = 220.0
RIVER_WIDTH  = 60.0
LANE_COUNT   = 5
DEFAULT_SLOPE = 0.001

# ---- Gameplay ----
SECONDS_LIMIT = 20.0
COIN_TIME_BONUS = 5.0

# ---- Hydraulics drag (x=cross-stream, z=downstream) ----
DRAG_X = 0.12
DRAG_Z = 0.08

# ---- Boat ----
BOAT_LEN, BOAT_WID, BOAT_HGT = 3.0, 1.4, 0.6
ENGINE_THRUST   = 14.0
BRAKE_THRUST    = 8.0
TURN_RATE_DEG   = 120.0
MAX_SPEED_HARD  = 18.0 * 1.8   # TARGET_SPEED_MAX * 1.8

# ---- Bounce / steering ----
BOUNCE_RESTITUTION = 0.50
BOUNCE_DAMPING     = 0.90
TANGENT_BOOST      = 1.10
FRICTION_STATIC    = 0.60
FRICTION_DYNAMIC   = 0.40
TARGET_SPEED_MIN   = 7.0
TARGET_SPEED_MAX   = 18.0
FORWARD_SOFT_MIN_VZ = 4.5
MAX_BACK_BOUNCE_VZ  = 3.5
MAX_STEER_ACCEL     = 20.0
CURVE_TIME          = 0.8
CURVE_ACCEL         = 10.0
RECOVERY_DELAY      = 0.80

# ---- GL / Stability ----
GL_NEAR   = 0.5
GL_FAR    = 300.0
WATER_EPS = 0.002
SEPARATION_EPS = 0.05

# ---- UI toggles (defaults) ----
SHOW_MINIMAP = True
SHOW_PREDICT = True
USE_MOUSE_STEER = False

# ---- Markers ----
MARKERS = [m for m in range(100, int(RIVER_LENGTH)//100*100 + 1, 100)]

# ---- Colors (0..1) ----
WHITE=(1,1,1)
SHALLOW_WATER = (195/255,225/255,245/255)
DEEP_WATER    = (60/255,120/255,220/255)
COIN_COLOR = (245/255,170/255,30/255)
OBST_COLOR = (0.15,0.15,0.18)
DOCK_COLOR = (0.16,0.70,0.36)
BANK_COLOR = (0.2,0.45,0.25)
SKY_COLOR  = (210/255,230/255,245/255)
UI_BG_DARK = (22/255,26/255,32/255,0.90)

# ---- Predict ----
PREDICT_DT = 0.12
PREDICT_STEPS = 22

# ---- Lane tuning ----
LANE_TUNE_WINDOW = 2.0
