#!/usr/bin/env python3
"""Fresh KiCad checks and a separate PROTOTYPE fabrication/assembly package."""
import argparse,csv,json,hashlib,subprocess,zipfile,shutil,tempfile,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield-compact';BASE='gemilaimate-compact'
LAYERS='F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');ap.add_argument('--no-previews',action='store_true');a=ap.parse_args()
 cli=shutil.which('kicad-cli');assert cli,'KiCad CLI required on the build host'
 def run(*args):subprocess.run([cli,*map(str,args)],check=True,stdout=subprocess.DEVNULL)
 pcb=H/(BASE+'.kicad_pcb');sch=H/(BASE+'.kicad_sch');m=H/'manufacturing';reports=H/'reports';m.mkdir(exist_ok=True);reports.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory() as t:
  t=Path(t)
  run('sch','erc','--severity-all','--format','json','-o',t/'erc.json',sch)
  run('pcb','drc','--severity-all','--schematic-parity','--format','json','-o',t/'drc.json',pcb)
  erc=json.loads((t/'erc.json').read_text());drc=json.loads((t/'drc.json').read_text())
  assert not any(s['violations'] for s in erc['sheets']), 'ERC not clean'
  assert all(not drc[k] for k in ['violations','unconnected_items','schematic_parity']), 'DRC, unconnected or parity not clean'
  g=t/'gerber';g.mkdir()
  run('pcb','export','gerbers','--layers',LAYERS,'-o',str(g)+'/',pcb)
  run('pcb','export','drill','--format','excellon','--excellon-separate-th','-o',str(g)+'/',pcb)
  if a.verify_only:
   from verify_cam import normalize
   old=m/'gerber';assert sorted(f.name for f in old.iterdir())==sorted(f.name for f in g.iterdir())
   for f in g.iterdir():assert normalize(f.read_text())==normalize((old/f.name).read_text()),f.name
   manifest=json.loads((m/'manifest.json').read_text());assert manifest['pcb_sha256']==hashlib.sha256(pcb.read_bytes()).hexdigest()
   with zipfile.ZipFile(m/'gemilaimate-compact-0.1.0-PROTOTYPE.zip') as z:
    assert sorted(z.namelist())==sorted(f.name for f in old.iterdir())
    assert all(z.read(f.name)==f.read_bytes() for f in old.iterdir())
   print('PASS compact: fresh all-severity ERC/DRC/parity and 4-layer CAM match');return
  for name in ['erc.json','drc.json']:shutil.copyfile(t/name,reports/name)
  dest=m/'gerber';dest.mkdir(exist_ok=True)
  for f in dest.iterdir():f.unlink()
  for f in g.iterdir():
   text=f.read_text()
   text='\n'.join(re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2}|Z)?','2026-11-03T00:00:00',line) if re.search(r'CreationDate|Created by|DRILL file',line) else line for line in text.splitlines())+'\n'
   (dest/f.name).write_text(text)
 d=json.loads((H/'design.json').read_text());parts=d['parts']
 def table(name,header,rows):
  with (m/name).open('w',newline='') as f:
   w=csv.writer(f,lineterminator="\n");w.writerow(header);w.writerows(rows)
 table('BOM.csv',['Reference','Function_alias','Description','MPN_example','Footprint','Side','DNP','Quantity_1_PCB','Quantity_5_PCB'],[[c['designator'],c['ref'],c['value'],c['mpn'],c['footprint'],c['side'],int(c['dnp']),int(not c['dnp']),5*int(not c['dnp'])] for c in parts if c['section']!='Testpoints'])
 smd=[c for c in parts if not c['dnp'] and c['physical_pads'] and (c['ref']=='U1' or all(p['smd'] for p in c['physical_pads']))]
 groups={}
 for c in smd:groups.setdefault((c['value'],c['mpn'],c['footprint']),[]).append(c['designator'])
 table('BOM-SMD.csv',['Designators','Quantity_1_PCB','Quantity_5_PCB','Value','MPN_example','Footprint'],[[' '.join(refs),len(refs),5*len(refs),*key] for key,refs in groups.items()])
 centres={c['designator']:[c['x'],c['y']] for c in smd}
 body=d['module_body'];centres['U1']=[(body[0]+body[2])/2,(body[1]+body[3])/2]
 table('CPL-SMD.csv',['Designator','Mid X_mm','Mid Y_mm','Layer','Rotation_deg','Comment'],[[c['designator'],*centres[c['designator']],c['side'],c['rotation'],c['value']] for c in smd])
 table('BOM-THT.csv',['Reference','Alias','Description','Side','Assembly_note'],[[c['designator'],c['ref'],c['value'],c['side'],'Verify exact mating part and pin 1 against assembly drawing'] for c in parts if not c['dnp'] and c['designator'] not in centres])
 table('BOM-EXTERNAL.csv',['Item','Quantity_per_assembled_controller','Note'],[
  ['ADS1115 Blue breakout, 1x10 2.54mm',1,'Nominal 28x17mm; measure actual clone. Can share between prototypes'],
  ['MAX31855 breakout, VIN/3Vo/GND/DO/CS/CLK',1,'Nominal 20.32x22.86mm; verify VIN regulator and thermocouple polarity'],
  ['ADS male header 1x10 2.54mm',1,'Module underside; standard plastic adds 2.54mm height'],
  ['MAX male header 1x6 2.54mm',1,'Module underside; verify pin order'],
  ['JP_TC 2.54mm jumper cap',1,'Select 5V or 3V3 once for the actual breakout; never bridge all three pins'],
  ['M2 nylon fasteners and insulating supports',3,'Head <=4mm; allow underside PH plugs and cable bends'],
  ['External system',1,'Reuse matched display, pressure sensor, thermocouple, RobotDyn, SSR, isolated 5V PSU and harnesses per project docs; these are not SMD assembly items'],
  ['Optional VL53L0X and low-power RGBW/light loads',0,'Optional; 3.3V I2C, no direct LED strips on RGBW connector']])
 headers=[c for c in parts if c['section']=='Connectors' and not c['dnp']]
 table('HARNESSES.csv',['PCB_reference','Function','Housing','Contacts','Pin_1_to_N','Quantity_1_system'],[[c['designator'],c['value'],'PHR-'+str(len(c['nets'])),str(sum(1 for n in c['nets'].values() if n))+' x SPH-002T-P0.5L','; '.join(c['names'][str(i)] for i in range(1,len(c['nets'])+1)),1] for c in headers])
 table('PINOUT.csv',['Reference','Alias','Pin','Function','Net','x_top_view_mm','y_top_view_mm'],[[c['designator'],c['ref'],p['number'],p['name'],p['net'] or 'NC',p['x'],p['y']] for c in parts for p in c['pins']])
 archive=m/'gemilaimate-compact-0.1.0-PROTOTYPE.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(dest.iterdir()):
   i=zipfile.ZipInfo(f.name,(2026,11,3,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16;z.writestr(i,f.read_bytes())
 layout=json.loads((reports/'layout.json').read_text())
 manifest=dict(variant='compact',revision='0.1.0',status='PROTOTYPE / INDEPENDENT REVIEW REQUIRED',hardware_tested=False,manufacturing_release=False,board_size_mm=[65,50],copper_layers=4,pcb_sha256=hashlib.sha256(pcb.read_bytes()).hexdigest(),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),kicad_version=subprocess.check_output([cli,'version'],text=True).strip(),smd_placements=len(smd),drc_violations=0,erc_violations=0,unconnected=0,schematic_parity=0,minimum_track_mm=layout['minimum_track_mm'],source_of_3d='KiCad models plus nominal daughterboard envelopes; actual clones unmeasured',fabrication_notes='Confirm 4-layer stack and USB 90 ohms; 0.15mm USB pad gaps; board not physically validated')
 (m/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (m/'README.md').write_text('''# Compact: производственный комплект прототипа\n\nНе отправлять в производство как проверенный серийный проект. Нужны независимая проверка схемы/BOM, реальные размеры модулей и согласование стека/USB с фабрикой. Аппаратных испытаний нет.\n\nGerber ZIP: четыре слоя, без платы-панели и без заказа монтажа. BOM: количества на 1/5 PCB; DNP не устанавливать. Жгуты HARNESSES рассчитаны на одну кофемашину, не на пять. SMD CPL содержит центры компонентов и вид сверху; у WROOM учтён сдвиг 0,75 мм от начала его посадочного места. Модуль включён в SMD несмотря на тепловые PTH-площадки; сторона и повороты требуют проверки в предпросмотре конкретного сборщика. Выбор MPN-примеров проверить у поставщика по полному артикулу; не подменять DCT/DCU/X2SON. Гнёзда модулей и JST PH паять со стороны, указанной в BOM-THT.\n\nВсе резисторы 0603, малые конденсаторы 0603, 10uF — 1206. Основной модуль WROOM требует надёжной пайки центральной земли. Нужен ручной контроль сборки; один паяльник не гарантирует пайку скрытого контакта.\n\nСхема, ограничения питания и испытания: ../../../docs/compact-shield.md.\n''')
 if not a.no_previews:
  pv=H/'previews';pv.mkdir(exist_ok=True)
  for name,layers,mirror in [('board-top','F.Cu,F.Mask,F.Silkscreen,Edge.Cuts',False),('board-bottom','B.Cu,B.Mask,B.Silkscreen,Edge.Cuts',True),('assembly-top','F.Fab,F.Silkscreen,Edge.Cuts',False),('assembly-bottom','B.Fab,B.Silkscreen,Edge.Cuts',True)]:
   run('pcb','export','svg','--layers',layers,'--mode-single','--page-size-mode','2','--exclude-drawing-sheet',*(['--mirror'] if mirror else []),'-o',pv/(name+'.svg'),pcb)
  run('sch','export','svg','-o',str(pv)+'/',sch)
  for svg in pv.glob('*.svg'):svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
  import cairosvg
  for name in ['board-top','board-bottom','assembly-top','assembly-bottom']:cairosvg.svg2png(url=str(pv/(name+'.svg')),write_to=str(pv/(name+'.png')),output_width=1600)
  for name,side,rot in [('assembled-front','top','-50,0,-25'),('assembled-back','bottom','-50,0,25')]:
   run('pcb','render','--side',side,'--quality','high','--background','opaque','--rotate',rot,'--perspective','-w','1600','-h','1000','-o',pv/(name+'.png'),pcb)
  subprocess.run([sys.executable,str(H/'scripts/make_template.py')],check=True)
 print('PASS compact prototype export; no physical assembly/flash or manufacturing release claimed')
if __name__=='__main__':main()
