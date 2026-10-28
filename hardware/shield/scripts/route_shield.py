"""Two-layer grid router; KiCad DRC, not this router, is the final authority."""
import json, math, heapq, itertools, random, time
from pathlib import Path
from kicad_runtime import application
_app=application()
import pcbnew as p

OUT=Path(__file__).resolve().parents[1]
SPEC=json.loads((OUT/'design.json').read_text())
BOARD=p.LoadBoard(str(OUT/'gemilaimate-shield.kicad_pcb'))
for n in BOARD.GetNetsByNetcode().values():
 if n.GetNetname().startswith('/'):n.SetNetname(n.GetNetname()[1:])
for t in list(BOARD.GetTracks()): BOARD.Delete(t)
for z in list(BOARD.Zones()):
 if not z.GetIsRuleArea(): BOARD.Delete(z)
NETS_BY_NAME={n.GetNetname():n for n in BOARD.GetNetsByNetcode().values()}
GRID=.127; W,H=SPEC['size_mm']; NX=round(W/GRID)+1; NY=round(H/GRID)+1; N=NX*NY; CLEAR=.27
grid=lambda q:round(q/GRID)
xy=lambda i:(i%NX,(i%N)//NX)
idx=lambda x,y,l:l*N+y*NX+x
tracks=[];vias=[]
pads=[];by_net={};smd_locations=[]
for fp in sorted(BOARD.GetFootprints(),key=lambda f:(f.GetReference(),f.GetPosition().x,f.GetPosition().y)):
 for pad in sorted(fp.Pads(),key=lambda pa:(pa.GetNumber(),pa.GetPosition().x,pa.GetPosition().y)):
  pos=pad.GetPosition();name=pad.GetNetname()
  if name.startswith('unconnected-'):
   pad.SetNetCode(0);name=''
  x,y=p.ToMM(pos.x),p.ToMM(pos.y);hx,hy=p.ToMM(pad.GetSize().x)/2,p.ToMM(pad.GetSize().y)/2
  layers=(0,1) if pad.GetAttribute()!=p.PAD_ATTRIB_SMD else (0,)
  pads.append((x,y,hx,hy,name,layers,pad.GetShape()==p.PAD_SHAPE_CIRCLE))
  if name:by_net.setdefault(name,[]).append((grid(x),grid(y),layers))
  if pad.GetAttribute()==p.PAD_ATTRIB_SMD:smd_locations.append((x,y,hx,hy))


def circle(mask,cx,cy,r,layers=(0,1)):
 for y in range(max(0,grid(cy-r)-1),min(NY,grid(cy+r)+2)):
  for x in range(max(0,grid(cx-r)-1),min(NX,grid(cx+r)+2)):
   if (x*GRID-cx)**2+(y*GRID-cy)**2<r*r:
    for l in layers:mask[idx(x,y,l)]=1


def capsule(mask,a,b,r,l):
 ax,ay=a[0]*GRID,a[1]*GRID;bx,by=b[0]*GRID,b[1]*GRID
 for y in range(max(0,grid(min(ay,by)-r)-1),min(NY,grid(max(ay,by)+r)+2)):
  for x in range(max(0,grid(min(ax,bx)-r)-1),min(NX,grid(max(ax,bx)+r)+2)):
   px,py=x*GRID,y*GRID
   xx=max(min(ax,bx),min(px,max(ax,bx))); yy=max(min(ay,by),min(py,max(ay,by)))
   if (px-xx)**2+(py-yy)**2<r*r:mask[idx(x,y,l)]=1


def blocked(nn,width):
 m=bytearray(2*N)
 edge=.5+width/2+.03
 for l in (0,1):
  for y in range(NY):
   for x in range(NX):
    if min(x*GRID,y*GRID,W-x*GRID,H-y*GRID)<edge:m[idx(x,y,l)]=1
  a,b,c,d=SPEC['rf_keepout'];margin=width/2+.03
  for y in range(max(0,grid(b-margin)-1),min(NY,grid(d+margin)+2)):
   for x in range(max(0,grid(a-margin)-1),min(NX,grid(c+margin)+2)):m[idx(x,y,l)]=1
 for cx,cy,hx,hy,pn,layers,is_circle in pads:
  if pn==nn:continue
  inflate=CLEAR+width/2
  if is_circle:circle(m,cx,cy,hx+inflate,layers)
  else:
   for y in range(max(0,grid(cy-hy-inflate)-1),min(NY,grid(cy+hy+inflate)+2)):
    for x in range(max(0,grid(cx-hx-inflate)-1),min(NX,grid(cx+hx+inflate)+2)):
     dx=max(abs(x*GRID-cx)-hx,0);dy=max(abs(y*GRID-cy)-hy,0)
     if dx*dx+dy*dy<inflate*inflate:
      for ll in layers:m[idx(x,y,ll)]=1
 for tr in tracks:
  if tr['net']!=nn:capsule(m,tr['a'],tr['b'],(tr['width']+width)/2+CLEAR,tr['layer'])
 for v in vias:
  if v['net']!=nn:circle(m,v['x']*GRID,v['y']*GRID,.35+CLEAR+width/2)
 return m


def find_path(m,start,goals,nn):
 vm=blocked(nn,.7)
 for v in vias:
  if v['net']==nn:circle(vm,v['x']*GRID,v['y']*GRID,.56)
 for x,y,hx,hy,pn,layers,is_circle in pads:
  if pn==nn and len(layers)==2:circle(vm,x,y,hx+.42)
 # Goal set contains all existing copper cells of this net, on both layers
 # at plated pads. At own vias both planes are present as well.
 gx=[xy(a)[0] for a in goals];gy=[xy(a)[1] for a in goals]
 xmin,xmax,ymin,ymax=min(gx),max(gx),min(gy),max(gy)
 def h(x,y):return max(xmin-x,0,x-xmax)+max(ymin-y,0,y-ymax)
 best={};parent={};queue=[];seq=itertools.count()
 for l in start[2]:
  a=idx(start[0],start[1],l);best[a]=0;parent[a]=None
  heapq.heappush(queue,(h(start[0],start[1]),next(seq),a))
 visits=0
 while queue:
  _,_,a=heapq.heappop(queue);cost=best[a];x,y=xy(a);l=a//N
  if a in goals:
   path=[]
   while a is not None:path.append(a);a=parent[a]
   return path[::-1]
  visits+=1
  if visits>600000:return None
  for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
   xx,yy=x+dx,y+dy
   if 0<=xx<NX and 0<=yy<NY:
    b=idx(xx,yy,l)
    if not m[b] and cost+1<best.get(b,1e12):
     best[b]=cost+1;parent[b]=a;heapq.heappush(queue,(cost+1+h(xx,yy),next(seq),b))
  # A via has a larger physical annulus than the routed signal track. Check
  # neighbours on both planes as a conservative additional clearance guard.
  b=idx(x,y,1-l)
  if not m[b] and not vm[a] and not vm[b] and cost+36<best.get(b,1e12):
   ok=not any(abs(x*GRID-cx)<hx+.4 and abs(y*GRID-cy)<hy+.4 for cx,cy,hx,hy in smd_locations)
   for ll in (0,1):
    for dx,dy in ((0,0),(2,0),(-2,0),(0,2),(0,-2),(1,1),(-1,-1),(1,-1),(-1,1)):
     if not(0<=x+dx<NX and 0<=y+dy<NY) or m[idx(x+dx,y+dy,ll)]:ok=False;break
   if ok:best[b]=cost+36;parent[b]=a;heapq.heappush(queue,(cost+36+h(x,y),next(seq),b))
 return None


def add_path(path,nn,width):
 prev=None;anchor=None;direction=None
 def flush(a,b,l):
  if a!=b:tracks.append(dict(a=a,b=b,layer=l,net=nn,width=width))
 for a in path:
  x,y=xy(a);l=a//N
  if prev is None:anchor=(x,y);prev=(x,y,l);continue
  px,py,pl=prev
  if l!=pl:
   flush(anchor,(px,py),pl);vias.append(dict(x=x,y=y,net=nn));anchor=(x,y);direction=None
  else:
   nd=(x-px,y-py)
   if direction is not None and direction!=nd:flush(anchor,(px,py),l);anchor=(px,py)
   direction=nd
  prev=(x,y,l)
 if prev:flush(anchor,prev[:2],prev[2])


# Ground is explicitly routed as one connected network before signals;
# the two pours then reinforce this return instead of relying on islands.
# Join each electrically active alternative MCU socket pad to its primary
# pad before other signals can cut the corridor between the two rows.
preconnected={}
u1=next(c for c in SPEC['parts'] if c['ref']=='U1');groups={}
for pin in u1['physical_pads']:
 if pin['net']:groups.setdefault(pin['number'],[]).append(pin)
for number,pins in sorted(groups.items()):
 if len(pins)!=2 or pins[0]['net']=='GND':continue
 aa,bb=sorted(pins,key=lambda q:q['y']);nn=aa['net']
 x,y0,y1=grid(aa['x']),grid(aa['y']),grid(bb['y'])
 path=[idx(x,y,0) for y in range(y0,y1+1)]
 add_path(path,nn,.2032)
 if nn!='GND':
  assert nn not in preconnected
  preconnected[nn]=set(path)|{idx(x,y0,1),idx(x,y1,1)}

# Give every SMD terminal a short, tented escape via before routing long
# branches. Otherwise a previously routed supply can surround a fine SMD
# pad even though the rest of this two-layer board is largely empty.
# These are ordinary vias OUTSIDE all pads, not a via-in-pad process.
escapes={}
for cx,cy,hx,hy,nn,layers,is_circle in sorted(pads,key=lambda a:(a[1],a[0],a[4])):
 if layers!=(0,) or not nn:continue
 sx,sy=grid(cx),grid(cy);m=blocked(nn,.2032);vm=blocked(nn,.7)
 candidates=[(0,12),(0,-12),(12,0),(-12,0),(0,16),(0,-16),(16,0),(-16,0),
             (8,12),(-8,12),(8,-12),(-8,-12),(12,8),(-12,8),(12,-8),(-12,-8)]
 placed=False
 for dx,dy in candidates:
  vx,vy=sx+dx,sy+dy;x,y=vx*GRID,vy*GRID
  if not (0<=vx<NX and 0<=vy<NY) or vm[idx(vx,vy,0)] or vm[idx(vx,vy,1)]:continue
  if any(abs(x-px)<phx+.4 and abs(y-py)<phy+.4 for px,py,phx,phy,pn,pls,pc in pads):continue
  if any(math.hypot(x-v['x']*GRID,y-v['y']*GRID)<1.05 for v in vias):continue
  path=[idx(sx,sy,0)]
  xx,yy=sx,sy
  # Try both L-shaped escapes. No layer change is allowed until the via.
  for vertical_first in (True,False):
   xx,yy=sx,sy;path=[idx(xx,yy,0)]
   for axis in ((1,0) if vertical_first else (0,1)):
    end=vy if axis else vx
    while (yy if axis else xx)!=end:
     if axis:yy+=1 if yy<end else -1
     else:xx+=1 if xx<end else -1
     path.append(idx(xx,yy,0))
   if all(not m[a] for a in path):break
  else:continue
  add_path(path+[idx(vx,vy,1)],nn,.2032)
  escapes[(nn,sx,sy)]=(vx,vy,(0,1));placed=True;break
 if not placed:raise SystemExit(f'No safe SMD escape for {nn} at {cx},{cy}')
for nn,points in by_net.items():
 by_net[nn]=[escapes.get((nn,x,y),(x,y,layers)) for x,y,layers in points]
print('SMD escapes:',len(escapes),'outside-pad vias',flush=True)
started=time.time()
# Signals first; power last is a separate, wider route. Choose short local
# signals before long bus crossings. Plated through-hole pads join both layers.
def priority(nn):
 # Route narrow SMD escapes before wide supply branches can enclose them.
 ranks={'GND':-100,'ZC_SCHMITT_IN':-9,'PUMP_ZC':-8,'STEAM':-8,'BREW':-8,'STEAM_CONTACT':-8,'BREW_CONTACT':-8,'VALVE_IN':-8,'VALVE_5V':-8,'HEATER_5V':-8,'BOARD_ID':-8,'ZC_RAW':-7,'VALVE_3V3':-6,'HEATER_3V3':-5,'SCL_3V3':-4,'SDA_3V3':-4,'+3V3':-3,'+5V':-3,'DEV_5V':2}
 pts=by_net[nn]
 span=max(q[0] for q in pts)-min(q[0] for q in pts)+max(q[1] for q in pts)-min(q[1] for q in pts)
 return ranks.get(nn,1),span,nn
order=sorted(by_net,key=priority)

fail=[]
for nn in order:
 pts=list(dict.fromkeys(by_net[nn]))
 width=.508 if nn in ['GND','+5V','+3V3','DEV_5V'] else .2032
 if len(pts)<2:continue
 m=blocked(nn,width)
 if nn=='GND':
  rootpin=next(pin for c in SPEC['parts'] if c['ref']=='J1' for pin in c['pins'] if pin['net']=='GND')
  root=(grid(rootpin['x']),grid(rootpin['y']),(0,1))
 else:root=pts[0]
 goals=preconnected.get(nn,{idx(root[0],root[1],l) for l in root[2]})
 pending=[q for q in pts if not any(idx(q[0],q[1],ll) in goals for ll in q[2])]
 while pending:
  start=(min if nn=='GND' else max)(pending,key=lambda a:min(abs(a[0]-xy(g)[0])+abs(a[1]-xy(g)[1]) for g in goals))
  pending.remove(start)
  path=find_path(m,start,goals,nn);branch_width=width
  if not path and width>.254:
   path=find_path(blocked(nn,.2032),start,goals,nn);branch_width=.2032
  if not path:fail.append((nn,start));print('UNROUTED',nn,start,flush=True);continue
  add_path(path,nn,branch_width);goals.update(path);goals.update(idx(start[0],start[1],l) for l in start[2])
 print('ROUTED',nn,'tracks',len(tracks),'vias',len(vias),'seconds',round(time.time()-started,1),flush=True)

for tr in tracks:
 t=p.PCB_TRACK(BOARD);t.SetStart(p.VECTOR2I(p.FromMM(tr['a'][0]*GRID),p.FromMM(tr['a'][1]*GRID)))
 t.SetEnd(p.VECTOR2I(p.FromMM(tr['b'][0]*GRID),p.FromMM(tr['b'][1]*GRID)));t.SetWidth(p.FromMM(tr['width']))
 t.SetLayer(p.F_Cu if tr['layer']==0 else p.B_Cu);t.SetNet(NETS_BY_NAME[tr['net']]);BOARD.Add(t)
for v in vias:
 t=p.PCB_VIA(BOARD);t.SetPosition(p.VECTOR2I(p.FromMM(v['x']*GRID),p.FromMM(v['y']*GRID)));t.SetWidth(p.FromMM(.7));t.SetDrill(p.FromMM(.3));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(NETS_BY_NAME[v['net']]);BOARD.Add(t)
# Intermediate board intentionally not published.
# Ground planes avoid a long shared signal-return chain; keep the antenna exclusion.
for layer in [p.F_Cu,p.B_Cu]:
 z=p.ZONE(BOARD);z.SetLayer(layer);z.SetNet(NETS_BY_NAME['GND']);z.SetLocalClearance(p.FromMM(.2));z.SetMinThickness(p.FromMM(.18));z.SetThermalReliefGap(p.FromMM(.25));z.SetThermalReliefSpokeWidth(p.FromMM(.2));z.SetPadConnection(p.ZONE_CONNECTION_THT_THERMAL);z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
 poly=z.Outline();poly.NewOutline()
 for x,y in [(.5,.5),(W-.5,.5),(W-.5,H-.5),(.5,H-.5)]:poly.Append(p.FromMM(x),p.FromMM(y))
 BOARD.Add(z)
for fp in sorted(BOARD.GetFootprints(),key=lambda f:(f.GetReference(),f.GetPosition().x,f.GetPosition().y)):
 for pad in sorted(fp.Pads(),key=lambda pa:(pa.GetNumber(),pa.GetPosition().x,pa.GetPosition().y)):
  if pad.GetNetname()=='GND':pad.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
p.ZONE_FILLER(BOARD).Fill(BOARD.Zones())
p.SaveBoard(str(OUT/'gemilaimate-shield.kicad_pcb'),BOARD)
(OUT/'routing.json').write_text(json.dumps(dict(failures=fail,segments=len(tracks),vias=len(vias),elapsed_seconds=time.time()-started),indent=2))
print('FINISHED',len(fail),'failures',flush=True)
if fail:raise SystemExit('Routing incomplete; do not export for fabrication')
