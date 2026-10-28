#!/usr/bin/env python3
"""Export the saved current PCB. Requires KiCad 10 CLI and its pcbnew Python."""
from pathlib import Path
import argparse,subprocess,shutil,zipfile,json,sys
ROOT=Path(__file__).resolve().parents[1];H=ROOT/'hardware/carrier'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kicad-cli',default=shutil.which('kicad-cli'));ap.add_argument('--kicad-python',required=True);args=ap.parse_args()
 if not args.kicad_cli:ap.error('Supply --kicad-cli /path/to/kicad-cli')
 cli=args.kicad_cli;m=H/'manufacturing';g=m/'gerber';g.mkdir(parents=True,exist_ok=True);pv=H/'previews';pv.mkdir(exist_ok=True)
 def run(a):subprocess.run([cli]+a,check=True)
 pcb=str(H/'gemilaimate-carrier.kicad_pcb');sch=str(H/'gemilaimate-carrier.kicad_sch')
 run(['sch','export','netlist','-o',str(H/'gemilaimate-carrier.net'),sch]);subprocess.run([sys.executable,str(H/'scripts/verify_netlist.py')],check=True)
 run(['pcb','export','pos','--format','csv','--units','mm','--smd-only','--exclude-fp-th','--side','front','-o',str(m/'positions-kicad.csv'),pcb])
 subprocess.run([args.kicad_python,str(H/'scripts/export_manufacturing.py')],check=True)
 run(['sch','erc','--severity-all','--format','json','-o',str(H/'erc.json'),sch]);run(['pcb','drc','--schematic-parity','--severity-all','--format','json','-o',str(H/'drc.json'),pcb])
 erc=json.loads((H/'erc.json').read_text());drc=json.loads((H/'drc.json').read_text())
 if any(x['violations'] for x in erc['sheets']) or any(drc[x] for x in ['violations','unconnected_items','schematic_parity']):raise SystemExit('ERC/DRC failed; do not publish fabrication files')
 for old in g.iterdir():
  if old.is_file():old.unlink()
 run(['pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts','-o',str(g)+'/',pcb])
 run(['pcb','export','drill','--format','excellon','--excellon-separate-th','--generate-report','--report-path',str(m/'drill-report.txt'),'-o',str(g)+'/',pcb])
 for name,layers in [('board-top','F.Cu,F.Mask,F.Silkscreen,Edge.Cuts'),('board-bottom','B.Cu,B.Mask,B.Silkscreen,Edge.Cuts'),('assembly-top','F.Fab,F.Silkscreen,Edge.Cuts')]:
  run(['pcb','export','svg','--layers',layers,'--mode-single','--page-size-mode','2','--exclude-drawing-sheet','-o',str(pv/(name+'.svg'))]+(['--mirror'] if name=='board-bottom' else [])+[pcb])
 run(['sch','export','svg','-o',str(pv)+'/',sch])
 subprocess.run([sys.executable,str(H/'scripts/make_3d_models.py')],check=True)
 for name,view in [('assembled-3d-front',['--rotate','-55,0,-30','--perspective','--zoom','0.95','--floor','-h','1500']),('assembled-3d-back',['--rotate','-55,0,145','--perspective','--zoom','0.95','--floor','-h','1500']),('assembled-3d-top',['-h','1400'])]:
  run(['pcb','render','--side','top','--quality','high','--background','opaque','-w','2400']+view+['-o',str(pv/(name+'.png')),pcb])
 with zipfile.ZipFile(m/'gerber-drill.zip','w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(g.iterdir()):z.write(p,p.name)
 print('Current hardware export passed ERC/DRC/parity and 13 GPIO checks')
if __name__=='__main__':main()
