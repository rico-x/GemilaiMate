#!/usr/bin/env python3
"""Deterministic geometric placement search; execute on the build host only.

Uses KiCad courtyards, PTH pad rows and explicit USB/RF envelopes. This is not
an electrical or 3D acceptance check: DRC and mechanical review follow it.
"""
import json, sys, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
_data=json.loads((H/'design.json').read_text());aliases={c['designator']:c['ref'] for c in _data['parts']}
F={aliases.get(f.GetReference(),f.GetReference()):f for f in B.GetFootprints()}
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
D=json.loads((H/'design.json').read_text());parts={x['ref']:x for x in D['parts']}

def box(f,mode='court'):
    if f.GetReference()==parts['U1']['designator']:return [5.25,-.1,24.75,19.8]
    if mode=='pth':
        items=[a for a in f.Pads() if a.GetAttribute()!=p.PAD_ATTRIB_SMD]
    else:items=[a for a in f.GraphicalItems() if a.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]
    boxes=[a.GetBoundingBox() for a in items]
    if not boxes:return None
    return [min(p.ToMM(a.GetLeft()) for a in boxes),min(p.ToMM(a.GetTop()) for a in boxes),
            max(p.ToMM(a.GetRight()) for a in boxes),max(p.ToMM(a.GetBottom()) for a in boxes)]

def overlap(a,b,margin=.08):
    return bool(a and b and a[0]<b[2]+margin and b[0]<a[2]+margin and a[1]<b[3]+margin and b[1]<a[3]+margin)

placed=[]
# All drills, regardless of side, need clearance from components. For reserve
# headers on the reverse side the socket body may overlap a front SMD body.
def obstacles(f):
    back=f.IsFlipped();out=[]
    for ref in placed:
        g=F[ref]
        if g.IsFlipped()==back:out.append(box(g))
        else:
            if box(f,'pth'):out.append(box(g))
            else:out.append(box(g,'pth'))
    out.extend([[x-2.1,y-2.1,x+2.1,y+2.1] for x,y in D['mounts_mm']])
    # USB plug and routing corridor; its actual metal outline goes to y=50.3.
    if f.GetReference()!=parts['J_USB']['designator']:out.append([1.8,39.6,13.1,50])
    return out

def fits(f):
    a=box(f)
    if f.GetReference() not in [parts[r]['designator'] for r in ['U1','J_USB']] and (a[0]<.4 or a[1]<.4 or a[2]>64.6 or a[3]>49.6):return False
    return not any(overlap(a,b) for b in obstacles(f))

def setcenter(ref,x,y,angle=0):
    f=F[ref];f.SetOrientationDegrees(angle);f.SetPosition(V(0,0));a=box(f)
    f.SetPosition(V(x-(a[0]+a[2])/2,y-(a[1]+a[3])/2))

for ref in ['U1','J_USB','J_ADS','J_TC']:
    if not fits(F[ref]):print('Fixed clash:',ref)
    placed.append(ref)
# The connector centre describes the actual housing courtyard, not pad 1.
fixed={'J_PWR':(29.5,3.5,0),'J_DISPLAY':(38,3.5,0),'J_RGBW':(61.5,11.5,90),
       'J_ALBA':(61.5,24,90),'J_VALVE':(61.5,34.25,90),'J_LIGHT':(61.5,44,90),
       'J_PRESS':(20,46.5,0),'J_BUTTONS':(31.5,46.5,0),'J_PUMP':(43.9,46.5,0),
       'J_ALT':(54.1,46.5,0),'J_HEAT':(44.5,39.5,0),'J_TOF':(35,33.5,0)}
for ref,xyz in fixed.items():
    setcenter(ref,*xyz)
    if not fits(F[ref]):print('Fixed connector clash:',ref,box(F[ref]))
    placed.append(ref)

# Greedy nearest-feasible candidates; large packages go first. Small passives
# are biased to their initial circuit placement and already placed neighbours.
order=['U_REG','U_LED','U_SSR','SW_RESET','SW_BOOT','U_LEVEL','U_ZC','U_PUMP','J_EXT','J_FREE','J_SCALE']
order+=sorted([r for r in parts if r not in placed and r not in order],key=lambda r:-(box(F[r])[2]-box(F[r])[0])*(box(F[r])[3]-box(F[r])[1]))
for ref in order:
    f=F[ref];initial=f.GetPosition();target=(p.ToMM(initial.x),p.ToMM(initial.y));best=None
    obs=obstacles(f)
    neighbour=[]
    nets={a.GetNetname() for a in f.Pads() if a.GetNetname() and a.GetNetname() not in ['/GND','/+3V3','/+5V_CORE','/+5V_EXT']}
    for other in placed:
        for a in F[other].Pads():
            if a.GetNetname() in nets:neighbour.append((p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y)))
    for angle in [0,90,180,270]:
        f.SetOrientationDegrees(angle);f.SetPosition(V(0,0));a=box(f);pw=box(f,'pth')
        for ix in range(2,129):
            x=ix*.5
            if x+a[0]<.4 or x+a[2]>64.6:continue
            for iy in range(2,99):
                y=iy*.5
                b=[x+a[0],y+a[1],x+a[2],y+a[3]]
                if b[1]<.4 or b[3]>49.6 or any(overlap(b,o) for o in obs):continue
                score=abs(x-target[0])+abs(y-target[1])
                if neighbour:score+=.25*sum(abs(x-nx)+abs(y-ny) for nx,ny in neighbour)/len(neighbour)
                score+=angle/10000
                if best is None or score<best[0]:best=(score,x,y,angle)
    if best is None:raise SystemExit('No feasible location for '+ref)
    _,x,y,angle=best;f.SetOrientationDegrees(angle);f.SetPosition(V(x,y));placed.append(ref)
    print(ref,x,y,angle,flush=True)

out={r:dict(x=round(p.ToMM(f.GetPosition().x),4),y=round(p.ToMM(f.GetPosition().y),4),rotation=f.GetOrientationDegrees()) for r,f in F.items() if r in parts}
(H/'placement.json').write_text(json.dumps(out,indent=2)+'\n')
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
print('Saved deterministic placement; regenerate schematic/data, then run DRC.')
