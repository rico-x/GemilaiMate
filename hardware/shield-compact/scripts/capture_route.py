#!/usr/bin/env python3
"""Store a reviewed router session as explicit copper in routing.json.

Run on the build host after prepare_route.py and Freerouting: the prepared
board holds the locked USB/ID routes, the SES adds the routed copper. The
Specctra paths are parsed directly: a headless KiCad SES import needs an
editor frame.
"""
import gc;gc.disable()
import sys,json,sexpdata as s
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p
ses_path=Path(sys.argv[1]) if len(sys.argv)>1 else H/'reports/routed.ses'
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'));D=json.loads((H/'design.json').read_text())
mm=lambda v:round(p.ToMM(v),6)
def child(node,key):return [x for x in node if isinstance(x,list) and str(x[0])==key]
items=[]
def track(net,locked,start,end,width,layer):
 a,b=sorted([[round(start[0],6),round(start[1],6)],[round(end[0],6),round(end[1],6)]])
 items.append(dict(net=net,locked=locked,kind='track',start=a,end=b,width=round(width,6),layer=layer))
def via(net,locked,xy,diameter,drill):
 items.append(dict(net=net,locked=locked,kind='via',xy=[round(xy[0],6),round(xy[1],6)],diameter=diameter,drill=drill))
for t in B.GetTracks():
 if isinstance(t,p.PCB_VIA):via(t.GetNetname(),bool(t.IsLocked()),(mm(t.GetPosition().x),mm(t.GetPosition().y)),mm(t.GetWidth(p.F_Cu)),mm(t.GetDrillValue()))
 else:track(t.GetNetname(),bool(t.IsLocked()),(mm(t.GetStart().x),mm(t.GetStart().y)),(mm(t.GetEnd().x),mm(t.GetEnd().y)),mm(t.GetWidth()),B.GetLayerName(t.GetLayer()))
fixed={json.dumps({k:v for k,v in x.items() if k!='locked'},sort_keys=True) for x in items}
ses=s.loads(ses_path.read_text());routes=child(ses,'routes')[0]
res=child(routes,'resolution')[0];assert str(res[1])=='um';scale=1000*float(res[2])
added=0
for item in child(routes,'network_out')[0][1:]:
 if str(item[0])!='net':continue
 name=str(item[1]);net=B.FindNet(name);assert net and net.GetNetCode()>0,name
 before=len(items)
 for wire in child(item,'wire'):
  path=child(wire,'path')[0];layer=str(path[1]);width=float(path[2])/scale
  pts=[(float(path[i])/scale,-float(path[i+1])/scale) for i in range(3,len(path),2)]
  for a,b in zip(pts,pts[1:]):
   if a!=b:track(name,False,a,b,width,layer)
 for v in child(item,'via'):
  assert str(v[1])=='Via[0-3]_800:400_um',v[1]
  via(name,False,(float(v[2])/scale,-float(v[3])/scale),.8,.4)
 # Locked pre-routes come back from the router as fixed wiring: keep one copy.
 new=[x for x in items[before:] if json.dumps({k:v for k,v in x.items() if k!='locked'},sort_keys=True) not in fixed]
 items[before:]=new;added+=len(new)
items.sort(key=lambda x:json.dumps(x,sort_keys=True))
route=dict(revision=D['revision'],size_mm=D['size_mm'],units='mm',
           origin='Freerouting 2.5.0 session plus locked USB/ID routes; saved before automatic widening',
           hardware_tested=False,items=items)
(H/'routing.json').write_text(json.dumps(route,indent=2)+'\n')
print('Captured',len(items),'copper items,',added,'from',ses_path.name)
