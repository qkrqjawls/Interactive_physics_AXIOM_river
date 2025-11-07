import random
from .config import RIVER_WIDTH, RIVER_LENGTH
from .entities import Obstacle, Coin, Dock

def random_positions_avoiding(avoid_boxes, margin=6.0):
    tries=0
    while True:
        tries+=1
        x=random.uniform(-RIVER_WIDTH*0.48,RIVER_WIDTH*0.48)
        z=random.uniform(8.0,RIVER_LENGTH-16.0)
        ax0,az0,ax1,az1=x-0.5,z-0.5,x+0.5,z+0.5
        ok=True
        for (x0,z0,x1,z1) in avoid_boxes:
            if not (ax1+margin<x0 or ax0-margin>x1 or az1+margin<z0 or az0-margin>z1):
                ok=False; break
        if ok: return x,z
        if tries>4000: return 0.0,RIVER_LENGTH*0.5

def build_scene():
    obstacles=[Obstacle(-10.0,RIVER_LENGTH*0.42,8.0,5.0,2.0),
               Obstacle(+12.0,RIVER_LENGTH*0.22,10.0,3.0,1.6),
               Obstacle(+2.0, RIVER_LENGTH*0.66,6.0,4.0,1.6)]
    avoid=[o.aabb() for o in obstacles]
    coins=[]
    for _ in range(6):
        x,z=random_positions_avoiding(avoid,6.0); coins.append(Coin(x,z,0.9))
    dock=Dock(0.0,3.0,14.0,3.0)
    return obstacles, coins, dock
