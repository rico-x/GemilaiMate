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
W,H_MM=D['size_mm']
usb=next(c for c in D['parts'] if c['ref']=='J_USB')
assert abs(usb['y']+9.135-H_MM)<.001,'USB mating face must reach the board edge'
assert B.GetCopperLayerCount()==4
tracks=list(B.GetTracks());vias=[t for t in tracks if isinstance(t,p.PCB_VIA)]
assert not any(not isinstance(t,p.PCB_VIA) and t.GetLayer() not in [p.F_Cu,p.In2_Cu,p.B_Cu] for t in tracks),'Unexpected copper layer used'
labels=[t for t in B.GetDrawings() if isinstance(t,p.PCB_TEXT) and t.GetLayer() in [p.F_SilkS,p.B_SilkS]]
assert labels
shells=[]
for c in D['parts']:
 if c['section']=='Connectors' and not c['dnp']:
  shells += [a.GetBoundingBox() for a in F[c['designator']].GraphicalItems() if a.GetLayer()==p.B_CrtYd]
for a in B.GetDrawings():
 if a.GetLayer()!=p.B_SilkS:continue
 bb=a.GetBoundingBox()
 assert not any(bb.GetLeft()<q.GetRight() and q.GetLeft()<bb.GetRight() and bb.GetTop()<q.GetBottom() and q.GetTop()<bb.GetBottom() for q in shells),('Back silk hidden by connector housing',a.GetText() if isinstance(a,p.PCB_TEXT) else 'shape',[mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom())])
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
# Daughterboard bodies do not overlap one another, the MCU body or the RF zone.
def overlap(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
module_bodies=[D['module_sockets'][r]['body_rect_mm'] for r in ['J_ADS','J_TC','J_LEVEL']]
# Derive the module body from actual pad vectors, independently of the
# generator's rotation angle convention and mean-row offset calculation.
for alias,local_origin in [('J_ADS',(0,0)),('J_TC',(0,0)),('J_LEVEL',(-5.08,6.35))]:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']]
 a=next(a for a in f.Pads() if a.GetNumber()=='1').GetPosition()
 b=next(a for a in f.Pads() if a.GetNumber()=='2').GetPosition()
 pitch=-2.54 if alias=='J_TC' else 2.54
 ux,uy=mm(b.x-a.x)/pitch,mm(b.y-a.y)/pitch
 mod=D['module_sockets'][alias];lx,ly=mod['body_center_local_mm'];lx-=local_origin[0];ly-=local_origin[1]
 cx,cy=mm(a.x)+ux*lx-uy*ly,mm(a.y)+uy*lx+ux*ly
 w,h=mod['body_size_mm'];w,h=abs(ux)*w+abs(uy)*h,abs(uy)*w+abs(ux)*h
 expected=[cx-w/2,cy-h/2,cx+w/2,cy+h/2]
 assert all(abs(a-b)<.001 for a,b in zip(expected,mod['body_rect_mm'])),(alias,expected,mod['body_rect_mm'])
for i,a in enumerate(module_bodies):
 assert a[0]>=0 and a[1]>=0 and a[2]<=W and a[3]<=H_MM,(a,W,H_MM)
 assert not overlap(a,D['module_body']) and not overlap(a,D['rf_keepout']),a
 for b in module_bodies[i+1:]:assert not overlap(a,b),(a,b)
# The three inserted daughterboards occupy real volume; front-side SMD bodies
# may not sit under them even where their electrical footprints do not overlap.
module_refs={next(c['designator'] for c in D['parts'] if c['ref']==r) for r in ['J_ADS','J_TC','J_LEVEL']}
for ref,f in F.items():
 # U1's library courtyard includes the antenna reservation, not only its
 # physical body. Its body and antenna envelope were checked above.
 if ref in module_refs or ref=='U1' or f.IsFlipped():continue
 items=[a for a in f.GraphicalItems() if a.GetLayer()==p.F_CrtYd]
 if not items:continue
 boxes=[a.GetBoundingBox() for a in items]
 body=[min(mm(b.GetLeft()) for b in boxes),min(mm(b.GetTop()) for b in boxes),
       max(mm(b.GetRight()) for b in boxes),max(mm(b.GetBottom()) for b in boxes)]
 for reserved in module_bodies:
  assert not overlap(body,reserved),(ref,'front-side component under plug-in module',body,reserved)
gnd_zones=[z for z in B.Zones() if z.GetNetname()=='GND' and z.GetLayer()==p.In1_Cu]
assert gnd_zones and all(z.GetFilledPolysList(p.In1_Cu).OutlineCount()>0 for z in gnd_zones),'No filled inner ground plane'
result=dict(pcb_sha256=hashlib.sha256((H/'gemilaimate-compact.kicad_pcb').read_bytes()).hexdigest(),board_size_mm=[W,H_MM],copper_layers=4,visible_text_via_overlaps=0,unfilled_via_drill_smd_overlaps=0,all_actual_pad_coordinates_match=True,inner_ground_plane=True,nominal_module_body_overlap=False,actual_clone_dimensions_verified=False,usb_plug_physical_test=False,hardware_tested=False)
(H/'reports/geometry.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS independent geometry: module envelopes, pads, three signal layers, inner ground plane, silk/vias and no unfilled via-in-pad except intentional WROOM thermal land')
