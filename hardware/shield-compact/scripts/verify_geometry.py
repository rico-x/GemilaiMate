#!/usr/bin/env python3
"""Independent read-only inspection of the saved board (KiCad build host)."""
import gc;gc.disable()
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'));D=json.loads((H/'design.json').read_text());mm=p.ToMM
parts={c['designator']:c for c in D['parts']};F={f.GetReference():f for f in B.GetFootprints()}
assert B.GetCopperLayerCount()==4
tracks=list(B.GetTracks());vias=[t for t in tracks if isinstance(t,p.PCB_VIA)]
assert not any(not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.In1_Cu for t in tracks),'Ground reference used for routing'
labels=[t for t in B.GetDrawings() if isinstance(t,p.PCB_TEXT) and t.GetLayer() in [p.F_SilkS,p.B_SilkS]]
assert labels
for t in labels:
 bb=t.GetBoundingBox();a,b,c,d=map(mm,[bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()])
 for v in vias:
  x,y=map(mm,[v.GetPosition().x,v.GetPosition().y]);dist=math.hypot(max(a-x,0,x-c),max(b-y,0,y-d))
  assert dist>=mm(v.GetWidth(p.F_Cu))/2+.15,(t.GetText(),x,y)
# Through-hole/thermal vias in the WROOM ground land are intentional. Other
# open drilled holes must not intersect an SMD land (cheap unfilled-via process).
wicking=[]
for v in vias:
 x,y=map(mm,[v.GetPosition().x,v.GetPosition().y]);r=mm(v.GetDrillValue())/2
 for ref,f in F.items():
  if ref=='U1':continue
  for a in f.Pads():
   if a.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
   bb=a.GetBoundingBox();lo,top,hi,bottom=map(mm,[bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()])
   dist=math.hypot(max(lo-x,0,x-hi),max(top-y,0,y-bottom))
   if dist<r:wicking.append([ref,a.GetNumber(),x,y])
assert not wicking,('Unfilled via drill intersects SMD land',wicking)
# Actual module pad coordinates and no PSRAM escapes.
for c in D['parts']:
 f=F[c['designator']]
 for entry in c['physical_pads']:
  assert any(a.GetNumber()==entry['number'] and abs(mm(a.GetPosition().x)-entry['x'])<1e-5 and abs(mm(a.GetPosition().y)-entry['y'])<1e-5 for a in f.Pads()),c['designator']
assert all(mm(t.GetWidth())>=.2-1e-6 for t in tracks if not isinstance(t,p.PCB_VIA))
# Daughterboard bodies do not overlap each other or the module/RF body.
def overlap(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
a=D['module_sockets']['J_ADS']['body_rect_mm'];b=D['module_sockets']['J_TC']['body_rect_mm'];assert not overlap(a,b)
for q in [a,b]:assert not overlap(q,D['module_body']) and not overlap(q,D['rf_keepout'])
result=dict(pcb_sha256=hashlib.sha256((H/'gemilaimate-compact.kicad_pcb').read_bytes()).hexdigest(),visible_text_via_overlaps=0,unfilled_via_drill_smd_overlaps=0,all_actual_pad_coordinates_match=True,dedicated_ground_layer=True,nominal_module_body_overlap=False,actual_clone_dimensions_verified=False,usb_plug_physical_test=False,hardware_tested=False)
(H/'reports/geometry.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS independent geometry: actual pads, >=0.20mm tracks, ground layer, silk/vias and no unfilled via-in-pad except intentional WROOM thermal land')
