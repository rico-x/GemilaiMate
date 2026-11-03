#!/usr/bin/env python3
"""True-size print with a positive page origin; never changes the source PCB."""
import gc;gc.disable()
from pathlib import Path
import sys,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
# Put the antenna and all PCB edges inside A4, instead of clipping negative Y.
delta=V(10,20)
for f in B.GetFootprints():f.Move(delta)
for t in B.GetTracks():t.Move(delta)
for z in B.Zones():z.Move(delta)
for a in B.GetDrawings():a.Move(delta)
# Nominal daughterboard outlines supplement the socket rows in the 1:1 print.
import json
D=json.loads((H/'design.json').read_text())
for key,mod in D['module_sockets'].items():
 x,y,e,g=mod['body_rect_mm']
 for start,end in [((x,y),(e,y)),((e,y),(e,g)),((e,g),(x,g)),((x,g),(x,y))]:
  s=p.PCB_SHAPE(B);s.SetShape(p.SHAPE_T_SEGMENT);s.SetLayer(p.Dwgs_User);s.SetWidth(p.FromMM(.1));s.SetStart(V(start[0]+10,start[1]+20));s.SetEnd(V(end[0]+10,end[1]+20));B.Add(s)
 t=p.PCB_TEXT(B);t.SetText(key+' NOMINAL');t.SetPosition(V((x+e)/2+10,y+21));t.SetTextSize(V(.8,.8));t.SetLayer(p.Dwgs_User);B.Add(t)
board_size=D['size_mm']
for x,y,text,size in [(43,6,f'GemilaiMate Compact Shield / PRINT 100% / PCB {board_size[0]} x {board_size[1]} mm',1),(43,9,'PROTOTYPE: verify actual modules and enclosure',.85),(18,100,'10 mm calibration',1)]:
 t=p.PCB_TEXT(B);t.SetText(text);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetLayer(p.Dwgs_User);B.Add(t)
for a,b in [((10,97),(20,97)),((10,96),(10,98)),((20,96),(20,98))]:
 s=p.PCB_SHAPE(B);s.SetShape(p.SHAPE_T_SEGMENT);s.SetLayer(p.Dwgs_User);s.SetWidth(p.FromMM(.15));s.SetStart(V(*a));s.SetEnd(V(*b));B.Add(s)
with tempfile.TemporaryDirectory() as tmp:
 f=Path(tmp)/'compact-template.kicad_pcb';p.SaveBoard(str(f),B)
 subprocess.run(['kicad-cli','pcb','export','pdf','--layers','F.Fab,F.Silkscreen,Dwgs.User,Edge.Cuts','--black-and-white','--scale','1','--mode-single','-o',str(H/'previews/assembly-1to1.pdf'),str(f)],check=True)
print('Exported unclipped 1:1 A4 template and a 10mm calibration bar; source PCB unchanged')
