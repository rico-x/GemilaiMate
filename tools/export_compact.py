#!/usr/bin/env python3
"""Fresh KiCad checks and a separate PROTOTYPE fabrication/assembly package."""
import argparse,csv,json,hashlib,subprocess,zipfile,shutil,tempfile,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield-compact';BASE='gemilaimate-compact'
LAYERS='F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');ap.add_argument('--no-previews',action='store_true');a=ap.parse_args()
 revision_date=json.loads((H/'revision.json').read_text())['date']
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
   revision=json.loads((H/'revision.json').read_text())['revision']
   with zipfile.ZipFile(m/f'gemilaimate-compact-{revision}-PROTOTYPE.zip') as z:
    assert sorted(z.namelist())==sorted(f.name for f in old.iterdir())
    assert all(z.read(f.name)==f.read_bytes() for f in old.iterdir())
   print('PASS compact shield: fresh all-severity ERC/DRC/parity and CAM match');return
  for name in ['erc.json','drc.json']:shutil.copyfile(t/name,reports/name)
  dest=m/'gerber';dest.mkdir(exist_ok=True)
  for f in dest.iterdir():f.unlink()
  for f in g.iterdir():
   text=f.read_text()
   text='\n'.join(re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2}|Z)?',revision_date+'T00:00:00',line) if re.search(r'CreationDate|Created by|DRILL file',line) else line for line in text.splitlines())+'\n'
   (dest/f.name).write_text(text)
 d=json.loads((H/'design.json').read_text());parts=d['parts']
 def table(name,header,rows):
  with (m/name).open('w',newline='') as f:
   w=csv.writer(f,lineterminator="\n");w.writerow(header);w.writerows(rows)
 table('BOM.csv',['Reference','Function_alias','Description','MPN_example','Footprint','Side','DNP','Quantity_1_PCB','Quantity_5_PCB'],[[c['designator'],c['ref'],c['value'],c['mpn'],c['footprint'],c['side'],int(c['dnp']),int(not c['dnp']),5*int(not c['dnp'])] for c in parts if c['section']!='Testpoints'])
 smd=[c for c in parts if not c['dnp'] and c['physical_pads'] and (c['ref'] in ['U1','J_USB'] or all(p['smd'] for p in c['physical_pads']))]
 groups={}
 for c in smd:groups.setdefault((c['value'],c['mpn'],c['footprint']),[]).append(c['designator'])
 table('BOM-SMD.csv',['Designators','Quantity_1_PCB','Quantity_5_PCB','Value','MPN_example','Footprint'],[[' '.join(refs),len(refs),5*len(refs),*key] for key,refs in groups.items()])
 centres={c['designator']:[c['x'],c['y']] for c in smd}
 body=d['module_body'];centres['U1']=[(body[0]+body[2])/2,(body[1]+body[3])/2]
 table('CPL-SMD.csv',['Designator','Mid X_mm','Mid Y_mm','Layer','Rotation_deg','Comment'],[[c['designator'],*centres[c['designator']],c['side'],c['rotation'],c['value']] for c in smd])
 table('BOM-THT.csv',['Reference','Alias','Description','MPN_example','Side','Assembly_note'],[[c['designator'],c['ref'],c['value'],c['mpn'],c['side'],'Verify exact mating part and pin 1 against assembly drawing'] for c in parts if not c['dnp'] and c['designator'] not in centres])
 table('BOM-EXTERNAL.csv',['Item','Quantity_per_assembled_controller','MPN_example','Dimensions_mm','Note'],[
  ['ADS1115 Blue breakout, 1x10 2.54mm',1,'Unspecified clone','28 x 17 x varies','Nominal seller outline only; measure actual board, components and pins. Can share between prototypes'],
  ['MAX31855 breakout, VIN/3Vo/GND/DO/CS/CLK',1,'Unspecified clone','20.32 x 22.86 x varies','Adafruit reference outline only; measure actual clone and thermocouple terminal'],
  ['CJMCU-0102 TXS0102 breakout, 2x1x5 2.54mm',1,'Selected marketplace module','15.24 x 15.24 x varies; row gap 12.70 assumed','Measure actual module and row spacing; row A is 3V3, row B is 5V'],
  ['ADS male header 1x10 2.54mm',1,'Harwin M20-9991046','25.40 x 2.54 x 11.64','Fit on breakout underside; 0.64 mm square pins, 6.1 mm mating length'],
  ['MAX male header 1x6 2.54mm',1,'Harwin M20-9990646','15.24 x 2.54 x 11.64','Fit on breakout underside; verify pin order'],
  ['CJMCU male headers 2 x 1x5 2.54mm',2,'Harwin M20-9990546','12.70 x 2.54 x 11.64 each; 12.70 mm row gap','Solder to module underside after measuring the actual row gap'],
  ['M2 nylon fasteners and insulating supports',4,'Generic','Head <=4 mm','Use the documented mounting holes; check connector and cable clearance'],
  ['External system',1,'Per docs/components.md','Varies','Reuse matched display, pressure sensor, thermocouple, RobotDyn, SSR and isolated 5V PSU; power modules remain separate'],
  ['Optional VL53L0X and low-power RGBW/light loads',0,'Per docs/components.md','Varies','Optional; 3.3V I2C, no direct LED strips on RGBW connector']])
 headers=[c for c in parts if c['section']=='Connectors' and not c['dnp']]
 xh=lambda c:'JST_XH' in c['source_footprint']
 table('HARNESSES.csv',['PCB_reference','Function','Housing','Contacts','Pin_1_to_N','Quantity_1_system'],[[c['designator'],c['value'],('XHP-' if xh(c) else 'PHR-')+str(len(c['nets'])),str(sum(1 for n in c['nets'].values() if n))+(' x SXH-001T-P0.6' if xh(c) else ' x SPH-002T-P0.5L'),'; '.join(c['names'][str(i)] for i in range(1,len(c['nets'])+1)),1] for c in headers])
 table('PINOUT.csv',['Reference','Alias','Pin','Function','Net','x_top_view_mm','y_top_view_mm'],[[c['designator'],c['ref'],p['number'],p['name'],p['net'] or 'NC',p['x'],p['y']] for c in parts for p in c['pins']])
 revision=json.loads((H/'revision.json').read_text())['revision']
 archive=m/f'gemilaimate-compact-{revision}-PROTOTYPE.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(dest.iterdir()):
   i=zipfile.ZipInfo(f.name,(*map(int,revision_date.split('-')),0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o644<<16;z.writestr(i,f.read_bytes())
 layout=json.loads((reports/'layout.json').read_text())
 manifest=dict(variant='compact-shield',revision=revision,status='PROTOTYPE / INDEPENDENT REVIEW REQUIRED',hardware_tested=False,manufacturing_release=False,board_size_mm=d['size_mm'],copper_layers=d['copper_layers'],pcb_sha256=hashlib.sha256(pcb.read_bytes()).hexdigest(),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),kicad_version=subprocess.check_output([cli,'version'],text=True).strip(),smd_placements=len(smd),drc_violations=0,erc_violations=0,unconnected=0,schematic_parity=0,minimum_track_mm=layout['minimum_track_mm'],minimum_copper_clearance_mm=.2,default_signal_clearance_mm=.25,power_usb_clearance_mm=.3,minimum_power_track_mm=.3,via_diameter_drill_mm=[.8,.4],hole_to_copper_mm=.5,usb_hole_to_copper_mm=.4,thickness_mm=1.6,copper_oz=1,source_of_3d='Manufacturer dimensions for components/connectors; HRO USB and breakout 3D envelopes are nominal; marketplace clones remain unmeasured',fabrication_notes='2-layer hand-assembly prototype; clearance >=0.20mm, no 0.15mm fabrication exception. Independently review outer GND continuity, USB, RF and module fit.')
 (m/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (m/'README.md').write_text(f'''# GemilaiMate Compact Shield {revision}: комплект прототипа\n\nНе отправлять в производство как проверенный серийный проект. Нужны независимая проверка схемы/BOM, реальные размеры модулей и согласование стека/USB с фабрикой. Аппаратных испытаний нет.\n\nGerber ZIP: два медных слоя, без платы-панели и без заказа монтажа. На обеих сторонах заливка GND; внутренних слоёв нет. BOM: количества на 1/5 PCB; DNP не устанавливать. HARNESSES рассчитан на одну кофемашину, не на пять. SMD CPL содержит центры компонентов и вид сверху; у WROOM учтён сдвиг от начала посадочного места. Модуль включён в SMD несмотря на тепловые PTH-площадки; проверить предпросмотр сборщика. ADS1115, MAX31855 и CJMCU вставляются в отдельные гнёзда; реальные платы и межрядье CJMCU пока не измерены. Гнёзда модулей и JST паять со стороны, указанной в BOM-THT.\n\nПод ручной монтаж: резисторы и малые конденсаторы 0805, 10 мкФ и предохранители 1206 — все с удлинёнными площадками HandSolder; SOT-23/SMA тоже HandSolder; микросхемы SOIC с шагом 1,27 мм. У полярных деталей на шелкографии точка первого вывода или черта катода. SMD паять до установки модулей: часть деталей стоит под ними. Основной модуль WROOM требует надёжной пайки центральной земли. Нужен ручной контроль сборки; один паяльник не гарантирует пайку скрытого контакта.\n\nСхема, ограничения питания и испытания: ../../../docs/compact-shield.md.\n''')
 if not a.no_previews:
  pv=H/'previews';pv.mkdir(exist_ok=True)
  for name,layers,mirror in [('board-top','F.Cu,F.Mask,F.Silkscreen,Edge.Cuts',False),('board-bottom','B.Cu,B.Mask,B.Silkscreen,Edge.Cuts',True),('assembly-top','F.Fab,F.Silkscreen,Edge.Cuts',False),('assembly-bottom','B.Fab,B.Silkscreen,Edge.Cuts',True)]:
   run('pcb','export','svg','--layers',layers,'--mode-single','--page-size-mode','2','--exclude-drawing-sheet',*(['--mirror'] if mirror else []),'-o',pv/(name+'.svg'),pcb)
  run('sch','export','svg','-o',str(pv)+'/',sch)
  for svg in pv.glob('*.svg'):svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
  import cairosvg
  for name in ['board-top','board-bottom','assembly-top','assembly-bottom']:cairosvg.svg2png(url=str(pv/(name+'.svg')),write_to=str(pv/(name+'.png')),output_width=1600)
  subprocess.run([sys.executable,str(H/'scripts/render_assembly.py')],check=True)
  subprocess.run([sys.executable,str(H/'scripts/make_template.py')],check=True)
 subprocess.run([sys.executable,str(H/'scripts/component_dimensions.py')],check=True)
 print('PASS compact shield prototype export; no physical assembly/flash or manufacturing release claimed')
if __name__=='__main__':main()
