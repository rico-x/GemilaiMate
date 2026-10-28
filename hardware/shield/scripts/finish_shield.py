"""Align saved PCB to schematic and assign nominal module/socket 3D models."""
import json, math
from pathlib import Path
from kicad_runtime import application
_app=application()
import pcbnew as p

H=Path(__file__).resolve().parents[1]
from make_3d_models import box
B=p.LoadBoard(str(H/'gemilaimate-shield.kicad_pcb'))
tb=B.GetTitleBlock();tb.SetRevision('0.2.3');tb.SetTitle('GemilaiMate Shield - Rico-X');tb.SetDate('2026-10-28');B.SetTitleBlock(tb)
for item in B.GetDrawings():
    if isinstance(item,p.PCB_TEXT) and item.GetLayer()==p.B_SilkS and abs(p.ToMM(item.GetPosition().x)-32)<.01 and abs(p.ToMM(item.GetPosition().y)-23)<.01:
        item.SetText('github.com/Rico-X/GemilaiMate')
    if isinstance(item,p.PCB_TEXT) and item.GetText()=='1' and abs(p.ToMM(item.GetPosition().x)-67)<.1 and abs(p.ToMM(item.GetPosition().y)-8.89)<.1:
        item.SetPosition(p.VECTOR2I(p.FromMM(68.75),p.FromMM(8.89)))
# Mark the revised dock orientation on the manufactured board, not only in docs.
for label,x,y in [('ROBOTDYN CABLE',45.72,66.8)]:
    if not any(isinstance(t,p.PCB_TEXT) and t.GetText()==label and abs(p.ToMM(t.GetPosition().x)-x)<.01 and abs(p.ToMM(t.GetPosition().y)-y)<.01 for t in B.GetDrawings()):
        t=p.PCB_TEXT(B);t.SetText(label);t.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
        t.SetLayer(p.F_SilkS);t.SetTextSize(p.VECTOR2I(p.FromMM(.8),p.FromMM(.8)));t.SetTextThickness(p.FromMM(.12));B.Add(t)
mapping=json.loads((H/'schematic-pad-nets.json').read_text())
for n in B.GetNetsByNetcode().values():
    if n.GetNetname() and not n.GetNetname().startswith('/'):
        n.SetNetname('/'+n.GetNetname())
nets={n.GetNetname():n for n in B.GetNetsByNetcode().values()}
for fp in B.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute()==p.PAD_ATTRIB_PTH:
            pad.SetLayerSet(p.PAD.PTHMask())
        k=fp.GetReference()+'.'+pad.GetNumber()
        if k not in mapping:continue
        nn=mapping[k]
        if nn not in nets:
            n=p.NETINFO_ITEM(B,nn);B.Add(n);nets[nn]=n
        pad.SetNet(nets[nn])

# A branch may reach an SMD escape on its front side and never use the
# bottom layer. Remove that now-redundant via instead of waiving dangling
# via DRC. Unconnected schematic pins must never acquire routed copper.
for t in list(B.GetTracks()):
    if t.GetNetname().lstrip('/').startswith('unconnected-'):B.Delete(t)
B.BuildConnectivity()
connectivity=B.GetConnectivity();unused=[]
for t in B.GetTracks():
    if isinstance(t,p.PCB_VIA) and t.GetNetname()!='/GND':
        if not (connectivity.IsConnectedOnLayer(t,p.F_Cu) and connectivity.IsConnectedOnLayer(t,p.B_Cu)):unused.append(t)
for t in unused:B.Delete(t)
print('Removed unused single-layer escape vias:',len(unused))

d=json.loads((H/'design.json').read_text())
colors={'J2':'0.02 0.20 0.35','J7':'0.32 0.08 0.40','J3':'0.03 0.20 0.45'}
for c in d['parts']:
    if c['ref'] not in ['J2','J3','J5','J6','J7']:continue
    fp=next(f for f in B.GetFootprints() if f.GetReference()==c['ref'])
    ox,oy=c['x'],c['y'];items=[]
    for pin in c['pins']:
        x,y=pin['x']-ox,-(pin['y']-oy)
        items.append(box((x,y,4.25),(2.5,2.5,8.5),'0.06 0.06 0.07'))
        items.append(box((x,y,8.85),(.64,.64,2.0),'0.65 0.58 0.35'))
    if c['ref'] in colors:
        a,b,e,f=c['rect'];cx,cy=(a+e)/2-ox,-((b+f)/2-oy)
        items.append(box((cx,cy,11.84),(e-a,f-b,1.6),colors[c['ref']]))
        items.append(box((cx,cy,13.8),(6,5,2.3),'0.10 0.10 0.12'))
        if c['ref']=='J3':
            items.append(box((cx,-(f-4-oy),16.3),(10,7,8.0),'0.16 0.45 0.12'))
    fn=c['ref']+'_SocketModule_NOMINAL.wrl'
    (H/'GemilaiMate.3dshapes'/fn).write_text('#VRML V2.0 utf8\n'+''.join(items))
    fp.Models().clear()
    m=p.FP_3DMODEL();m.m_Filename='${KIPRJMOD}/GemilaiMate.3dshapes/'+fn
    m.m_Scale.x=m.m_Scale.y=m.m_Scale.z=1
    fp.Models().append(m)
for t in B.GetTracks():
    if isinstance(t,p.PCB_VIA):
        t.SetFrontTentingMode(p.TENTING_MODE_TENTED);t.SetBackTentingMode(p.TENTING_MODE_TENTED)
# Sparse GND stitching joins the two pours around signal-routing islands.
# Exclude every pad, NPTH, RF area, foreign track and existing via. KiCad DRC
# remains the final check; this is not a clearance waiver or via-in-pad process.
def segdist(x,y,ax,ay,bx,by):
    dx,dy=bx-ax,by-ay
    t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(x-ax-t*dx,y-ay-t*dy)
pads=[pa for fp in B.GetFootprints() for pa in fp.Pads()]
tracks=list(B.GetTracks());existing=[t for t in tracks if isinstance(t,p.PCB_VIA)]
ground=next(n for n in B.GetNetsByNetcode().values() if n.GetNetname()=='/GND')
a,b,e,f=d['rf_keepout'];added=0
p.ZONE_FILLER(B).Fill(B.Zones())
front=next(z for z in B.Zones() if not z.GetIsRuleArea() and z.GetLayerSet().Contains(p.F_Cu))
back=next(z for z in B.Zones() if not z.GetIsRuleArea() and z.GetLayerSet().Contains(p.B_Cu))
fpoly=front.GetFilledPolysList(p.F_Cu);bpoly=back.GetFilledPolysList(p.B_Cu)
for ix in range(1,12):
 for iy in range(1,10):
    x,y=ix*7.62,iy*7.62
    vv=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
    if not fpoly.Contains(vv) or not bpoly.Contains(vv):continue
    if x>88 or y>73 or (a-.6<x<e+.6 and b-.6<y<f+.6):continue
    ok=True
    for pa in pads:
        q=pa.GetPosition();hx=p.ToMM(pa.GetSize().x)/2;hy=p.ToMM(pa.GetSize().y)/2
        dx=max(abs(x-p.ToMM(q.x))-hx,0);dy=max(abs(y-p.ToMM(q.y))-hy,0)
        if math.hypot(dx,dy)<.62:ok=False;break
    if not ok:continue
    for t in tracks:
        if isinstance(t,p.PCB_VIA):
            q=t.GetPosition()
            if math.hypot(x-p.ToMM(q.x),y-p.ToMM(q.y))<1.05:ok=False;break
        elif t.GetNetname()!='/GND':
            q,r=t.GetStart(),t.GetEnd()
            if segdist(x,y,p.ToMM(q.x),p.ToMM(q.y),p.ToMM(r.x),p.ToMM(r.y))<.62+p.ToMM(t.GetWidth())/2:ok=False;break
    if not ok:continue
    v=p.PCB_VIA(B);v.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
    v.SetWidth(p.FromMM(.7));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH)
    v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(ground)
    v.SetFrontTentingMode(p.TENTING_MODE_TENTED);v.SetBackTentingMode(p.TENTING_MODE_TENTED)
    B.Add(v);added+=1
# Reinforce any residual SMD pour islands with a via outside the pad.
# The router already connects GND explicitly; DRC still decides connectivity.
p.ZONE_FILLER(B).Fill(B.Zones())
fpoly=front.GetFilledPolysList(p.F_Cu);bpoly=back.GetFilledPolysList(p.B_Cu)
for ref in sorted({fp.GetReference() for fp in B.GetFootprints() for pa in fp.Pads() if pa.GetNetname()=='/GND' and pa.GetAttribute()==p.PAD_ATTRIB_SMD}):
 fp=next(fp for fp in B.GetFootprints() if fp.GetReference()==ref)
 pa=next(pa for pa in fp.Pads() if pa.GetNetname()=='/GND')
 q=pa.GetPosition();cx,cy=p.ToMM(q.x),p.ToMM(q.y)
 island=next((i for i in range(fpoly.OutlineCount()) if fpoly.Contains(q,i)),None)
 if island is None:raise RuntimeError('GND pad has no pour: '+ref)
 if any(isinstance(t,p.PCB_VIA) and t.GetNetname()=='/GND' and fpoly.Contains(t.GetPosition(),island) and bpoly.Contains(t.GetPosition()) for t in B.GetTracks()):continue
 placed=False
 offsets=sorted([(ix*.254,iy*.254) for ix in range(-16,17) for iy in range(-16,17) if 1.0<=math.hypot(ix*.254,iy*.254)<=4.064],key=lambda q:(math.hypot(*q),q[0],q[1]))
 for dx,dy in offsets:
    x,y=cx+dx,cy+dy;ok=True
    vv=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
    if not fpoly.Contains(vv,island) or not bpoly.Contains(vv):continue
    for pad in pads:
        pq=pad.GetPosition();hx=p.ToMM(pad.GetSize().x)/2;hy=p.ToMM(pad.GetSize().y)/2
        distance=math.hypot(max(abs(x-p.ToMM(pq.x))-hx,0),max(abs(y-p.ToMM(pq.y))-hy,0))
        if distance<(.4 if pad.GetNetname()=='/GND' else .62):ok=False;break
    if not ok:continue
    for t in B.GetTracks():
        if isinstance(t,p.PCB_VIA):
            pq=t.GetPosition()
            if math.hypot(x-p.ToMM(pq.x),y-p.ToMM(pq.y))<1.05:ok=False;break
        elif t.GetNetname()!='/GND':
            pq,r=t.GetStart(),t.GetEnd()
            if segdist(x,y,p.ToMM(pq.x),p.ToMM(pq.y),p.ToMM(r.x),p.ToMM(r.y))<.56+p.ToMM(t.GetWidth())/2:ok=False;break
    if not ok:continue
    v=p.PCB_VIA(B);v.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
    v.SetWidth(p.FromMM(.7));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH)
    v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(ground)
    v.SetFrontTentingMode(p.TENTING_MODE_TENTED);v.SetBackTentingMode(p.TENTING_MODE_TENTED)
    B.Add(v);added+=1;placed=True;print('SMD ground bridge:',ref,x,y);break
 if not placed:print('No SMD bridge candidate:',ref)
for fp in B.GetFootprints():
    if fp.GetReference() in {c['ref'] for c in d['parts']}:p.FootprintSave(str(H/'GemilaiMate.pretty'),fp)
p.ZONE_FILLER(B).Fill(B.Zones())
p.SaveBoard(str(H/'gemilaimate-shield.kicad_pcb'),B)
print('Schematic net names aligned; nominal socket/module 3D and filled GND saved.')
print('New GND stitching vias:',added)
