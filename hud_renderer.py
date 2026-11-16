"""AEGIS visor: procedural, antialiased optical instrumentation.

All art is original geometry. The central aperture has zero alpha, except for
the optional reticle. Static glass/armor is cached; small moving instruments are
composited over it. No desktop capture, game assets or sensor readings are used.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reticles import render_reticle
from terrain_scanner import CaveScanner
from signal_bus import SignalBus

PALETTES = {
    'blue': ((66, 218, 255), (161, 113, 255), (220, 249, 255)),
    'red': ((255, 79, 105), (255, 179, 77), (255, 229, 226)),
    'yellow': ((255, 202, 76), (86, 219, 244), (255, 247, 214)),
    'green': ((67, 241, 174), (88, 175, 255), (223, 255, 240)),
}

@dataclass(frozen=True)
class HUDConfig:
    theme: str = 'blue'
    density: int = 2
    deep: bool = True
    crosshair: bool = True
    motion: bool = True
    brightness: float = .9
    reticle_style: str = 'cross'
    reticle_scale: float = 1.0
    reticle_motion: bool = False

@dataclass
class HUDState:
    clock: str = '25:00'
    stage: str = 'STANDBY'
    goal: str = '准备执行下一次行动'
    progress: float = 0.0
    points: int = 0
    rank: str = '黄阶 · 见习'
    elapsed: str = '00:00'
    local_time: str = '00:00:00'
    difficulty: str = '标准'
    chapter: str = '自由任务'
    boot: float = 10.0

def rgba(rgb, alpha=255):
    return (*rgb[:3], max(0, min(255, int(alpha))))

def mix(a, b, t):
    return tuple(int(x+(y-x)*t) for x, y in zip(a[:3], b[:3]))

@lru_cache(maxsize=120)
def font(size, kind='mono'):
    names = {'mono':'consola.ttf', 'bold':'consolab.ttf', 'display':'bahnschrift.ttf', 'cn':'msyh.ttc'}
    path = Path('C:/Windows/Fonts') / names[kind]
    return ImageFont.truetype(str(path), max(7, size))

class Pen:
    """Draw in 1920-wide design coordinates, at an arbitrary raster scale."""
    def __init__(self, image, scale=1, details=None):
        self.im, self.s = image, scale
        self.d = ImageDraw.Draw(image)
        self.details = ImageDraw.Draw(details) if details is not None else self.d

    def ink(self, color):
        # On static surfaces, luminous ink belongs OVER the tinted glass. Drawing
        # low-alpha strokes into the glass would instead cut bright holes in it.
        return self.details if color is not None and sum(color[:3])>150 else self.d

    def pts(self, points): return [(round(x*self.s), round(y*self.s)) for x,y in points]
    def line(self, points, fill, width=1):
        self.ink(fill).line(self.pts(points), fill=fill, width=max(1, round(width*self.s)), joint='curve')
    def poly(self, points, fill, outline=None, width=1):
        p = self.pts(points)
        if fill is not None: self.ink(fill).polygon(p, fill=fill)
        if outline: self.ink(outline).line(p+[p[0]], fill=outline, width=max(1, round(width*self.s)), joint='curve')
    def rect(self, box, fill=None, outline=None, width=1):
        coords=tuple(round(v*self.s) for v in box)
        if fill is not None:self.ink(fill).rectangle(coords,fill=fill)
        if outline:self.ink(outline).rectangle(coords,outline=outline,width=max(1,round(width*self.s)))
    def ellipse(self, box, fill=None, outline=None, width=1):
        coords=tuple(round(v*self.s) for v in box)
        if fill is not None:self.ink(fill).ellipse(coords,fill=fill)
        if outline:self.ink(outline).ellipse(coords,outline=outline,width=max(1,round(width*self.s)))
    def arc(self, x, y, r, start, end, fill, width=1):
        self.ink(fill).arc(tuple(round(v*self.s) for v in (x-r,y-r,x+r,y+r)), start, end, fill=fill, width=max(1, round(width*self.s)))
    def text(self, x, y, value, fill, size=11, kind='mono', anchor='la'):
        self.details.text((round(x*self.s), round(y*self.s)), str(value), font=font(round(size*self.s), kind), fill=fill, anchor=anchor)
    def fitted(self, x, y, value, fill, max_width, size=13, kind='cn', anchor='la'):
        f = font(round(size*self.s), kind)
        value = str(value)
        if f.getlength(value) > max_width*self.s:
            while value and f.getlength(value+'…') > max_width*self.s: value = value[:-1]
            value += '…'
        self.text(x, y, value, fill, size, kind, anchor)
    def cut_panel(self, x, y, w, h, fill, outline, cut=14):
        self.poly([(x+cut,y),(x+w,y),(x+w,y+h-cut),(x+w-cut,y+h),(x,y+h),(x,y+cut)],fill,outline)
    def cross(self, x, y, r, color):
        self.line([(x-r,y),(x+r,y)],color); self.line([(x,y-r),(x,y+r)],color)

class VisorRenderer:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.scale = width/1920
        self.h = height/self.scale
        self.config = None
        self.static = None
        self.glow = None
        self.build_count = 0
        self.cave = CaveScanner()
        self.signal_bus = SignalBus()
        self.random = random.Random(37)
        self.blips = [(self.random.uniform(.2,.8), self.random.uniform(0,math.tau)) for _ in range(8)]

    def configure(self, config):
        if config == self.config: return
        old=self.config
        self.config = config
        if old and (old.theme,old.density,old.deep)==(config.theme,config.density,config.deep):return
        self.primary, self.secondary, self.white = PALETTES[config.theme]
        self.dim = mix(self.primary, (9,22,36), .68)
        self.side = 286 if config.deep else 205
        self.build_static()

    def build_static(self):
        # Supersample the static engineering lines once, never every frame.
        s = self.scale*1.5
        im = Image.new('RGBA',(round(self.width*1.5),round(self.height*1.5)))
        glow = Image.new('RGBA',im.size)
        details = Image.new('RGBA',im.size)
        p, g = Pen(im,s,details), Pen(glow,s)
        h, side, cfg = self.h, self.side, self.config
        a,b,w = self.primary,self.secondary,self.white
        n=cfg.density
        # Tinted optical glass, fading smoothly before the central aperture.
        # It gives the projected widgets a common physical surface on white pages.
        fade_width=side+75 if cfg.deep else side+30
        for xx in range(fade_width):
            alpha=105*(1-xx/fade_width)**.85 if cfg.deep else 45*(1-xx/fade_width)
            p.line([(xx,0),(xx,h)],(3,12,25,int(alpha)))
            p.line([(1920-xx,0),(1920-xx,h)],(3,12,25,int(alpha)))
        if n>=2:
            # Faint hex-cell substrate, restricted to the peripheral glass.
            for mirrored in [False,True]:
                for row in range(int(h/28)):
                    for col in range(6 if cfg.deep else 4):
                        cx=36+col*33+(16 if row%2 else 0);cy=210+row*28
                        if cy>h-190:continue
                        points=[(cx+18*math.cos(math.pi/3*k),cy+18*math.sin(math.pi/3*k)) for k in range(7)]
                        if mirrored:points=[(1920-x,y) for x,y in points]
                        p.line(points,rgba(a,13))
        # Optical edge falloff; it fades to fully clear before the work aperture.
        rim = 26 if cfg.deep else 15
        for i in range(rim):
            p.rect((i,i,1920-i,h-i),outline=(2,7,16,int(125*(1-i/rim)**1.6)))
        # The upper/lower housings form a continuous visor, rather than 4 boxes.
        brow = [(0,0),(1920,0),(1920,94),(1814,94),(1767,124),(1480,124),
                (1418,69),(1166,69),(1126,91),(794,91),(754,69),(502,69),
                (440,124),(153,124),(106,94),(0,94)]
        p.poly(brow,(5,12,25,224),rgba(a,60))
        p.poly([(0,0),(1920,0),(1920,35),(1490,35),(1448,50),(1170,50),
                (1136,67),(784,67),(750,50),(472,50),(430,35),(0,35)],(13,25,44,232))
        jaw = [(0,h),(1920,h),(1920,h-87),(1804,h-87),(1768,h-117),
               (1505,h-117),(1433,h-74),(1180,h-74),(1138,h-105),
               (782,h-105),(740,h-74),(487,h-74),(415,h-117),(152,h-117),(112,h-87),(0,h-87)]
        p.poly(jaw,(4,10,22,225),rgba(a,80))
        # Faceted temple/cheek pieces with small metallic insets.
        for mirror in [False, True]:
            def tr(points): return [(1920-x if mirror else x,y) for x,y in points]
            p.poly(tr([(0,94),(99,94),(154,132),(side-23,132),(side+15,181),
                       (side-13,204),(80,177),(44,218),(44,h-248),(93,h-206),
                       (side-27,h-206),(side+14,h-162),(side-2,h-127),(153,h-127),
                       (107,h-95),(0,h-95)]),(7,15,30,190),rgba(a,55))
            p.poly(tr([(0,104),(68,104),(112,140),(side-34,150),(side-12,176),
                       (72,157),(23,211),(23,h-241),(74,h-192),(side-24,h-184),
                       (side-10,h-157),(95,h-170),(57,h-126),(0,h-120)]),(19,33,51,205))
            paths = [([(18,94),(91,94),(137,126),(side-20,126),(side+23,179)],a),
                     ([(11,117),(58,117),(104,153),(side-31,164)],b),
                     ([(18,h-97),(105,h-97),(154,h-132),(side-10,h-132),(side+25,h-177)],a),
                     ([(4,h-123),(59,h-123),(95,h-160),(side-18,h-175)],b)]
            for points,col in paths:
                p.line(tr(points),rgba(col,225),1.5)
                g.line(tr(points),rgba(col,160),4)
            # Machined vents and fasteners are distinct from projected optics.
            for yy in [113,h-143]:
                for j in range(7): p.line(tr([(24+j*6,yy),(34+j*6,yy+13)]),(55,74,95,210),2)
            for xx,yy in [(18,75),(72,115),(32,h-151),(175,h-141)]:
                x=1920-xx if mirror else xx
                p.ellipse((x-4,yy-4,x+4,yy+4),fill=(4,10,19,230),outline=(61,86,106,200))
                p.line([(x-2,yy),(x+2,yy)],(82,109,130,220))
            # Segmented vertical optical rail.
            x = 18 if not mirror else 1902
            for j in range(40):
                yy=223+j*(h-465)/40
                length=10 if j%5==0 else 5
                p.line([(x,yy),(x+(length if not mirror else -length),yy)],rgba(a,180 if j%5==0 else 75))
            p.line(tr([(35,246),(35,h-265)]),rgba(a,70))
            p.line(tr([(41,266),(41,h-285)]),rgba(b,38))
        # Brow accent traces converge on the central optical marker.
        for points in [[(280,18),(451,18),(483,45),(736,45),(778,77),(885,77)],
                       [(1640,18),(1469,18),(1437,45),(1184,45),(1142,77),(1035,77)]]:
            p.line(points,rgba(a,210),1.3); g.line(points,rgba(a,150),3)
        p.poly([(943,81),(977,81),(960,99)],(0,0,0,0),rgba(a,230),1.5)
        p.line([(953,83),(960,90),(967,83)],rgba(b,220))
        # Logo, callsign and system identifier.
        p.poly([(42,29),(58,20),(74,29),(74,47),(58,56),(42,47)],(8,26,39,220),rgba(a,230))
        p.line([(49,45),(58,29),(67,45),(62,45),(58,38),(54,45)],rgba(w,240),2)
        p.text(89,22,'A E G I S',rgba(w,250),25,'display')
        p.text(91,55,'MK.IV  /  COGNITIVE OPERATIONS',rgba(a,190),9)
        p.text(48,84,'OPTICAL ARRAY  //  01',rgba(a,160),10)
        p.text(1870,21,'F O C U S   / /   F I E L D',rgba(w,240),17,'display','ra')
        p.text(1870,48,'PERSONAL MISSION INTERFACE',rgba(a,180),9,'mono','ra')
        if n>=1:
            p.text(309,84,'N-04  /  OPTICAL BUS',rgba(a,135),8)
            p.text(1611,84,'SYSTEM ARMED  /  MANUAL',rgba(a,135),8,anchor='ra')
            for mirrored in [False,True]:
                for k in range(5):
                    xx=330+k*26
                    pts=[(xx,58),(xx+17,58),(xx+13,63),(xx-4,63)]
                    if mirrored:pts=[(1920-x,y) for x,y in pts]
                    p.poly(pts,rgba(a,70+k*25))
        # Compass is an optical ornament, deliberately not a real sensor reading.
        for i in range(49):
            x=768+i*8
            y=27 if i%6==0 else 33
            p.line([(x,y),(x,42)],rgba(a,170 if i%6==0 else 75))
            if i%12==0: p.text(x,14,f'{(i-24)*3:+03}',rgba(a,140),8,anchor='ma')
        p.line([(960,20),(960,48)],rgba(w,230),2)
        p.text(960,50,'HUMAN IN CONTROL',rgba(a,200),9,anchor='ma')
        # Upper split information plates; shallow mode keeps these narrow.
        p.cut_panel(56,146,side-49,56,(4,13,26,180),rgba(a,75),10)
        p.text(70,156,'VISOR LINK',rgba(w,230),12,'bold')
        p.text(70,177,'LOCAL / ENCRYPTED',rgba(a,165),9)
        p.rect((side-20,159,side-15,164),fill=rgba(a,240))
        # Lower identity/chapter plates and the central mission dock.
        p.text(58,h-77,'OPERATOR  /  001',rgba(a,180),9)
        p.text(58,h-28,'FOCUS // FIELD     •     AEGIS SYSTEMS',rgba(a,110),8)
        p.text(1864,h-28,'DECORATIVE TELEMETRY / SIM',rgba(a,110),8,anchor='ra')
        p.cut_panel(744,h-85,432,68,(5,13,26,225),rgba(a,70),13)
        p.text(766,h-75,'CURRENT DIRECTIVE',rgba(a,180),9)
        p.line([(757,h-29),(1162,h-29)],rgba(a,60))
        for j in range(6):
            p.poly([(688+j*7,h-43),(692+j*7,h-47),(695+j*7,h-47),(691+j*7,h-43)],rgba(a,90+j*22))
            p.poly([(1232-j*7,h-43),(1228-j*7,h-47),(1225-j*7,h-47),(1229-j*7,h-43)],rgba(a,90+j*22))
        # Large curvature at the chin evokes a wraparound helmet lens.
        for offset,alpha in [(0,125),(7,40)]:
            pts=[]
            for i in range(101):
                x=330+i*12.6
                y=h-37-42*(1-((x-960)/630)**2)-offset
                pts.append((x,y))
            # Keep the mission dock legible by splitting the arc.
            p.line(pts[:31],rgba(b,alpha),1.3); p.line(pts[70:],rgba(b,alpha),1.3)
        # The instrument pods: reduced detail still keeps a designed silhouette.
        self.left_x=55
        self.pod_width=side-50
        self.radar_y=max(350,h*.355)
        self.globe_y=max(400,h*.425)
        self.radius=min(94,(self.pod_width-22)/2)
        self.right_x=1920-side-3
        if n>=1:
            x=self.left_x; pw=self.pod_width; y=self.radar_y-self.radius-44
            p.cut_panel(x,y,pw,self.radius*2+83,(3,14,26,183),rgba(a,70))
            p.text(x+14,y+12,'01 / TACTICAL ARRAY',rgba(w,220),10,'bold')
            p.line([(x+14,y+33),(x+pw-14,y+33)],rgba(a,50))
            cx=x+pw/2; cy=self.radar_y
            for r in [self.radius*.3,self.radius*.62,self.radius]: p.ellipse((cx-r,cy-r,cx+r,cy+r),outline=rgba(a,75))
            for deg in range(0,360,5):
                rad=math.radians(deg); r=self.radius
                end=r+(7 if deg%30==0 else 3)
                p.line([(cx+math.cos(rad)*r,cy+math.sin(rad)*r),(cx+math.cos(rad)*end,cy+math.sin(rad)*end)],rgba(a,170 if deg%30==0 else 70))
            p.cross(cx,cy,8,rgba(w,160))
            for deg in range(0,360,90):
                rad=math.radians(deg);r=self.radius*.72
                p.line([(cx+math.cos(rad)*12,cy+math.sin(rad)*12),(cx+math.cos(rad)*r,cy+math.sin(rad)*r)],rgba(a,40))
            p.text(x+14,cy+self.radius+18,'SECTOR 07',rgba(a,170),9)
            p.text(x+pw-14,cy+self.radius+18,'SIM',rgba(b,190),9,anchor='ra')
            # Right sphere frame, asymmetric to the scanner on the left.
            x=self.right_x;y=self.globe_y-self.radius-48
            p.cut_panel(x,y,pw,self.radius*2+98,(4,12,29,190),rgba(b,90))
            p.text(x+14,y+12,'02 / FOCUS CORE',rgba(w,230),10,'bold')
            cx=x+pw/2;cy=self.globe_y
            p.arc(cx,cy,self.radius+7,15,150,rgba(a,130),2)
            p.arc(cx,cy,self.radius+7,195,330,rgba(b,180),2)
            for dx in [-1,1]:
                xx=cx+dx*(self.radius+13)
                p.line([(xx,cy-18),(xx,cy+18)],rgba(a,200))
                p.line([(xx,cy),(xx+dx*7,cy)],rgba(a,200))
            p.text(x+14,cy+self.radius+27,'RESERVE',rgba(a,170),9)
            p.text(x+pw-14,cy+self.radius+27,'SESSION',rgba(b,170),9,anchor='ra')
        # Lower pods: rich data typography, traces and a projection map.
        self.signal_y=h-388
        self.terrain_y=h-345
        self.buffer_y=self.radar_y+self.radius+54
        self.reserve_y=self.globe_y+self.radius+63
        self.has_aux=(n>=2 and self.signal_y-self.buffer_y>=132 and self.terrain_y-self.reserve_y>=101)
        if self.has_aux:
            # Secondary instrument trays tie the large instruments together.
            x=self.left_x;pw=self.pod_width;y=self.buffer_y
            p.cut_panel(x,y,pw,118,(4,13,26,190),rgba(a,50),8)
            p.text(x+14,y+12,'EXECUTION BUFFER',rgba(a,190),9,'bold')
            p.line([(x+14,y+32),(x+pw-14,y+32)],rgba(a,45))
            for j,label in enumerate(['ELAPSED','RECORD','PRIORITY']):
                p.text(x+14,y+45+j*21,label,rgba(a,145),8)
            x=self.right_x;y=self.reserve_y
            p.cut_panel(x,y,pw,87,(4,13,26,190),rgba(a,50),8)
            p.text(x+14,y+12,'MISSION CAPACITY',rgba(a,180),9,'bold')
            p.text(x+14,y+63,'TIME REMAINING',rgba(a,130),8)
        if n>=2 and h>=900:
            x=self.left_x; y=self.signal_y; pw=self.pod_width
            p.cut_panel(x,y,pw,172,(4,13,26,185),rgba(a,65))
            p.text(x+14,y+13,'03 / SIGNAL BUS',rgba(w,220),10,'bold')
            for j in range(3):
                yy=y+47+j*25
                p.text(x+13,yy-5,['A','B','C'][j],rgba(a,150),9)
                p.line([(x+30,yy+2),(x+pw-14,yy+2)],rgba(a,30))
            p.text(x+14,y+142,'LINK / SIM',rgba(a,160),8)
            p.text(x+pw-14,y+142,'3 CHANNELS',rgba(b,180),8,anchor='ra')
            x=self.right_x;y=self.terrain_y
            p.cut_panel(x,y,pw,134,(4,13,26,190),rgba(a,65))
            p.text(x+14,y+12,'04 / EXTRACTION GRID',rgba(w,220),9,'bold')
            p.text(x+14,y+112,'CAVE / SIM',rgba(a,170),8)
            p.text(x+pw-14,y+112,'E-07',rgba(b,220),8,anchor='ra')
        # Thin inward lens rails leave a large rectangular aperture untouched.
        if cfg.deep:
            for mirrored in [False,True]:
                xx=side+35
                points=[(xx+40,208),(xx,240),(xx,318)]
                lower=[(xx,h-322),(xx,h-255),(xx+40,h-220)]
                for pts in [points,lower]:
                    if mirrored: pts=[(1920-x,y) for x,y in pts]
                    p.line(pts,rgba(a,95));g.line(pts,rgba(a,80),2)
                # Floating collimator scale: sparse ticks bend with the visor.
                for i in range(17):
                    yy=h*.36+i*(h*.28/16)
                    xx=side+30-13*math.sin(i/16*math.pi)
                    length=9 if i%4==0 else 4
                    if mirrored:xx=1920-xx;length=-length
                    p.line([(xx,yy),(xx+length,yy)],rgba(a,100 if i%4==0 else 45))
                    if i in (0,8,16):p.text(xx+(15 if not mirrored else -15),yy-4,f'{8-i:+02}',rgba(a,100),7,anchor='la' if not mirrored else 'ra')
        # Technical microstructure is confined to the physical rim.
        if n>=1:
            for mirrored in [False,True]:
                for i in range(22):
                    x=326+i*8
                    if mirrored:x=1920-x
                    p.line([(x,11),(x+3,15)],rgba(a,75+i%4*25))
                for j in range(30):
                    x=346+j*8
                    if mirrored:x=1920-x
                    p.rect((x,h-16,x+3,h-11),fill=rgba(a,110 if j%5 else 200))
        if n>=2:
            # Long technical traces at the bottom edge, with contact pads.
            for mirrored in [False,True]:
                for j in range(3):
                    pts=[(481,h-57+j*7),(564,h-57+j*7),(583,h-39+j*7),(665,h-39+j*7)]
                    if mirrored:pts=[(1920-x,y) for x,y in pts]
                    p.line(pts,rgba(a,70+j*25))
                    xx,yy=pts[-1];p.ellipse((xx-2,yy-2,xx+2,yy+2),outline=rgba(a,150))
        # Bloom is computed once. Keep all alpha real, including the glass.
        glow=glow.filter(ImageFilter.GaussianBlur(6*s))
        im.alpha_composite(glow)
        im.alpha_composite(details)
        self.static=im.resize((self.width,self.height),Image.Resampling.LANCZOS)
        self.build_count+=1

    def draw_reticle(self, p, t):
        if not self.config.crosshair: return
        tile=render_reticle(self.config.reticle_style,self.primary,self.secondary,self.white,
                            self.config.reticle_scale,t,self.config.reticle_motion and self.config.motion)
        if self.scale!=1:
            size=max(2,round(tile.width*self.scale/2)*2)
            tile=tile.resize((size,size),Image.Resampling.LANCZOS)
        p.im.alpha_composite(tile,((self.width-tile.width)//2,(self.height-tile.height)//2))

    def draw_radar(self, p, t):
        cfg=self.config
        if cfg.density<1:return
        a,b,w=self.primary,self.secondary,self.white
        cx=self.left_x+self.pod_width/2;cy=self.radar_y;r=self.radius
        phase=(t*.42)%math.tau
        # A fan of light with a decaying trailing edge.
        for j in range(28):
            angle=phase-j*.018
            p.line([(cx,cy),(cx+(r-3)*math.cos(angle),cy+(r-3)*math.sin(angle))],rgba(a,65*(1-j/28)**1.7),1.4)
        p.line([(cx,cy),(cx+(r-2)*math.cos(phase),cy+(r-2)*math.sin(phase))],rgba(w,190),1.4)
        for i,(dist,angle) in enumerate(self.blips[:5 if cfg.density==1 else 8]):
            x=cx+dist*r*math.cos(angle);y=cy+dist*r*math.sin(angle)
            trail=(phase-angle)%math.tau
            opacity=55+190*math.exp(-trail*1.3)
            col=b if i%3==0 else a
            p.poly([(x,y-3),(x+3,y),(x,y+3),(x-3,y)],rgba(col,opacity))
            if i in (0,3):
                p.line([(x+5,y-5),(x+10,y-11),(x+23,y-11)],rgba(col,opacity*.6))
                p.text(x+11,y-21,f'{i+1:02}',rgba(col,opacity),7)
        for start in [t*7,180+t*7]: p.arc(cx,cy,r+11,start,start+45,rgba(b,190),2)

    def draw_globe(self,p,t,progress):
        if self.config.density<1:return
        a,b,w=self.primary,self.secondary,self.white
        cx=self.right_x+self.pod_width/2;cy=self.globe_y;r=self.radius*.77
        tilt=.36;rotation=t*.16
        def project(lat,lon):
            x=math.cos(lat)*math.sin(lon+rotation)
            z=math.cos(lat)*math.cos(lon+rotation)
            y=math.sin(lat)
            yy=y*math.cos(tilt)-z*math.sin(tilt)
            zz=y*math.sin(tilt)+z*math.cos(tilt)
            return cx+x*r,cy+yy*r,zz
        for latitude in range(-60,61,20):
            points=[project(math.radians(latitude),j*math.tau/64) for j in range(65)]
            for j in range(64):
                p.line([points[j][:2],points[j+1][:2]],rgba(a,65+int(105*max(0,points[j][2]))))
        for longitude in range(0,360,30):
            points=[project(-math.pi/2+j*math.pi/40,math.radians(longitude)) for j in range(41)]
            for j in range(40):
                p.line([points[j][:2],points[j+1][:2]],rgba(a,45+int(110*max(0,points[j][2]))))
        # Orbital arcs and a satellite marker are decoration, reserve is real.
        p.arc(cx,cy,r+9,30-t*9,152-t*9,rgba(b,230),2)
        p.arc(cx,cy,r+9,210-t*9,332-t*9,rgba(a,160))
        ang=-t*.16
        x=cx+(r+9)*math.cos(ang);y=cy+(r+9)*math.sin(ang)
        p.ellipse((x-3,y-3,x+3,y+3),fill=rgba(w,230))
        # A dark central tile guarantees legibility over the wireframe.
        p.cut_panel(cx-37,cy-17,74,35,(3,12,24,218),rgba(a,120),5)
        p.text(cx,cy-13,f'{round((1-progress)*100):02d}%',rgba(w,250),22,'display','ma')

    def draw_signal(self,p,t):
        if self.config.density<2 or self.h<900:return
        x=self.left_x;y=self.signal_y;pw=self.pod_width
        a,b=self.primary,self.secondary
        samples,fraction=self.signal_bus.frame(t)
        span=pw-48
        for channel in range(3):
            color=b if channel==1 else a
            baseline=y+49+channel*25
            # Subpixel scrolling uses fixed historical samples, not rerolled noise.
            pts=[]
            for j,row in enumerate(samples):
                position=(j-fraction)/self.signal_bus.WINDOW
                if not 0<=position<=1:continue
                pts.append((x+31+position*span,baseline-row[channel]*11))
            for j in range(1,len(pts)):
                strength=65+165*j/(len(pts)-1)
                p.line(pts[j-1:j+1],rgba(color,strength),1.15)
            xx,yy=pts[-1]
            p.ellipse((xx-1.4,yy-1.4,xx+1.4,yy+1.4),fill=rgba(self.white,240))
            for j in range(1,6):
                xx=x+31+j*span/6
                p.line([(xx,baseline-9),(xx,baseline+9)],rgba(a,22))
        for j,level in enumerate(self.signal_bus.levels(samples)):
            xx=x+14+j*(pw-28)/25
            height=2+min(15,level*32)
            p.rect((xx,y+131-height,xx+max(1,(pw-28)/25-2),y+131),fill=rgba(a,100+level*200))
            p.line([(xx,y+131-height),(xx+max(1,(pw-28)/25-2),y+131-height)],rgba(b,200))

    def draw_terrain(self,p,t):
        if self.config.density<2 or self.h<900:return
        x=self.right_x;y=self.terrain_y;pw=self.pod_width
        tile=self.cave.render((max(1,round((pw-16)*self.scale)),round(80*self.scale)),
                              t,self.primary,self.secondary)
        p.im.alpha_composite(tile,(round((x+8)*self.scale),round((y+29)*self.scale)))

    def draw_status(self,p,state,t):
        a,b,w=self.primary,self.secondary,self.white
        h=self.h;side=self.side
        # The large countdown is the hero readout, in its own quiet bay.
        x=1920-side-3;pw=self.pod_width
        p.cut_panel(x,146,pw,100,(4,12,25,222),rgba(a,100),13)
        p.text(x+14,156,'EXTRACTION / T-MINUS',rgba(a,180),9)
        p.text(x+pw/2,172,state.clock,rgba(w,255),38 if self.config.deep else 30,'display','ma')
        p.text(x+pw/2,220,state.stage,rgba(b if state.stage in ('PAUSED','EXTRACTION READY') else a,240),8,'bold','ma')
        # Real session progress across a segmented top strip.
        for j in range(24):
            xx=771+j*14.9
            col=rgba(a,235) if j/24<state.progress else rgba(a,45)
            p.poly([(xx,103),(xx+10,103),(xx+7,107),(xx-3,107)],col)
        p.text(746,99,'IN',rgba(a,120),8,anchor='ra')
        p.text(1176,99,'OUT',rgba(a,120),8)
        # Helmet-side moving light packets (slow, no blinking or random jumps).
        if self.config.density>=1:
            for mirrored in [False,True]:
                x=35 if not mirrored else 1885
                yy=265+(t*24)%(h-560)
                p.line([(x,yy),(x,yy+34)],rgba(a,220),2)
                p.ellipse((x-2,yy+32,x+2,yy+36),fill=rgba(w,240))
        # Real operator state and mission briefing label.
        p.fitted(58,h-59,state.rank,rgba(w,240),320,15)
        p.text(350,h-57,f'{state.points:05d} XP',rgba(a,240),14,'display')
        p.fitted(766,h-55,state.goal,rgba(w,245),386,14)
        p.text(960,h-25,'FOCUS ACTIVE' if state.stage=='MISSION ACTIVE' else state.stage,rgba(a,155),8,anchor='ma')
        p.text(1864,h-79,state.local_time,rgba(w,230),23,'display','ra')
        p.text(1864,h-49,f'ELAPSED  {state.elapsed}',rgba(a,180),10,'mono','ra')
        p.text(1455,h-55,'MISSION',rgba(a,130),8)
        p.fitted(1455,h-41,state.difficulty,rgba(w,220),105,11)
        if self.config.density>=1:
            p.text(66,h-185,'ARCHIVE / CURRENT CHAPTER',rgba(a,130),8)
            p.fitted(66,h-166,state.chapter,rgba(w,205),side-67,11)
            # Lateral labels sit on the rim, not in the central clear area.
            p.text(1920-side+12,h-179,'OPTICS ONLINE',rgba(a,150),9)
            p.text(1920-side+12,h-162,'INPUT PASSTHROUGH',rgba(a,100),8)
        if self.has_aux:
            x=self.left_x;y=self.buffer_y;pw=self.pod_width
            p.text(x+pw-14,y+43,state.elapsed,rgba(w,235),11,'bold','ra')
            p.text(x+pw-14,y+64,f'{state.points:05d} XP',rgba(w,220),10,'mono','ra')
            p.text(x+pw-14,y+83,state.difficulty,rgba(b,230),10,'cn','ra')
            x=self.right_x;y=self.reserve_y
            for j in range(20):
                xx=x+14+j*(pw-28)/20
                col=rgba(a,220) if j/20<1-state.progress else rgba(a,40)
                p.poly([(xx,y+38),(xx+5,y+38),(xx+3,y+51),(xx-2,y+51)],col)
            p.text(x+pw-14,y+61,f'{round((1-state.progress)*100)}%',rgba(w,230),10,'bold','ra')

    def render(self,config,state,t):
        self.configure(config)
        # Composite moving light over glass; don't punch low-alpha holes into it.
        dynamic=Image.new('RGBA',(self.width,self.height))
        p=Pen(dynamic,self.scale)
        phase=t if config.motion else 7.25
        self.draw_radar(p,phase)
        self.draw_globe(p,phase,max(0,min(1,state.progress)))
        self.draw_signal(p,phase)
        self.draw_terrain(p,phase)
        self.draw_status(p,state,phase)
        self.draw_reticle(p,phase)
        # Boot sequence lights edge modules progressively; the work aperture stays clear.
        if config.motion and state.boot<2.4:
            a=self.primary
            q=min(1,state.boot/2.4)
            for mirrored in [False,True]:
                xx=26 if not mirrored else 1894
                end=80+(self.h-160)*q
                p.line([(xx,80),(xx,end)],rgba(a,220),2)
                p.line([(xx-8,end),(xx+8,end)],rgba(self.white,255),2)
            p.text(960,121,'VISOR CALIBRATION  /  '+f'{int(q*100):03d}%',rgba(a,200),10,anchor='ma')
        frame=self.static.copy()
        if config.density>=2:
            # Only two emissive instruments need animated bloom. Processing their
            # small bounds avoids resampling millions of fully clear pixels.
            for cx,cy in [(self.left_x+self.pod_width/2,self.radar_y),
                          (self.right_x+self.pod_width/2,self.globe_y)]:
                r=self.radius+22
                box=tuple(round(v*self.scale) for v in (cx-r,cy-r,cx+r,cy+r))
                bloom=dynamic.crop(box)
                original=bloom.size
                bloom=bloom.resize((max(1,original[0]//4),max(1,original[1]//4)),Image.Resampling.BILINEAR)
                bloom=bloom.filter(ImageFilter.GaussianBlur(1.8))
                bloom.putalpha(bloom.getchannel('A').point(lambda v:int(v*.7)))
                bloom=bloom.resize(original,Image.Resampling.BILINEAR)
                frame.alpha_composite(bloom,(box[0],box[1]))
        return Image.alpha_composite(frame,dynamic)

def preview_scene(width=1920,height=1080,dark=False):
    """Synthetic document backdrop for screenshots; never reads user content."""
    image=Image.new('RGBA',(width,height),(15,23,35,255) if dark else (222,227,233,255))
    p=Pen(image,width/1920);h=height/(width/1920)
    page=(25,35,48,255) if dark else (250,249,245,255)
    ink=(175,189,205,255) if dark else (53,65,77,255)
    muted=(91,112,136,255) if dark else (143,151,160,255)
    p.rect((430,135,1490,h-122),fill=page)
    p.text(510,188,'RESEARCH ARCHIVE    /    FIELD NOTES',muted,12)
    p.text(510,229,'Attention, immersion & the working mind',ink,31,'display')
    p.text(510,282,'A workspace for reading, writing and deep work.',muted,17,'display')
    p.line([(510,322),(1410,322)],muted)
    p.text(510,351,'01   A CLEAR WINDOW INTO YOUR WORK',ink,14,'bold')
    for column in [510,975]:
        for row in range(int((h-610)/24)):
            y=401+row*24
            length=385-((row*79)%105)
            p.line([(column,y),(column+length,y)],muted,2)
    p.text(960,h-178,'Your content stays here. The mission lives at the edge.',muted,15,'display','ma')
    return image

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='previews')
    args=parser.parse_args()
    folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    renderer=VisorRenderer(1920,1080)
    state=HUDState(clock='38:42',stage='MISSION ACTIVE',goal='提取核心观点，完成本轮研究记录',progress=.14,
                   points=360,rank='黄阶 · 精锐',elapsed='06:18',local_time='21:48:07',chapter='自由任务 / 深度研究')
    for theme in PALETTES:
        cfg=HUDConfig(theme=theme)
        frame=renderer.render(cfg,state,12.0)
        frame.save(folder/f'hud-{theme}-transparent.png')
        for dark in [False,True]:
            scene=preview_scene(dark=dark)
            scene.alpha_composite(frame)
            scene.convert('RGB').save(folder/f'hud-{theme}-{"dark" if dark else "light"}.jpg',quality=94)
