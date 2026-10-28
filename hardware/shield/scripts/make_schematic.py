import json,uuid,csv
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]
d=json.loads((OUT/'design.json').read_text())
uid=lambda:str(uuid.uuid4())
q=lambda s:json.dumps(str(s),ensure_ascii=False)
rootid=uid()
libs=[];placed=[];wires=[];labels=[];nc=[]
net_counts={}
for c in d['parts']:
 for pin in c['pins']:
  if pin['net']:net_counts[pin['net']]=net_counts.get(pin['net'],0)+1


def effects(size=1,justify=None):
 return f'(effects (font (size {size} {size}))'+(f'(justify {justify})' if justify else '')+')'


for i,c in enumerate(d['parts']):
 ref=c['ref'];n=len(c['pins']);lid='GemilaiMate:'+ref
 if ref=='U1':sx,sy=48,55
 else:
  j=i-1;sx=140+100*(j%4);sy=35+35*(j//4)
 sx=round(sx/1.27)*1.27;sy=round(sy/1.27)*1.27
 dual=n>=14
 coords=[]
 for j,pin in enumerate(c['pins']):
  if n==2:
   xx=-7.62 if j==0 else 7.62;dy=0
  elif dual:
   half=n//2;xx=-12.7 if j<half else 12.7;dy=((j%half)-(half-1)/2)*2.54
  else:xx=-10.16;dy=(j-(n-1)/2)*2.54
  coords.append((xx,dy,pin))
 height=max(5.08,(n//2 if dual else n-1)*2.54+2.54)
 boxw=10.16 if dual else 7.62
 ps=[]
 for xx,dy,pin in coords:
  ang=0 if xx<0 else 180
  length=2.54 if n!=2 else 5.08
  typ='passive'
  number=int(pin['number']);name=pin['name']
  if ref=='U1':
   typ='bidirectional'
   if name=='GND':typ='power_in'
   elif number==1:typ='power_out'
   elif name in ['3V3','5V']:typ='passive'
   elif name=='EN':typ='input'
  elif ref=='U2':
   typ='power_in' if number in [7,14] else ('tri_state' if number in [3,6,8,11] else 'input')
  elif ref=='U3':typ='power_in' if number in [3,5] else ('output' if number==4 else 'input')
  elif ref=='J1':typ='power_out'
  elif ref.startswith('J') and not ref.startswith('JP'):
   if name.startswith('GND') or name in ['VCC3V3','VCC5V','VDD5V','VCCA','VCCB','USB5V']:typ='power_in'
   elif ref=='J3':typ='passive' if name=='VIN_SELECT' else ('output' if name=='DO' else 'input')
   elif ref=='J4' and name.startswith('OUT'):typ='output'
   elif ref=='J5':typ='output' if name.startswith('ZC') else 'input'
   elif ref in ['J7','J11']:typ='input' if name=='OE' else 'bidirectional'
   elif ref=='J10':typ='input'
  if ref.startswith('C'):length=6.35
  ps.append(f'(pin {typ} line (at {xx} {-dy} {ang}) (length {length}) (name {q(pin["name"])} {effects(.8)}) (number {q(pin["number"])} {effects(.8)}))')
 if n==2:
  height=2.54;boxw=2.54
 shape=f'(rectangle (start {-boxw} {height/2}) (end {boxw} {-height/2}) (stroke(width .254)(type default))(fill(type none)))'
 if ref.startswith('C'):
  shape=''.join(f'(polyline(pts(xy {x} -2.54)(xy {x} 2.54))(stroke(width .254)(type default))(fill(type none)))' for x in [-1.27,1.27])
 libs.append(f'''(symbol {q(lid)} (pin_names(offset .5)) (in_bom yes)(on_board yes)
  (property "Reference" {q(ref)} (at 0 {height/2+2.54} 0) {effects()})
  (property "Value" {q(c['value'])} (at 0 {-height/2-2.54} 0) {effects()})
  (property "Footprint" {q(c['footprint'])} (at 0 0 0) (effects(font(size 1.27 1.27))(hide yes)))
  (symbol {q(ref+'_0_1')} {shape})
  (symbol {q(ref+'_1_1')} {''.join(ps)}))''')
 symbolid=uid()
 placed.append(f'''(symbol(lib_id {q(lid)})(at {sx} {sy} 0)(unit 1)(in_bom yes)(on_board yes)(dnp no)(uuid {q(symbolid)})
  (property "Reference" {q(ref)}(at {sx} {sy-height/2-2.54} 0){effects()})
  (property "Value" {q(c['value'])}(at {sx} {sy+height/2+2.54} 0){effects(.9)})
  (property "Footprint" {q(c['footprint'])}(at {sx} {sy} 0)(effects(font(size 1.27 1.27))(hide yes)))
  (instances(project "gemilaimate-shield"(path {q('/'+rootid)}(reference {q(ref)})(unit 1)))))''')
 for xx,dy,pin in coords:
  px,py=sx+xx,sy+dy
  if not pin['net']:
   nc.append(f'(no_connect(at {px} {py})(uuid {q(uid())}))')
  else:
   lx=px+(-7.62 if xx<0 else 7.62)
   wires.append(f'(wire(pts(xy {px} {py})(xy {lx} {py}))(stroke(width 0)(type default))(uuid {q(uid())}))')
   labels.append(f'(label {q(pin["net"])}(at {lx} {py} 0){effects(.9,"right bottom" if xx<0 else "left bottom")}(uuid {q(uid())}))')

doc=f'''(kicad_sch(version 20250114)(generator "eeschema")(uuid {q(rootid)})(paper "A2")
 (title_block(title "GemilaiMate - LOW VOLTAGE carrier / Rico-X")(date "2026-10-28")(rev "0.2.2 SHIELD - PROTOTYPE")
 (comment 1 "Breakouts in dedicated sockets; J5/J6 wired controls to separate power modules. No mains on board.")
 (comment 2 "Module pin geometry and machine volume remain UNMEASURED. NOT RELEASED FOR FABRICATION.")
 (comment 3 "JP1 open for USB; R13 = removable 0R valve buffer link.")
 (comment 4 "ERC checks interface connectivity only, not internals of purchased modules."))
 (lib_symbols{''.join(libs)})
 {''.join(wires)}{''.join(labels)}{''.join(nc)}{''.join(placed)}
 (sheet_instances(path "/"(page "1"))))
'''
(OUT/'gemilaimate-shield.kicad_sch').write_text(doc)
# Project design rules remain in the supplied .kicad_pro
(OUT/'sym-lib-table').write_text('(sym_lib_table\n  (version 7)\n  (lib (name "GemilaiMate") (type "KiCad") (uri "${KIPRJMOD}/GemilaiMate.kicad_sym") (options "") (descr "Carrier interface symbols"))\n)\n')
external=''.join(libs)
for c in d['parts']:external=external.replace('"GemilaiMate:'+c['ref']+'"','"'+c['ref']+'"')
(OUT/'GemilaiMate.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+external+')\n')
with (OUT/'connections.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['Reference','Value','Pin','Pin name','Net','x_mm','y_mm'])
 for c in d['parts']:
  for pin in c['pins']:w.writerow([c['ref'],c['value'],pin['number'],pin['name'],pin['net'] or 'NC',pin['x'],pin['y']])
print('SCHEMATIC',len(placed),'parts')
