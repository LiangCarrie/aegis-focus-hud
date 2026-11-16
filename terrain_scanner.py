"""Small CPU-only, seeded cavern scanner. Coordinates are simulated, not sensors."""
import math
import random
from functools import lru_cache
from PIL import Image, ImageDraw

class CaveScanner:
    def __init__(self, seed=None):
        self.seed = random.randrange(2**30) if seed is None else seed

    def noise(self, index, channel=0):
        return random.Random(self.seed + index * 92821 + channel * 68917).uniform(-1, 1)

    def smooth(self, z, channel):
        k = math.floor(z / 22)
        f = z / 22 - k
        f = f*f*(3-2*f)
        return self.noise(k, channel)*(1-f) + self.noise(k+1, channel)*f

    def center(self, z):
        return (self.smooth(z, 1)*17, self.smooth(z, 2)*7, z)

    @lru_cache(maxsize=256)
    def section(self, index):
        z = index * 3
        x,y,_ = self.center(z)
        radius = 6 + (self.smooth(z, 3)+1)*4
        ring = []
        for j in range(8):
            angle = j*math.tau/8
            rough = 1 + self.noise(index, j+10)*.18
            ring.append((x+math.cos(angle)*radius*rough,
                         y+math.sin(angle)*radius*.65*rough,z))
        return tuple(ring)

    def render(self, size, t, primary, accent):
        # Fixed-size local target clips every line, including offscreen tunnels.
        width,height = size
        im = Image.new('RGBA',size)
        d = ImageDraw.Draw(im)
        z = t*2.4
        origin = self.center(z)
        ahead = self.center(z+5)
        yaw = .65 + math.atan2(ahead[0]-origin[0],5)*.3
        co,si = math.cos(yaw),math.sin(yaw)
        scale = min(width/155,height/65)
        def project(v):
            x,y,depth = (v[i]-origin[i] for i in range(3))
            horizontal = x*co+depth*si
            forward = depth*co-x*si
            return (width*.48+horizontal*scale,
                    height*.58-forward*.48*scale-y*scale)
        def line(points, color, weight=1):
            d.line([project(v) for v in points],fill=color,width=max(1,round(weight*scale)))
        first = math.floor(z/3)-20
        rings = [self.section(i) for i in range(first,first+42)]
        # Back-to-front translucent facets convey height without an opaque map.
        for j in range(len(rings)-2,-1,-1):
            distance = abs((first+j)*3-z)
            alpha = int(110*max(.12,1-distance/70))
            a,b = rings[j],rings[j+1]
            for k in range(8):
                q=(k+1)%8
                if k in (3,4,5):
                    d.polygon([project(v) for v in (a[k],b[k],b[q],a[q])],
                              fill=(*primary,int(alpha*.12)))
                line((a[k],b[k]),(*primary,alpha))
            line((*a,a[0]),(*primary,alpha+25))
        # Persistent side passages join the main route at stable world positions.
        for sector in range(math.floor((z-55)/30),math.floor((z+55)/30)+1):
            junction = sector*30
            if self.noise(sector,30)<-.25: continue
            start = self.center(junction)
            sign = 1 if self.noise(sector,31)>0 else -1
            branch=[]
            for step in range(7):
                branch.append((start[0]+sign*step*5,start[1]+math.sin(step*.5)*4,
                               junction+step*2))
            for offset in (-3,3):
                line([(x,y+offset,zz) for x,y,zz in branch],(*primary,75))
            for v in branch:
                line(((v[0],v[1]-3,v[2]),(v[0],v[1]+3,v[2])),(*primary,65))
            line(branch,(*accent,85))
        # Traveled path is dim; the forward route remains luminous and continuous.
        line([self.center(z+i) for i in range(-44,1,2)],(*accent,105),1.3)
        route=[self.center(z+i) for i in range(0,47,2)]
        line(route,(*accent,245),1.5)
        for distance in (12,28,44):
            x,y=project(self.center(z+distance))
            d.ellipse((x-2,y-2,x+2,y+2),outline=(*accent,220))
        x,y=project(origin)
        radius=7*scale
        d.ellipse((x-radius,y-radius,x+radius,y+radius),outline=(*primary,110))
        d.polygon([(x,y-4*scale),(x+3*scale,y+3*scale),(x,y+scale),
                   (x-3*scale,y+3*scale)],fill=(235,255,255,255))
        # Edge calibration marks stay attached to the instrument, not the world.
        for x in range(8,width-8,max(8,round(12*scale))):
            d.line((x,height-3,x,height-1),fill=(*primary,75))
        return im
