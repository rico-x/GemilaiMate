#!/usr/bin/env python3
"""Net-aware, mechanically constrained placement search on the build host.

Starts from the reviewed placement. Moves low SMD parts beneath elevated
modules, but preserves the MCU/antenna, sockets, harness banks and LDO cluster.
This minimises a wire-length estimate, not routing or hardware acceptance.
"""
import argparse
import gc
gc.disable()
import json
import math
from pathlib import Path
import random
import sys

R=Path(__file__).resolve().parents[3]
H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'hardware/shield/scripts'))
from kicad_runtime import application
app=application()
import pcbnew as p

ap=argparse.ArgumentParser()
ap.add_argument('--seed',type=int,default=1)
ap.add_argument('--iterations',type=int,default=150000)
ap.add_argument('--lock',default='')
a=ap.parse_args();rng=random.Random(a.seed)
D=json.loads((H/'design.json').read_text());W,HEIGHT=D['size_mm']
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
aliases={x['designator']:x['ref'] for x in D['parts']}
parts={x['ref']:x for x in D['parts']}
F={aliases.get(f.GetReference(),f.GetReference()):f for f in B.GetFootprints()}
mm=p.ToMM
ignore={'GND','+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED'}
state={};netpins={};shapes={};pth={};sides={};angles={}

def bbox(item):
    q=item.GetBoundingBox()
    return [mm(q.GetLeft()),mm(q.GetTop()),mm(q.GetRight()),mm(q.GetBottom())]

for ref,c in parts.items():
    f=F[ref];x,y=mm(f.GetPosition().x),mm(f.GetPosition().y)
    state[ref]=(x,y,0);angles[ref]=f.GetOrientationDegrees();sides[ref]=f.IsFlipped()
    court=[bbox(q) for q in f.GraphicalItems() if q.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]
    if ref=='U1':court=[[5.25,-.1,24.75,19.8]]
    elif ref=='J_LEVEL':
        court=[[x-6.8,y-7.85,x+6.8,y-4.85],[x-6.8,y+4.85,x+6.8,y+7.85]]
    elif court:
        court=[[min(b[0] for b in court),min(b[1] for b in court),max(b[2] for b in court),max(b[3] for b in court)]]
    shapes[ref]=[[q[0]-x,q[1]-y,q[2]-x,q[3]-y] for q in court]
    pth[ref]=[]
    for pad in f.Pads():
        if pad.GetAttribute()!=p.PAD_ATTRIB_SMD:
            q=bbox(pad);pth[ref].append([q[0]-x,q[1]-y,q[2]-x,q[3]-y])
        net=pad.GetNetname()
        if net and net not in ignore and not net.startswith('unconnected-'):
            netpins.setdefault(net,[]).append((ref,mm(pad.GetPosition().x)-x,mm(pad.GetPosition().y)-y))

def point(q,offset):
    x,y,turn=q;dx,dy=offset
    for _ in range(turn%4):dx,dy=dy,-dx
    return x+dx,y+dy

def boxes(ref,which=shapes):
    q=state[ref];out=[]
    for x,y,u,v in which[ref]:
        corners=[point(q,(x,y)),point(q,(u,y)),point(q,(u,v)),point(q,(x,v))]
        out.append([min(t[0] for t in corners),min(t[1] for t in corners),max(t[0] for t in corners),max(t[1] for t in corners)])
    return out

def hit(a,b,gap=.10):
    return a[0]<b[2]+gap and b[0]<a[2]+gap and a[1]<b[3]+gap and b[1]<a[3]+gap

cached={r:boxes(r) for r in state};cached_pth={r:boxes(r,pth) for r in state}
module_boxes=[x['body_rect_mm'] for x in D['module_sockets'].values()]
def legal(refs):
    for ref in refs:
        cs=boxes(ref);ps=boxes(ref,pth)
        for q in cs:
            if q[0]<.5 or q[1]<.5 or q[2]>W-.5 or q[3]>HEIGHT-.5:return False
            for x,y in D['mounts_mm']:
                if math.hypot(max(q[0]-x,0,x-q[2]),max(q[1]-y,0,y-q[3]))<2.1:return False
            if ref.startswith(('SW_','TP','J_')) and not sides[ref] and any(hit(q,b) for b in module_boxes):return False
        for other in state:
            if other==ref:continue
            oc=boxes(other) if other in refs else cached[other]
            op=boxes(other,pth) if other in refs else cached_pth[other]
            if sides[ref]==sides[other]:
                if any(hit(u,v) for u in cs for v in oc):return False
            elif any(hit(u,v) for u in ps for v in oc) or any(hit(u,v) for u in cs for v in op):return False
    return True

def netcost(net):
    pts=[point(state[r],(x,y)) for r,x,y in netpins[net]]
    weight=3 if net.startswith(('USB','TC_')) or net in ('BOARD_ID','PRESSURE') else 1
    return weight*(max(x for x,y in pts)-min(x for x,y in pts)+max(y for x,y in pts)-min(y for x,y in pts))

nets_by_ref={r:{n for n,pins in netpins.items() if any(x[0]==r for x in pins)} for r in state}
locked={'U1','J_USB','J_ADS','J_TC','J_LEVEL','U_REG','C_IN','C_OUT','C_MCU','C_MCUHF'}
locked.update(a.lock.split(','))
locked.update(r for r,c in parts.items() if c['section'] in ('Connectors','Expansion'))
groups={r:[r] for r in state if r not in locked}
for owner,cap in [('U_LED','C_PCA'),('U_SSR','C_SSR'),('U_ZC','C_ZC'),('U_PUMP','C_PUMP')]:
    if owner not in locked:groups[owner]=[owner,cap];groups.pop(cap,None)
keys=list(groups);scores={n:netcost(n) for n in netpins};score=sum(scores.values())
best_score=initial=score;best=dict(state);accepted=0
for index in range(a.iterations):
    ref=rng.choice(keys);refs=groups[ref];old={r:state[r] for r in refs}
    x,y,turn=state[ref]
    radius=4 if index<a.iterations*.6 else 1.5
    if rng.random()<.10:
        dx,dy=rng.randrange(2,int(W*2)-2)/2-x,rng.randrange(2,int(HEIGHT*2)-2)/2-y
    else:dx,dy=rng.randrange(-int(radius*2),int(radius*2)+1)/2,rng.randrange(-int(radius*2),int(radius*2)+1)/2
    dt=rng.choice([0,0,0,0,1,2,3])
    for r in refs:
        ox,oy,ot=old[r];rx,ry=ox-x,oy-y
        for _ in range(dt):rx,ry=ry,-rx
        state[r]=(x+dx+rx,y+dy+ry,(ot+dt)%4)
    if not legal(set(refs)):
        state.update(old);continue
    affected=set().union(*(nets_by_ref[r] for r in refs))
    fresh={n:netcost(n) for n in affected};delta=sum(fresh.values())-sum(scores[n] for n in affected)
    temperature=1.5*(1-index/a.iterations)+.025
    if delta<=0 or rng.random()<math.exp(-delta/temperature):
        score+=delta;scores.update(fresh);accepted+=1
        for r in refs:cached[r]=boxes(r);cached_pth[r]=boxes(r,pth)
        if score<best_score:best_score=score;best=dict(state)
    else:state.update(old)

placement=json.loads((H/'placement.json').read_text())
for r,(x,y,turn) in best.items():placement[r].update(x=round(x,4),y=round(y,4),rotation=(angles[r]+turn*90)%360)
(H/'placement.json').write_text(json.dumps(placement,indent=2)+'\n')
out=dict(seed=a.seed,iterations=a.iterations,initial_hpwl=round(initial,3),final_hpwl=round(best_score,3),accepted_moves=accepted,
         metric='weighted signal HPWL; ignores supply/GND; not proof of routability')
(H/'reports/placement-optimization.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
