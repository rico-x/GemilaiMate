#!/usr/bin/env python3
"""Measure filled GND islands and USB return coverage; KiCad Python on build host.

Coverage is a geometric proxy: opposite-layer GND pour intersected by the
track centreline. It is not an impedance, EMC or hardware validation test.
"""
import gc;gc.disable()
import argparse,json,sys
from pathlib import Path
from shapely.geometry import Point,Polygon,LineString
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p

def ground_polygons(board):
 result={p.F_Cu:[],p.B_Cu:[]}
 def coords(outline):return [(p.ToMM(outline.CPoint(k).x),p.ToMM(outline.CPoint(k).y)) for k in range(outline.PointCount())]
 for z in board.Zones():
  if z.GetIsRuleArea() or z.GetNetname()!='GND':continue
  layer=z.GetLayer();polys=z.GetFilledPolysList(layer)
  for i in range(polys.OutlineCount()):
   shape=Polygon(coords(polys.Outline(i)),[coords(polys.Hole(i,j)) for j in range(polys.HoleCount(i))]).buffer(0)
   if not shape.is_empty:result[layer].append(shape)
 return result

def measure(board):
 mm=p.ToMM;polys=ground_polygons(board);ground={l:unary_union(s) for l,s in polys.items()}
 tracks=list(board.GetTracks());usb={}
 for net in ['USB_DP','USB_DM','USB_DP_MCU','USB_DM_MCU']:
  segments=[t for t in tracks if not isinstance(t,p.PCB_VIA) and t.GetNetname()==net]
  length=sum(mm(t.GetLength()) for t in segments);covered=0
  for t in segments:
   a,b=t.GetStart(),t.GetEnd();line=LineString([(mm(a.x),mm(a.y)),(mm(b.x),mm(b.y))])
   covered+=line.intersection(ground[p.B_Cu if t.GetLayer()==p.F_Cu else p.F_Cu]).length
  usb[net]={'length_mm':round(length,4),'signal_vias':sum(isinstance(t,p.PCB_VIA) and t.GetNetname()==net for t in tracks),
            'opposite_gnd_pour_coverage_percent':round(100*covered/length,2) if length else None}
 vias=[t for t in tracks if isinstance(t,p.PCB_VIA) and t.GetNetname()=='GND']
 bridges=[(Point(mm(v.GetPosition().x),mm(v.GetPosition().y)),mm(v.GetWidth(p.F_Cu))/2) for v in vias]
 for f in board.GetFootprints():
  for a in f.Pads():
   if a.GetNetname()=='GND' and a.GetAttribute()==p.PAD_ATTRIB_PTH:
    bridges.append((Point(mm(a.GetPosition().x),mm(a.GetPosition().y)),max(mm(a.GetSize().x),mm(a.GetSize().y))/2))
 for net,entry in usb.items():
  entry['via_return_bridge_distances_mm']=[]
  for t in tracks:
   if isinstance(t,p.PCB_VIA) and t.GetNetname()==net:
    q=Point(mm(t.GetPosition().x),mm(t.GetPosition().y))
    entry['via_return_bridge_distances_mm'].append(round(min(q.distance(a) for a,_ in bridges),3))
  entry['via_return_bridge_distances_mm'].sort()
 return {'gnd_vias':len(vias),'ground_pours':{board.GetLayerName(l):{'regions':len(s),'largest_region_mm2':round(max((x.area for x in s),default=0),3),'total_area_mm2':round(sum(x.area for x in s),3)} for l,s in polys.items()},
         'usb':usb,'coverage_method':'Track centreline intersected with filled opposite-layer GND pour; pad/track copper excluded. Not a return-path or impedance simulation.',
         'hardware_tested':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--pcb',type=Path,default=H/'gemilaimate-compact.kicad_pcb');ap.add_argument('--output',type=Path,default=H/'reports/ground-integrity.json');a=ap.parse_args()
 report=measure(p.LoadBoard(str(a.pcb)));a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
