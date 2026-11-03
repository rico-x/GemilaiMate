#!/usr/bin/env python3
import gc;gc.disable()
import sys,json,sexpdata as s
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-finish')
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
# The SES holds only new routes; preserve the locked pre-route. Parse the
# documented Specctra paths directly so a headless KiCad import cannot depend
# on an editor frame. Fresh KiCad DRC/parity checks the resulting geometry.
def child(node,key):return [x for x in node if isinstance(x,list) and str(x[0])==key]
ses=s.loads((H/'reports/routed.ses').read_text());routes=child(ses,'routes')[0]
res=child(routes,'resolution')[0];assert str(res[1])=='um';scale=1000*float(res[2])
network=child(routes,'network_out')[0]
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
for item in network[1:]:
 if str(item[0])!='net':continue
 net=B.FindNet(str(item[1]));assert net and net.GetNetCode()>0,str(item[1])
 for wire in child(item,'wire'):
  path=child(wire,'path')[0];layer=B.GetLayerID(str(path[1]));width=max(.2,float(path[2])/scale)
  pts=[(float(path[i])/scale,-float(path[i+1])/scale) for i in range(3,len(path),2)]
  for a,b in zip(pts,pts[1:]):
   if a==b:continue
   t=p.PCB_TRACK(B);t.SetStart(V(*a));t.SetEnd(V(*b));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(net);B.Add(t)
 for v in child(item,'via'):
  assert str(v[1])=='Via[0-3]_700:350_um'
  t=p.PCB_VIA(B);t.SetPosition(V(float(v[2])/scale,-float(v[3])/scale));t.SetWidth(p.FromMM(.7));t.SetDrill(p.FromMM(.35));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(net);B.Add(t)
for layer in [p.F_Cu,p.In1_Cu]:
 z=p.ZONE(B);z.SetLayer(layer);z.SetNet(B.FindNet('GND'));z.SetLocalClearance(p.FromMM(.15));z.SetThermalReliefGap(p.FromMM(.2));z.SetThermalReliefSpokeWidth(p.FromMM(.3));z.SetMinThickness(p.FromMM(.15))
 z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS);z.SetPadConnection(p.ZONE_CONNECTION_THERMAL);o=z.Outline();o.NewOutline()
 for x,y in [(0.4,.4),(64.6,.4),(64.6,49.6),(.4,49.6)]:o.Append(int(p.FromMM(x)),int(p.FromMM(y)))
 B.Add(z)
p.ZONE_FILLER(B).Fill(B.Zones())
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
print('Imported SES and filled ground planes.')
