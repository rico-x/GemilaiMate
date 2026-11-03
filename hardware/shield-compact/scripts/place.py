#!/usr/bin/env python3
"""Deterministic geometric placement search; execute on the build host only.

Uses KiCad courtyards, PTH pad rows and explicit USB/RF envelopes. This is not
an electrical or 3D acceptance check: DRC and mechanical review follow it.
With --keep, every part already in placement.json stays put and only parts
added since are placed around them.
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
W,H_MM=D['size_mm']

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
designator_alias={c['designator']:c['ref'] for c in D['parts']}
def under_module_ok(f):
    ref=designator_alias.get(f.GetReference(),'')
    return all(a.GetAttribute()==p.PAD_ATTRIB_SMD for a in f.Pads()) and not ref.startswith(('SW_','TP'))
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
    # Plug-in modules sit 11 mm above the board and are fitted after soldering,
    # so low SMD parts may live underneath. Buttons, test points and wire
    # headers must stay reachable with the modules inserted.
    for alias in ['J_ADS','J_TC','J_LEVEL']:
        if f.GetReference()==parts[alias]['designator'] or under_module_ok(f):
            continue
        socket_fp=F[alias]
        if socket_fp.IsFlipped()==back:
            out.append(D['module_sockets'][alias]['body_rect_mm'])
    out.extend([[x-2.1,y-2.1,x+2.1,y+2.1] for x,y in D['mounts_mm']])
    # USB plug, receptacle, and the locked differential escape routes. Reserve
    # the route corridors before placing ordinary components/testpoints; these
    # are manually restored by prepare_route.py after placement.
    usb_fixed={parts[r]['designator'] for r in ['J_USB','U1','U_ESD','R_USBM','R_USBP']}
    if f.GetReference() not in usb_fixed:
        out.append([1.8,49.2,13.1,H_MM])
        out.append([.5,15.5,10.0,49.2])
    return out

def fits(f):
    a=box(f)
    if f.GetReference() not in [parts[r]['designator'] for r in ['U1','J_USB']] and (a[0]<.4 or a[1]<.4 or a[2]>W-.4 or a[3]>H_MM-.4):return False
    alias=next((r for r in D['module_sockets'] if parts[r]['designator']==f.GetReference()),None)
    if alias:
        body=D['module_sockets'][alias]['body_rect_mm']
        if overlap(body,D['module_body']) or overlap(body,D['rf_keepout']):return False
        for other in ['J_ADS','J_TC','J_LEVEL']:
            if other!=alias and overlap(body,D['module_sockets'][other]['body_rect_mm']):return False
    return not any(overlap(a,b) for b in obstacles(f))

def setcenter(ref,x,y,angle=0):
    f=F[ref];f.SetOrientationDegrees(angle);f.SetPosition(V(0,0));a=box(f)
    f.SetPosition(V(x-(a[0]+a[2])/2,y-(a[1]+a[3])/2))

KEEP='--keep' in sys.argv
kept=json.loads((H/'placement.json').read_text()) if KEEP else {}
if KEEP:placed.extend(r for r in parts if r in kept)
else:F['J_USB'].SetPosition(V(4.5,H_MM-9.135))
for ref in [] if KEEP else ['U1','J_USB','J_ADS','J_TC','J_LEVEL']:
    if not fits(F[ref]):print('Fixed clash:',ref)
    placed.append(ref)
# The connector centre describes the actual housing courtyard, not pad 1.
fixed={'J_PWR':(54,6,0),'J_DISPLAY':(54,15,0),'J_RGBW':(66.5,9,90),
       'J_ALBA':(66.5,23.5,90),'J_VALVE':(66.5,35.5,90),'J_LIGHT':(66.5,47,90),
       'J_PRESS':(16,43,0),'J_BUTTONS':(22,52,0),'J_PUMP':(36,52,0),
       'J_ALT':(49,52,0),'J_HEAT':(53,34,0),'J_TOF':(53,42,0)}
for ref,xyz in ({} if KEEP else fixed).items():
    setcenter(ref,*xyz)
    if not fits(F[ref]):print('Fixed connector clash:',ref,box(F[ref]))
    placed.append(ref)

# prepare_route.py restores these exact hand-routed native-USB components and
# tracks; reserve their final geometry before the greedy placement pass.
for ref,x,y,angle in [] if KEEP else [('R_USBM',3.2,15.7,180),('R_USBP',3.2,18.6,180),('U_ESD',7.475,33.5,90)]:
    f=F[ref];f.SetOrientationDegrees(angle);f.SetPosition(V(x,y))
    if not fits(f):print('Fixed USB component clash:',ref,box(f))
    placed.append(ref)

# Keep the two ID-divider resistors just beyond the WROOM pad fanout, next to
# GPIO40/GPIO11.
for ref,xyz in ({} if KEEP else {'R_ID_TOP':(27.5,7.2,0),'R_ID_LOW':(27.5,9.8,0)}).items():
    setcenter(ref,*xyz)
    if not fits(F[ref]):print('Fixed ID resistor clash:',ref,box(F[ref]))
    placed.append(ref)

# Greedy nearest-feasible candidates; large packages go first. Small passives
# are biased to their initial circuit placement and already placed neighbours.
anchors={'C_IN':('U_REG','1'),'C_OUT':('U_REG','3'),'C_PCA':('U_LED','20'),
         'C_SSR':('U_SSR','14'),'C_ZC':('U_ZC','5'),'C_PUMP':('U_PUMP','5'),
         'C_LVA':('J_LEVEL','3'),'C_LVB':('J_LEVEL','8')}
order=[] if KEEP else ['U_REG','C_IN','C_OUT','U_LED','C_PCA','U_SSR','C_SSR','SW_RESET','SW_BOOT',
       'U_ZC','C_ZC','U_PUMP','C_PUMP','C_LVA','C_LVB','J_EXT','J_FREE','J_SCALE']
order+=sorted([r for r in parts if r not in placed and r not in order],key=lambda r:-(box(F[r])[2]-box(F[r])[0])*(box(F[r])[3]-box(F[r])[1]))
for ref in order:
    f=F[ref];initial=f.GetPosition();target=(p.ToMM(initial.x),p.ToMM(initial.y));best=None
    if ref in anchors:
        owner,num=anchors[ref];a=next(a for a in F[owner].Pads() if a.GetNumber()==num)
        target=(p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y))
    obs=obstacles(f)
    neighbour=[]
    nets={a.GetNetname() for a in f.Pads() if a.GetNetname() and a.GetNetname() not in ['/GND','/+3V3','/+5V_CORE','/+5V_EXT']}
    for other in placed:
        for a in F[other].Pads():
            if a.GetNetname() in nets:neighbour.append((p.ToMM(a.GetPosition().x),p.ToMM(a.GetPosition().y)))
    for angle in [0,90,180,270]:
        f.SetOrientationDegrees(angle);f.SetPosition(V(0,0));a=box(f);pw=box(f,'pth')
        for ix in range(2,int(W*2)-1):
            x=ix*.5
            if x+a[0]<.4 or x+a[2]>W-.4:continue
            for iy in range(2,int(H_MM*2)-1):
                y=iy*.5
                b=[x+a[0],y+a[1],x+a[2],y+a[3]]
                if b[1]<.4 or b[3]>H_MM-.4 or any(overlap(b,o) for o in obs):continue
                if ref in anchors and math.dist((x,y),target)>4:continue
                score=abs(x-target[0])+abs(y-target[1])
                if neighbour:score+=.25*sum(abs(x-nx)+abs(y-ny) for nx,ny in neighbour)/len(neighbour)
                score+=angle/10000
                if best is None or score<best[0]:best=(score,x,y,angle)
    if best is None:raise SystemExit('No feasible location for '+ref)
    _,x,y,angle=best;f.SetOrientationDegrees(angle);f.SetPosition(V(x,y));placed.append(ref)
    print(ref,x,y,angle,flush=True)

out=dict(kept)
out.update({r:dict(x=round(p.ToMM(f.GetPosition().x),4),y=round(p.ToMM(f.GetPosition().y),4),rotation=f.GetOrientationDegrees()) for r,f in F.items() if r in parts and r not in kept})
(H/'placement.json').write_text(json.dumps(out,indent=2)+'\n')
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
print('Saved deterministic placement; regenerate schematic/data, then run DRC.')
