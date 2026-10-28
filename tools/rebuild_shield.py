#!/usr/bin/env python3
"""Rebuild/validate all shield artifacts; supports Linux without DISPLAY."""
import argparse,os,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--kicad-python',required=True)
ap.add_argument('--kicad-cli',required=True)
a=ap.parse_args()
print('Shield rebuild: DISPLAY='+repr(os.environ.get('DISPLAY')),flush=True)
def run(python,script,*args):
 subprocess.run([python,str(R/script),*args],cwd=R,check=True)
for name in ['make_shield.py','route_shield.py']:
 run(a.kicad_python,'hardware/shield/scripts/'+name)
run(sys.executable,'hardware/shield/scripts/make_schematic.py')
run(sys.executable,'tools/export_shield.py','--kicad-python',a.kicad_python,'--kicad-cli',a.kicad_cli)
run(sys.executable,'tools/build_shield_page.py')
run(sys.executable,'tools/build_wiring_page.py')
run(sys.executable,'tools/check_shield.py','--write-report')
run(sys.executable,'tools/check_project.py')
print('PASS complete shield rebuild and artifact checks',flush=True)
