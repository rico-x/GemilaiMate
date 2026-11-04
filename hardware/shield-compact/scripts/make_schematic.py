#!/usr/bin/env python3
"""Create readable functional KiCad sheets with real pin electrical types."""
from pathlib import Path
import json
import uuid

H=Path(__file__).resolve().parents[1]
D=json.loads((H/'design.json').read_text())
NS=uuid.uuid5(uuid.NAMESPACE_URL,'https://github.com/Rico-X/GemilaiMate/hardware/shield-compact')
uid=lambda name:str(uuid.uuid5(NS,name))
q=lambda val:json.dumps(str(val),ensure_ascii=False)
root=uid('root')


def effects(size=1,justify=''):
    return f'(effects(font(size {size} {size}))'+(f'(justify {justify})' if justify else '')+')'


def group(c):
    r=c['ref']
    if r in ['J_EXT','J_SCALE','J_FREE'] or r.startswith('TP'):return 'expansion'
    if r.startswith(('R_BREW','R_STEAM','C_BREW','C_STEAM')) or r=='J_BUTTONS':return 'buttons'
    if r in ['U1','R_EN','C_EN','R_BOOT','SW_RESET','SW_BOOT','R_ID_TOP','R_ID_LOW','C_ID','C_MCU','C_MCUHF']:return 'mcu'
    if r in ['J_USB','U_ESD','F_USB','F_EXT','D_USB','D_EXT','D_TVS','U_REG','C_IN','C_OUT','C_EXT','J_PWR','J_DISPLAY'] or r.startswith(('R_CC','R_USB')):return 'power-usb'
    if r in ['J_LEVEL','C_LVA','C_LVB','R_OE','C_OE','J_ADS','R_PRESS','C_PRESS','J_PRESS']:return 'pressure'
    if r in ['J_TC','R_TC3V3','R_TC5V']:return 'temperature'
    if c['section']=='Alba' or r in ['J_TOF','J_ALBA','J_RGBW','J_LIGHT','R_EXTSDA','R_EXTSCL']:return 'alba'
    return 'outputs'


groups={k:[] for k in ['power-usb','mcu','pressure','temperature','outputs','buttons','alba','expansion']}
for c in D['parts']:groups[group(c)].append(c)
# Flags are deliberate declarations of external/passive-chain power delivery.
for i,net in enumerate(D['power_flags'],1):
    groups['power-usb'].append(dict(ref='#FLG'+str(i),value='PWR_FLAG',footprint='',dnp=False,
                                  pins=[dict(number='1',name='pwr',net=net,type='power_out')]))
root_sheets=[];symbol_paths={};library=[]
titles={'power-usb':'USB-C and protected core power','mcu':'ESP32-S3 and ID=4 / Boot',
        'pressure':'ADS1115 and 3V3/5V I2C','temperature':'MAX31855 socket',
        'outputs':'ZC and buffered external outputs','buttons':'Active-low dry contacts',
        'alba':'PCA9634 and tank / lighting','expansion':'Reserved interfaces and free GPIO'}

for page,(name,parts) in enumerate(groups.items(),2):
    sid=uid('sheet:'+name);docid=uid('file:'+name);libs=[];symbols=[];wires=[];labels=[];ncs=[]
    for i,c in enumerate(parts):
        ref=c['ref'];des=c.get('designator',ref);pins=c['pins'];count=len(pins);half=(count+1)//2
        sx,sy=round((65+(i%4)*140)/1.27)*1.27,round((55+(i//4)*65)/1.27)*1.27
        dual=count>8;coords=[];height=max(5.08,((half if dual else count)-1)*2.54+5.08)
        for j,pin in enumerate(pins):
            left=not dual or j<half
            x=-15.24 if left else 15.24
            y=((j if left else j-half)-((half if dual else count)-1)/2)*2.54
            if count==2:x=-7.62 if j==0 else 7.62;y=0
            coords.append((x,y,pin))
        libid='GemilaiMateCompact:'+ref.replace('#','')
        libname=libid.split(':')[1];graphic=''
        if count==2:
            graphic='(rectangle(start -2.54 -1.27)(end 2.54 1.27)(stroke(width .254)(type default))(fill(type none)))'
        else:
            graphic=f'(rectangle(start -12.7 {-height/2})(end 12.7 {height/2})(stroke(width .254)(type default))(fill(type none)))'
        ps=[]
        for x,y,pin in coords:
            length=5.08 if count==2 else 2.54
            ps.append(f'(pin {pin["type"]} line(at {x} {-y} {0 if x<0 else 180})(length {length})'
                      f'(name {q(pin["name"])}{effects(.8)})(number {q(pin["number"])}{effects(.8)}))')
        lib=f'''(symbol {q(libid)}(pin_names(offset .5))(in_bom {'no' if ref.startswith(('#','TP')) else 'yes'})(on_board {'no' if ref.startswith('#') else 'yes'})
          (property "Reference" {q(des)}(at 0 {height/2+2.54} 0){effects()})
          (property "Value" {q(c['value'])}(at 0 {-height/2-2.54} 0){effects()})
          (property "Footprint" {q(c['footprint'])}(at 0 0 0)(effects(font(size 1 1))(hide yes)))
          (symbol {q(libname+'_0_1')}{graphic})(symbol {q(libname+'_1_1')}{''.join(ps)}))'''
        libs.append(lib);library.append(lib.replace(q(libid),q(libname),1))
        symid=uid('symbol:'+ref);path='/'+root+'/'+sid
        symbol_paths[ref]=path+'/'+symid
        symbols.append(f'''(symbol(lib_id {q(libid)})(at {sx} {sy} 0)(unit 1)
          (in_bom {'no' if ref.startswith(('#','TP')) else 'yes'})(on_board {'no' if ref.startswith('#') else 'yes'})(dnp {'yes' if c['dnp'] else 'no'})(uuid {q(symid)})
          (property "Reference" {q(des)}(at {sx} {sy-height/2-2.54} 0){effects()})
          (property "Value" {q(c['value'])}(at {sx} {sy+height/2+2.54} 0){effects(.9)})
          (property "Footprint" {q(c['footprint'])}(at {sx} {sy} 0)(effects(font(size 1 1))(hide yes)))
          (instances(project "gemilaimate-compact"(path {q(path)}(reference {q(des)})(unit 1)))))''')
        for x,y,pin in coords:
            px,py=sx+x,sy+y;key=ref+'.'+pin['number']
            if pin['net'] is None:
                ncs.append(f'(no_connect(at {px} {py})(uuid {q(uid("nc:"+key))}))')
            else:
                lx=px+(-5.08 if x<0 else 5.08)
                wires.append(f'(wire(pts(xy {px} {py})(xy {lx} {py}))(stroke(width 0)(type default))(uuid {q(uid("wire:"+key))}))')
                labels.append(f'(global_label {q(pin["net"])}(shape bidirectional)(at {lx} {py} {0 if x<0 else 180})'
                              f'{effects(.85,"right" if x<0 else "left")}(uuid {q(uid("label:"+key))}))')
    text=f'''(kicad_sch(version 20250114)(generator "eeschema")(uuid {q(docid)})(paper "A2")
      (title_block(title {q(titles[name])})(date {q(D['date'])})(rev {q(D['revision'])})
      (comment 1 "GemilaiMate Compact Shield / Rico-X / github.com/Rico-X/GemilaiMate")
      (comment 2 "PROTOTYPE - NOT HARDWARE VALIDATED / NO MAINS"))
      (lib_symbols{''.join(libs)}){''.join(wires)}{''.join(labels)}{''.join(ncs)}{''.join(symbols)}
      (sheet_instances(path {q('/'+root+'/'+sid)}(page {q(page)}))))'''
    (H/(name+'.kicad_sch')).write_text(text)
    x,y=25+(page-2)%2*130,30+(page-2)//2*48
    root_sheets.append(f'''(sheet(at {x} {y})(size 110 30)(stroke(width .1524)(type default))(fill(color 0 0 0 0))(uuid {q(sid)})
      (property "Sheetname" {q(titles[name])}(at {x} {y-1} 0){effects(1.1,'left bottom')})
      (property "Sheetfile" {q(name+'.kicad_sch')}(at {x} {y+31} 0){effects(1,'left top')})
      (instances(project "gemilaimate-compact"(path {q('/'+root)}(page {q(page)})))))''')

rootdoc=f'''(kicad_sch(version 20250114)(generator "eeschema")(uuid {q(root)})(paper "A3")
  (title_block(title "GemilaiMate Compact Shield - Rico-X")(date {q(D['date'])})(rev {q(D['revision'])})
  (comment 1 "ESP32-S3-WROOM-1-N16R8 / {D['size_mm'][0]}x{D['size_mm'][1]}mm / 2 layers / native USB")
  (comment 2 "GM Pro PCB Rev 1.1 ID=4; official binary compatibility requires physical testing")
  (comment 3 "No mains on PCB. Heater output unused in stock Gemilai integration.")
  (comment 4 "github.com/Rico-X/GemilaiMate - PROTOTYPE - NOT HARDWARE VALIDATED"))
  (lib_symbols){''.join(root_sheets)}(sheet_instances(path "/"(page "1"))))'''
(H/'gemilaimate-compact.kicad_sch').write_text(rootdoc)
(H/'GemilaiMateCompact.kicad_sym').write_text('(kicad_symbol_lib(version 20241209)(generator "kicad_symbol_editor")'+''.join(library)+')\n')
(H/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "GemilaiMateCompact")(type "KiCad")(uri "${KIPRJMOD}/GemilaiMateCompact.kicad_sym")(options "")(descr "Compact circuit symbols")))\n')
(H/'schematic-paths.json').write_text(json.dumps(symbol_paths,indent=2)+'\n')
print('Generated',len(groups)+1,'functional schematic sheets with',len(D['parts']),'real components')
