#!/usr/bin/env python3
"""Validate/export the second, socketed prototype without changing carrier v0.1."""
from pathlib import Path
import argparse,subprocess,sys,shutil,json,zipfile,os,hashlib,re
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield'
sys.path.insert(0,str(H/'scripts'))
from revision import REVISION,DATE,ARCHIVE,pin_timestamps
def pin(path,*markers):
 # Generation timestamps -> revision date, only on the lines that carry them.
 lines=path.read_text().split('\n')
 path.write_text('\n'.join(pin_timestamps(l) if any(m in l for m in markers) else l for l in lines))
def previews(run,pcb,sch):
 pv=H/'previews';pv.mkdir(exist_ok=True)
 for name,layers in [('board-top','F.Cu,F.Mask,F.Silkscreen,Edge.Cuts'),('board-bottom','B.Cu,B.Mask,B.Silkscreen,Edge.Cuts'),('assembly-top','F.Fab,F.Silkscreen,Edge.Cuts'),('orientation-silkscreen','F.Silkscreen,Edge.Cuts')]:
  run('pcb','export','svg','--layers',layers,'--mode-single','--page-size-mode','2','--exclude-drawing-sheet','-o',pv/(name+'.svg'),*(['--mirror'] if name=='board-bottom' else []),pcb)
 run('sch','export','svg','-o',str(pv)+'/',sch)
 for svg in pv.glob('*.svg'):
  svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n');pin(svg,'<title>SVG Image created')
 if sys.platform=='darwin':
  os.environ['DYLD_FALLBACK_LIBRARY_PATH']=':'.join(['/opt/homebrew/lib','/usr/local/lib',os.environ.get('DYLD_FALLBACK_LIBRARY_PATH','')])
 import cairosvg
 for name in ['board-top','board-bottom','assembly-top','orientation-silkscreen']:
  cairosvg.svg2png(url=str(pv/(name+'.svg')),write_to=str(pv/(name+'.png')),output_width=1800,
                  background_color='#18352b' if name=='orientation-silkscreen' else None)
 # The ray tracer is not repeatable: render again only when the board itself changed.
 renders={'assembled-3d-front':['--rotate','-55,0,-30','--perspective','--zoom','0.95','--floor'],'assembled-3d-top':[]}
 state=pv/'renders.json';current={'pcb_sha256':hashlib.sha256(pcb.read_bytes()).hexdigest()}
 if state.exists() and json.loads(state.read_text())==current and all((pv/(n+'.png')).exists() for n in renders):return
 for name,view in renders.items():
  run('pcb','render','--side','top','--quality','high','--background','opaque','-w','1800','-h','1200',*view,'-o',pv/(name+'.png'),pcb)
 state.write_text(json.dumps(current,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kicad-cli',default=shutil.which('kicad-cli'));ap.add_argument('--kicad-python',required=True)
 ap.add_argument('--no-previews',action='store_true',help='skip SVG/PNG/3D previews (CI: images stay as committed)');a=ap.parse_args()
 if not a.kicad_cli:ap.error('Supply --kicad-cli')
 def run(*args):subprocess.run([a.kicad_cli,*map(str,args)],check=True)
 pcb=H/'gemilaimate-shield.kicad_pcb';sch=H/'gemilaimate-shield.kicad_sch'
 run('sch','export','netlist','-o',H/'gemilaimate-shield.net',sch)
 net=H/'gemilaimate-shield.net'
 net.write_text(re.sub(r'\(source "[^"]*/(gemilaimate-shield\.kicad_sch)"\)',r'(source "\1")',net.read_text(),count=1))
 pin(net,'(date ')
 subprocess.run([sys.executable,str(H/'scripts/verify_netlist.py')],check=True)
 subprocess.run([a.kicad_python,str(H/'scripts/finish_shield.py')],check=True)
 sys.path.insert(0,str(R/'tools'))
 from check_shield import check_usb_access,check_mechanical_profiles,check_markings
 design=json.loads((H/'design.json').read_text())
 check_usb_access(design);check_mechanical_profiles(design);check_markings(pcb.read_text(),design)
 run('sch','erc','--severity-all','--format','json','-o',H/'erc.json',sch)
 run('pcb','drc','--schematic-parity','--severity-all','--format','json','-o',H/'drc.json',pcb)
 pin(H/'erc.json','"date"');pin(H/'drc.json','"date"')
 erc=json.loads((H/'erc.json').read_text());drc=json.loads((H/'drc.json').read_text())
 if any(s['violations'] for s in erc['sheets']) or any(drc[k] for k in ['violations','unconnected_items','schematic_parity']):
  raise SystemExit('Shield checks failed; fabrication export stopped')
 m=H/'manufacturing';g=m/'gerber';g.mkdir(parents=True,exist_ok=True)
 for old in g.iterdir():
  if old.is_file():old.unlink()
 run('pcb','export','pos','--format','csv','--units','mm','--smd-only','--exclude-fp-th','--side','front','-o',m/'positions-kicad.csv',pcb)
 subprocess.run([a.kicad_python,str(H/'scripts/export_manufacturing.py')],check=True)
 run('pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts','-o',str(g)+'/',pcb)
 run('pcb','export','drill','--format','excellon','--excellon-separate-th','--generate-report','--report-path',m/'drill-report.txt','-o',str(g)+'/',pcb)
 for f in g.iterdir():pin(f,'CreationDate','G04 Created by','DRILL file')
 pin(m/'drill-report.txt','Created on')
 stats=json.loads((H/'board-stats.json').read_text())
 for mask in ['F_Mask.gts','B_Mask.gbs']:
  mask_text=(g/('gemilaimate-shield-'+mask)).read_text()
  assert mask_text.count('D03*')>=stats['pth_pad_sites_including_alternative_row'], 'Gerber THT mask openings missing'
 if not a.no_previews:previews(run,pcb,sch)
 archive=m/ARCHIVE
 for old in m.glob('gemilaimate-shield-v*-prototype.zip'):
  if old!=archive:old.unlink()
 # Fixed entry dates and modes: the archive hash changes only with its content.
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(g.iterdir()):
   info=zipfile.ZipInfo(f.name,date_time=(*map(int,DATE.split('-')),0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
   z.writestr(info,f.read_bytes())
 (m/'manifest.json').write_text(json.dumps({'variant':f'shield-v{REVISION}-prototype','size_mm':[90,75],'pcb_sha256':hashlib.sha256(pcb.read_bytes()).hexdigest(),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'physical_assembly_verified':False,'module_clone_geometry_verified':False,'external_controls':'J5 four wires; J6 three wires; no direct power-module docking','nominal_markings_and_plug_clearance_checked':True,'external_power_module_placement_verified':False},indent=2)+'\n')
 print('PASS Shield electrical/CAM export. Geometry is nominal; no physical fit or hardware test claimed.')
if __name__=='__main__':main()
