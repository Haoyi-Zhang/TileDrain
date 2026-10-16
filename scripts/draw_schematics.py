"""Vector drawing primitives; copied into each independent project generator."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)


# Sources: inputs/example.json and inputs/fork.json. Diagrams retain their labels,
# relation generators, lane membership, positive sizes and certified outcomes.
NAMES=('running-example','fork-obstruction')

def connect_centers(d,a,b,dashed=False):
    import math
    x,y,w,_,_=d.nodes[a];X,Y,W,_,_=d.nodes[b]
    dx,dy=X-x,Y-y;v=math.hypot(dx,dy)
    d.arrow((x+w*.5*dx/v,y+w*.5*dy/v),
            (X-W*.5*dx/v,Y-W*.5*dy/v),dashed=dashed)

def draw_all(out):
    import json
    inputs=Path(__file__).resolve().parents[1]/'inputs'
    example=json.loads((inputs/'example.json').read_text())
    fork=json.loads((inputs/'fork.json').read_text())
    assert example=={'p':[0,0,1,2,5,0],'q':[0,1,1,7,5,21],
                     'lane':[0,0,1,1,0,0],'weight':[1]*6,
                     'capacity':[2,2],'unsupported':8}
    assert fork=={'p':[0]*4,'q':[0,1,1,7],'lane':[0]*4,
                  'weight':[2,3,4,1],'capacity':[5],'unsupported':0}
    out.mkdir(parents=True,exist_ok=True)
    d=Drawing((-.5,-.7,8.65,3.1))
    d.text(-.3,2.7,'Source order',ha='left')
    coords=((0,1.8),(1.1,2.0),(1.1,.95),(2.25,1.8),(2.25,.65),(3.4,.65))
    for i,(x,y) in enumerate(coords):
        d.box('s'+str(i),x,y,.6,.6,str(i),shape='circle')
        if i<4:d.ax.patches[-1].set_facecolor('.85')
    for a,b in ((0,2),(1,3),(2,4)):connect_centers(d,'s'+str(a),'s'+str(b))
    for a,b in ((0,1),(2,3),(4,5)):connect_centers(d,'s'+str(a),'s'+str(b),True)
    d.text(4.4,2.7,'Destination FIFOs',ha='left')
    for tag,lane,y in (('a',(0,1,4,5),1.8),('b',(2,3),.75)):
        d.text(4.85,y,'$l='+('0' if tag=='a' else '1')+'$',ha='right')
        for j,i in enumerate(lane):
            d.box(tag+str(i),5.35+.85*j,y,.6,.6,str(i))
            if i<4:d.ax.patches[-1].set_facecolor('.85')
        for a,b in zip(lane,lane[1:]):d.edge(tag+str(a),tag+str(b),'e','w')
    d.text(6.75,.75,'$C=(2,2)$',ha='left')
    d.arrow((-.3,-.1),(.25,-.1));d.text(.32,-.1,'$P$ edge',ha='left')
    d.arrow((2,-.1),(2.55,-.1),dashed=True)
    d.text(2.62,-.1,'extra $Q$ edge',ha='left')
    d.box('legend',5.1,-.1,.3,.3,'')
    d.ax.patches[-1].set_facecolor('.85')
    d.text(5.4,-.1,'mandatory drain',ha='left')
    d.save(out,'running-example')

    d=Drawing((-.65,-.85,9.35,2.9))
    for name,x,y,label in (('u',0,1,'0'),('a',1.65,1.9,'1'),
                           ('b',1.65,.1,'2'),('j',3.3,1,'3')):
        d.box(name,x,y,.6,.6,label,shape='circle')
        if name=='u':d.ax.patches[-1].set_facecolor('.85')
    for a,b in (('u','a'),('u','b'),('a','j'),('b','j')):connect_centers(d,a,b)
    for x,y,label in ((0,1.6,'$s_0=2$'),(1.65,2.5,'$s_1=3$'),
                       (1.65,-.5,'$s_2=4$'),(3.3,1.6,'$s_3=1$')):
        d.text(x,y,label)
    d.frame(1.03,-.7,2.88,3.4);d.text(3.8,-.6,'$V$',ha='right',va='bottom')
    d.text(4.35,1.85,'$w_0(V)=8$\n'
        r'$w_0(\uparrow_Q(1)\cap V)=4$'+'\n'+
        r'$w_0(\uparrow_Q(2)\cap V)=5$',ha='left')
    d.text(4.35,.25,'$C_0=5$\n$A=\\{0,1\\},\\quad B\'=\\{0,2\\}$\n'
        '$A\\cap B\'=\\{0\\}$ is infeasible',ha='left')
    d.save(out,'fork-obstruction')



def main():
    import tempfile
    ap=argparse.ArgumentParser(description='Direct Python vector drawings of the manuscript relationships.')
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'figures');ap.add_argument('--check',action='store_true');a=ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);draw_all(out)
            for name in NAMES:
                p=a.output/(name+'.pdf')
                if not p.is_file() or p.read_bytes()!=(out/(name+'.pdf')).read_bytes():raise SystemExit('Missing/stale schematic: '+name)
        print('All schematics reproduce byte-for-byte.')
    else:draw_all(a.output)
if __name__=='__main__':main()

