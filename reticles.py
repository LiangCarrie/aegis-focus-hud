"""Original optical reticles based on common dot/cross/ring/T/bracket shapes.

Small supersampled sprites keep the center stable and avoid re-rendering the
large visor when selecting a reticle. Decorative motion is explicitly opt-in.
"""
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageFilter

STYLES = {
    '精密十字': 'cross', '光子圆点': 'dot', '全息圆环': 'ring',
    '战术 T 型': 'tee', '棱镜菱形': 'diamond', '鹰眼尖括': 'chevron',
    '目标锁框': 'brackets', '轨道核心': 'orbit',
}

def render_reticle(style='cross', primary=(66,218,255), secondary=(161,113,255),
                   white=(220,249,255), size=1.0, t=0.0, animate=False):
    if style not in STYLES.values(): style='cross'
    scale=round(max(.6,min(1.6,float(size))),2)
    # 12 steps/second for the ornamental layer; the central geometry never moves.
    phase=round((t%60)*12)/12 if animate else 0
    return _sprite(style,tuple(primary),tuple(secondary),tuple(white),scale,phase)

@lru_cache(maxsize=96)
def _sprite(style,a,b,w,size,phase):
    edge=math.ceil(112*size)
    if edge%2:edge+=1
    ss=3
    dims=(edge*ss,edge*ss)
    shadow=Image.new('RGBA',dims)
    light=Image.new('RGBA',dims)
    sd,ld=ImageDraw.Draw(shadow),ImageDraw.Draw(light)
    factor=size*ss;center=edge*ss/2
    def pts(points):return [(round(center+x*factor),round(center+y*factor)) for x,y in points]
    def line(points,col=a,alpha=235,width=1.4):
        q=pts(points)
        sd.line(q,fill=(1,7,14,200),width=max(1,round((width+2)*factor)),joint='curve')
        ld.line(q,fill=(*col,alpha),width=max(1,round(width*factor)),joint='curve')
    def arc(r,start,end,col=a,alpha=220,width=1.3):
        box=(*pts([(-r,-r)])[0],*pts([(r,r)])[0])
        sd.arc(box,start,end,fill=(1,7,14,185),width=max(1,round((width+2)*factor)))
        ld.arc(box,start,end,fill=(*col,alpha),width=max(1,round(width*factor)))
    def dot(r=1.6):
        box=(*pts([(-r-1,-r-1)])[0],*pts([(r+1,r+1)])[0])
        sd.ellipse(box,fill=(1,7,14,215))
        box=(*pts([(-r,-r)])[0],*pts([(r,r)])[0])
        ld.ellipse(box,fill=(*w,250))
    def ticks(r,angles,length=4,col=a):
        for angle in angles:
            q=math.radians(angle)
            line([(r*math.cos(q),r*math.sin(q)),((r+length)*math.cos(q),(r+length)*math.sin(q))],col,190,1)
    if style=='cross':
        for angle in [0,90,180,270]:
            q=math.radians(angle)
            line([(9*math.cos(q),9*math.sin(q)),(23*math.cos(q),23*math.sin(q))])
        for angle in [45,135,225,315]:arc(29,angle-9,angle+9,b,145,1)
        dot(1.3)
    elif style=='dot':
        dot(2.4)
        for angle in [0,90,180,270]:arc(9,angle+28,angle+62,a,180,1)
    elif style=='ring':
        for angle in [0,90,180,270]:arc(18,angle+9,angle+81,a)
        ticks(23,[0,90,180,270],5,b)
        dot(1.2)
        for angle in [35,215]:arc(30,angle+phase*6,angle+55+phase*6,b,135,1)
    elif style=='tee':
        line([(-26,0),(-10,0)]);line([(10,0),(26,0)]);line([(0,10),(0,27)])
        for x in [-22,22]:line([(x,-3),(x,3)],b,190,1)
        line([(-4,26),(4,26)],b,190,1)
        dot(1.3)
    elif style=='diamond':
        for angle in [0,90,180,270]:
            q=math.radians(angle)
            shape=[(-8,-17),(0,-25),(8,-17)]
            line([(x*math.cos(q)-y*math.sin(q),x*math.sin(q)+y*math.cos(q)) for x,y in shape])
        line([(0,-7),(7,0),(0,7),(-7,0),(0,-7)],b,205,1)
        ticks(32,[0,90,180,270],4,b);dot(1)
    elif style=='chevron':
        line([(-11,7),(0,-5),(11,7)],a,245,1.7)
        line([(-8,16),(0,8),(8,16)],b,195,1)
        line([(-33,0),(-23,0),(-18,5)],b,200,1)
        line([(33,0),(23,0),(18,5)],b,200,1)
        line([(0,-23),(0,-15)],a,200,1)
    elif style=='brackets':
        for sx in [-1,1]:
            for sy in [-1,1]:
                line([(sx*14,sy*27),(sx*27,sy*27),(sx*27,sy*14)],a,235,1.8)
                line([(sx*21,sy*32),(sx*32,sy*32),(sx*32,sy*21)],b,145,1)
        ticks(13,[0,90,180,270],4,a);dot(1.1)
    elif style=='orbit':
        for angle in [0,120,240]:
            arc(26,angle+phase*6,angle+76+phase*6,a,230,1.6)
            arc(34,angle-phase*4+20,angle-phase*4+67,b,185,1)
        ticks(15,[0,90,180,270],5,a)
        for angle in [45,135,225,315]:arc(9,angle-12,angle+12,b,210,1)
        dot(1.5)
        # Orbital marker is outside the fixed, open reading anchor.
        q=math.radians(phase*6)
        x,y=26*math.cos(q),26*math.sin(q)
        line([(x-1,y),(x+1,y)],w,250,2)
    # Subtle local bloom stays inside this tiny sprite.
    glow=light.filter(ImageFilter.GaussianBlur(1.8*factor))
    glow.putalpha(glow.getchannel('A').point(lambda v:int(v*.45)))
    shadow.alpha_composite(glow);shadow.alpha_composite(light)
    return shadow.resize((edge,edge),Image.Resampling.LANCZOS)
