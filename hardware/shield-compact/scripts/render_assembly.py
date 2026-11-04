#!/usr/bin/env python3
"""Render fitted parts only; never alter the accepted PCB.

Build a fitted-only temporary PCB beside the original, independent of viewer
preferences. Relative 3D paths keep resolving to the same bundled files; the
accepted PCB retains the optional footprints and hidden models.
"""
import gc
gc.disable()
import os
from pathlib import Path
import subprocess
import sys
import tempfile
R=Path(__file__).resolve().parents[3]
H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'hardware/shield/scripts'))
from kicad_runtime import application
app=application()
import pcbnew as p
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
removed=[]
for f in B.GetFootprints():
    if f.IsDNP():
        removed.append(f.GetReference())
        f.Models().clear()
fd,name=tempfile.mkstemp(prefix='.fitted-',suffix='.kicad_pcb',dir=H)
os.close(fd)
temporary=Path(name)
try:
    p.SaveBoard(str(temporary),B)
    for name,side,rotation in [('assembled-front','top','-50,0,-25'),('assembled-back','bottom','-50,0,25')]:
        subprocess.run(['kicad-cli','pcb','render','--side',side,'--quality','high','--background','opaque','--rotate',rotation,'--perspective','-w','1600','-h','1000','-o',str(H/'previews'/(name+'.png')),str(temporary)],check=True)
finally:
    temporary.unlink(missing_ok=True)
    for suffix in ['.kicad_pro','.kicad_prl']:
        temporary.with_suffix(suffix).unlink(missing_ok=True)
print('Rendered fitted assembly; DNP models omitted only in temporary view:',', '.join(removed))
