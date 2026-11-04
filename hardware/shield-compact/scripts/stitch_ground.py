#!/usr/bin/env python3
"""Propose deterministic GND stitches in free copper, without moving signals.

Run on a checked, widened board on the CAD host. This edits routing.json only;
re-import/finish and fresh KiCad all-severity DRC must accept the result.
"""
import gc;gc.disable()
import json,math
from pathlib import Path
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from ground_integrity import p,H,ground_polygons
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'));mm=p.ToMM
D=json.loads((H/'design.json').read_text());route=json.loads((H/'routing.json').read_text())
polys=ground_polygons(B);ground={l:unary_union(s) for l,s in polys.items()}
# Keep complete annuli inside both pours. Foreign drills and pad exclusion
# below are stricter than simply trusting existing fills.
free=ground[p.F_Cu].buffer(-.1).intersection(ground[p.B_Cu].buffer(-.1))
blocked=[];anchors=[]
for f in B.GetFootprints():
 for a in f.Pads():
  q=a.GetPosition();point=Point(mm(q.x),mm(q.y));bb=a.GetBoundingBox()
  copper=box(mm(bb.GetLeft()),mm(bb.GetTop()),mm(bb.GetRight()),mm(bb.GetBottom()))
  if a.GetNetname()!='GND':blocked.append(copper.buffer(.72))
  # No new unfilled via-in-pad, including same-net lands.
  else:blocked.append(copper.buffer(.22))
  if a.GetAttribute()!=p.PAD_ATTRIB_SMD:
   blocked.append(point.buffer(max(mm(a.GetDrillSize().x),mm(a.GetDrillSize().y))/2+.86))
   if a.GetNetname()=='GND':anchors.append(point)
for t in B.GetTracks():
 if isinstance(t,p.PCB_VIA):
  q=t.GetPosition();point=Point(mm(q.x),mm(q.y));blocked.append(point.buffer(max(.86+mm(t.GetDrillValue())/2,.72+mm(t.GetWidth(p.F_Cu))/2)))
  if t.GetNetname()=='GND':anchors.append(point)
 elif t.GetNetname()!='GND':
  a,b=t.GetStart(),t.GetEnd();blocked.append(LineString([(mm(a.x),mm(a.y)),(mm(b.x),mm(b.y))]).buffer(mm(t.GetWidth())/2+.72))
for x,y in D['mounts_mm']:blocked.append(Point(x,y).buffer(D['mount_keepout_radius_mm']+.42))
for z in B.Zones():
 if not z.GetIsRuleArea() or not z.GetDoNotAllowVias():continue
 # Rule-area outlines include the antenna keepout and mounting/edge bands.
 from shapely.geometry import Polygon
 o=z.Outline()
 for i in range(o.OutlineCount()):
  ring=o.Outline(i);blocked.append(Polygon([(mm(ring.CPoint(k).x),mm(ring.CPoint(k).y)) for k in range(ring.PointCount())]).buffer(.42))
free=free.intersection(box(.92,.92,D['size_mm'][0]-.92,D['size_mm'][1]-.92)).difference(unary_union(blocked))
# Fixed half-mm grid; USB vicinity first, then cover remaining free regions.
usb_points=[]
for t in B.GetTracks():
 if t.GetNetname().startswith('USB_D'):
  q=t.GetPosition() if isinstance(t,p.PCB_VIA) else t.GetStart();usb_points.append(Point(mm(q.x),mm(q.y)))
candidates=[Point(ix*.5,iy*.5) for ix in range(2,int(D['size_mm'][0]*2)-1) for iy in range(2,int(D['size_mm'][1]*2)-1) if free.contains(Point(ix*.5,iy*.5))]
def usb_dist(q):return min(q.distance(a) for a in usb_points)
candidates.sort(key=lambda q:(0 if usb_dist(q)<2.5 else 1,round(usb_dist(q),3),q.x,q.y))
added=[]
for q in candidates:
 spacing=2.5 if usb_dist(q)<2.5 else 5.0
 if any(q.distance(a)<spacing for a in anchors):continue
 added.append([q.x,q.y]);anchors.append(q)
for xy in added:route['items'].append(dict(net='GND',locked=False,kind='via',xy=xy,diameter=.8,drill=.4))
(H/'routing.json').write_text(json.dumps(route,ensure_ascii=False,indent=2)+'\n')
(H/'reports/ground-stitching.json').write_text(json.dumps({'added_vias':len(added),'positions_mm':added,'signal_routing_changed':False,'via_diameter_mm':.8,'drill_mm':.4,'minimum_spacing_to_foreign_copper_mm':.32,'minimum_new_drill_to_foreign_copper_mm':.52,'minimum_hole_to_hole_mm':.66,'hardware_tested':False},indent=2)+'\n')
print('Proposed',len(added),'GND stitches; fresh re-import/finish/DRC required')
