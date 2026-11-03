#!/usr/bin/env python3
import gc;gc.disable()
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-finish')
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
D=json.loads((H/'design.json').read_text())
# The complete accepted copper is explicit project source, including the
# manually completed branches. No router session or editor frame is required.
route=json.loads((H/'routing.json').read_text())
assert route['revision']==D['revision'] and route['size_mm']==D['size_mm']
removed=list(B.GetTracks())
for t in removed:B.Remove(t);t.thisown=False
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
for item in route['items']:
 net=B.FindNet(item['net']);assert net and net.GetNetCode()>0,item['net']
 if item['kind']=='track':
  t=p.PCB_TRACK(B);t.SetStart(V(*item['start']));t.SetEnd(V(*item['end']));t.SetWidth(p.FromMM(item['width']));t.SetLayer(B.GetLayerID(item['layer']))
 else:
  t=p.PCB_VIA(B);t.SetPosition(V(*item['xy']));t.SetWidth(p.FromMM(item['diameter']));t.SetDrill(p.FromMM(item['drill']));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu)
 t.SetNet(net);t.SetLocked(item['locked']);B.Add(t)
W,H_MM=D['size_mm']
# Keep the continuous inner ground reference. Outer power pours connect the
# distributed supply loads without narrowing the generous routing channels.
for layer,name in [(p.F_Cu,'+3V3'),(p.In1_Cu,'GND'),(p.In2_Cu,'+3V3'),(p.B_Cu,'+5V_EXT')]:
 z=p.ZONE(B);z.SetLayer(layer);z.SetNet(B.FindNet(name));z.SetLocalClearance(p.FromMM(.3));z.SetThermalReliefGap(p.FromMM(.2));z.SetThermalReliefSpokeWidth(p.FromMM(.3));z.SetMinThickness(p.FromMM(.15))
 z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS);z.SetPadConnection(p.ZONE_CONNECTION_THERMAL);o=z.Outline();o.NewOutline()
 for x,y in [(.4,.4),(W-.4,.4),(W-.4,H_MM-.4),(.4,H_MM-.4)]:o.Append(int(p.FromMM(x)),int(p.FromMM(y)))
 B.Add(z)
p.ZONE_FILLER(B).Fill(B.Zones())
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
print('Imported complete accepted routing and filled ground/power planes.')
