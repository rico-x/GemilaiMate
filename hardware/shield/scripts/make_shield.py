"""Convert the baseline v0.1 PCB to the socket shield (revision in revision.json).

Read the active sibling carrier v0.1 with KiCad's pcbnew Python. Module geometry
is an explicit prototype profile, not a claim about a received clone.
"""
from pathlib import Path
import json, csv
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('make_shield')
from revision import REVISION,DATE

H=Path(__file__).resolve().parents[1]
BASE=H.parent/'carrier'
B=p.LoadBoard(str(BASE/'gemilaimate-carrier.kicad_pcb'))
D=json.loads((BASE/'design.json').read_text())
tb=B.GetTitleBlock();tb.SetRevision(REVISION);tb.SetTitle('GemilaiMate Shield - Rico-X');tb.SetDate(DATE);B.SetTitleBlock(tb)
for net in B.GetNetsByNetcode().values():
    if net.GetNetname().startswith('/'):
        net.SetNetname(net.GetNetname()[1:])
NETS_BY_NAME={n.GetNetname():n for n in B.GetNetsByNetcode().values()}
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
W,HEIGHT=90,75
for t in list(B.GetTracks()): B.Delete(t)
for z in list(B.Zones()):
    if not z.GetIsRuleArea(): B.Delete(z)
parts={c['ref']:c for c in D['parts']}
fps={f.GetReference():f for f in B.GetFootprints() if f.GetReference() in parts}

def move(ref,dx,dy):
    fp=fps[ref]; fp.Move(V(dx,dy))
    c=parts[ref]; c['x']+=dx;c['y']+=dy
    c['rect']=[v+(dx if i%2==0 else dy) for i,v in enumerate(c['rect'])]
    for pin in c['pins']:
        pin['x']+=dx;pin['y']+=dy
    if 'physical_pads' in c:
        # The serialized list is independent of pins after JSON loading.
        for pin in c['physical_pads']:
            pin['x']+=dx;pin['y']+=dy

move('U1',1.27,0)
D['rf_keepout']=[v+(1.27 if i%2==0 else 0) for i,v in enumerate(D['rf_keepout'])]
for z in B.Zones():
    if z.GetIsRuleArea(): z.Move(V(1.27,0))
move('J4',8.89-parts['J4']['x'],69.85-parts['J4']['y'])
move('J8',27.94-parts['J8']['x'],69.85-parts['J8']['y'])
move('R12',17.78-parts['R12']['x'],69.85-parts['R12']['y'])
move('C6',22.86-parts['C6']['x'],69.85-parts['C6']['y'])

fps['J8'].Reference().SetPosition(V(31.75,67))
for ref,x,y in [('C3',78.5,10),('C5',68.58,41.0),('C6',22.86,66.7),('R13',69.75,33.91),('U3',79.5,1.3)]:
    fps[ref].Reference().SetPosition(V(x,y))

def shape(fp,a,b,layer,width=.1):
    t=p.PCB_SHAPE(fp);t.SetShape(p.SHAPE_T_SEGMENT)
    t.SetStart(V(*a));t.SetEnd(V(*b));t.SetLayer(layer);t.SetWidth(p.FromMM(width));fp.Add(t)

def rectangle(fp,rect,layer,margin=0):
    a,b,c,d=rect;a-=margin;b-=margin;c+=margin;d+=margin
    for e,f in [((a,b),(c,b)),((c,b),(c,d)),((c,d),(a,d)),((a,d),(a,b))]:shape(fp,e,f,layer,.05 if layer==p.F_CrtYd else .1)

profiles=[]
socket_labels={
 'J2':[('1',5.08,61.0),('VDD ... A3',16.51,59.6)],
 'J3':[('1',77.5,46.1),('CLK ... VIN',68.58,72.0)],
 'J5':[('1',41.91,73.3)],
 'J6':[('1',88.5,48.1),('DC+',80.5,49.53),('DC-',80.5,55.88),('CH1',80.5,60.96)],
 'J7':[('1',36.83,61.0),('A 3V3',42,61.0),('B 5V',42,53.3)],
}
def socket(ref,value,pins,body,socket_boxes,meta):
    old=fps[ref];B.Remove(old)
    fp=p.FOOTPRINT(B);fp.SetReference(ref);fp.SetValue(value)
    name=ref+'_socket_shield';fp.SetFPID(p.LIB_ID('GemilaiMate',name))
    fp.SetPosition(V(pins[0][1],pins[0][2]));B.Add(fp)
    fp.Reference().SetPosition(V(body[0]+(body[2]-body[0])/2,body[1]-1.4))
    if ref=='J5':fp.Reference().SetPosition(V(52.4,71.12))
    fp.Reference().SetTextSize(V(.8,.8));fp.Reference().SetTextThickness(p.FromMM(.12))
    fp.Value().SetVisible(False)
    for number,x,y,net,label in pins:
        pad=p.PAD(fp);pad.SetNumber(str(number));pad.SetPosition(V(x,y))
        pad.SetAttribute(p.PAD_ATTRIB_PTH);pad.SetShape(p.PAD_SHAPE_RECT if number==1 else p.PAD_SHAPE_CIRCLE)
        pad.SetSize(V(1.7,1.7));pad.SetDrillSize(V(1,1))
        # Do not mutate LSET.AllCuMask(): it is a cached native singleton.
        pad.SetLayerSet(p.PAD.PTHMask())
        if net: pad.SetNet(NETS_BY_NAME[net])
        fp.Add(pad)
    rectangle(fp,body,p.F_Fab)
    # Full nominal module outline, or the cable connector body for J5/J6.
    rectangle(fp,body,p.F_SilkS)
    if ref=='J6':shape(fp,(82.4,49.53),(84.3,50.8),p.F_SilkS,.1)
    for label,x,y in socket_labels[ref]:
        t=p.PCB_TEXT(fp);t.SetText(label);t.SetPosition(V(x,y));t.SetLayer(p.F_SilkS)
        t.SetTextSize(V(.8,.8));t.SetTextThickness(p.FromMM(.12));fp.Add(t)
    meta.update(silk_labels=[label for label,x,y in socket_labels[ref]],pin1_shape='rect',body_outline_layer='F.SilkS')
    # Daughterboard body is above 8.5 mm sockets; these module courtyards
    # are kept clear of other tall parts in the placement script.
    for box in socket_boxes:
        rectangle(fp,box,p.F_CrtYd,.25)
        rectangle(fp,box,p.F_SilkS)
    rec=dict(ref=ref,value=value,x=pins[0][1],y=pins[0][2],
        pins=[dict(number=str(n),x=x,y=y,net=nn,name=pn) for n,x,y,nn,pn in pins],
        rect=body,kind='cable_connector' if ref in ['J5','J6'] else 'module_socket',footprint='GemilaiMate:'+name,
        module_profile=meta)
    parts[ref].clear();parts[ref].update(rec);fps[ref]=fp
    profiles.append(dict(reference=ref,**meta,body_rect_mm=body if ref not in ['J5','J6'] else None,connector_rect_mm=body,
        pin_centres_mm=[dict(number=str(n),x=x,y=y,name=pn) for n,x,y,nn,pn in pins]))

pitch=2.54
ads_labels=['VDD','GND','SCL','SDA','ADDR','ALRT','A0','A1','A2','A3']
ads_nets=['+5V','GND','SCL_5V','SDA_5V','GND',None,'PRESSURE',None,None,None]
socket('J2','ADS1115 BLUE SOCKET 1x10',
    [(i+1,5.08+i*pitch,63.5,ads_nets[i],ads_labels[i]) for i in range(10)],
    [2.54,48.26,30.48,65.3],[[3.81,62.23,29.21,64.77]],
    dict(model='ADS1115 Blue 28x17',geometry_status='seller outline; 2.54 pitch assumed; received board not measured',
         url='https://aliexpress.ru/item/1005009774074735.html?sku_id=12000050121529945',
         source_notes='Selected Blue photo: one row of ten, VDD GND SCL SDA ADDR ALRT A0 A1 A2 A3; seller states 17x28 mm',
         outline_mm=[28,17],socket_height_mm=8.5))

# Numbers are connector numbers, not TXS IC numbers. Extra pad G is left
# electrically NC until continuity of that particular CJMCU revision is known.
txs=[]
for row,y,names,nets in [(0,63.5,['GND_A','OE','VCCA','A1','A2'],['GND','+3V3','+3V3','SCL_3V3','SDA_3V3']),
                        (1,50.8,['GND_B','G_RESERVED_NC','VCCB','B1','B2'],['GND',None,'+5V','SCL_5V','SDA_5V'])]:
    txs.extend((row*5+i+1,36.83+i*pitch,y,nets[i],names[i]) for i in range(5))
socket('J7','CJMCU-0102 SOCKET 2x1x5',txs,[34.29,49.53,49.53,64.77],
       [[35.56,62.23,48.26,64.77],[35.56,49.53,48.26,52.07]],
       dict(model='CJMCU-0102 TXS0102',geometry_status='pin labels from selected seller photo; row distance 12.70 mm is an unmeasured assumption',
            url='https://aliexpress.ru/item/32898604164.html?sku_id=65803725915',
            source_notes='Two rows of five. GND/OE/VA/A1/A2 opposite GND/G/VB/B1/B2. G pad deliberately NC on carrier.',
            outline_mm=[15.24,15.24],row_spacing_mm=12.7,socket_height_mm=8.5))

max_names=['VIN','3VO_NC','GND','DO','CS','CLK']
max_nets=['TC_VIN',None,'GND','TC_DO','TC_CS','TC_SCK']
socket('J3','MAX31855 VIN SOCKET 1x6',
       [(i+1,74.93-i*pitch,49.53,max_nets[i],max_names[i]) for i in range(6)],
       [58.42,47.50,78.74,70.36],[[60.96,48.26,76.2,50.8]],
       dict(model='MAX31855 6-pin regulated breakout',geometry_status='selected seller photo pinout; Adafruit v2 reference envelope, clone dimensions unmeasured',
            url='https://aliexpress.ru/item/33050360870.html?sku_id=67508712590',
            source_notes='VIN 3Vo GND DO CS CLK. 3Vo is an output and is NOT tied to carrier 3V3. Adafruit v2 is a reference, not proof of clone fit.',
            outline_mm=[20.32,22.86],socket_height_mm=8.5))

socket('J5','ROBOTDYN CABLE 1x4',
       [(i+1,41.91+i*pitch,71.12,nn,pn) for i,(nn,pn) in enumerate([('+5V','VCC5V'),('GND','GND'),('ZC_RAW','ZC5V'),('PUMP_PWM','PSM3V3')])],
       [40.64,69.85,50.8,72.39],[[40.64,69.85,50.8,72.39]],
       dict(model='RobotDyn 16A Standard external module',geometry_status='seller PCB outline only; header, heatsink, terminals and height unmeasured; no direct docking',
            url='https://aliexpress.ru/item/1005001965951718.html?sku_id=12000044296027587',
            source_notes='Seller image states 60x42 mm PCB only. Connect by four control wires to a separately retained module. Pin 1 LEFT on shield; no direct dock or header rework specified. No mains routing on shield.',
            outline_mm=[60,42],height_mm=None,assembly_reservation_mm=[80,65,65],reservation_is_measured=False,
            placement_on_shield=None,mounting_mode='external_wired',socket_height_mm=8.5,requires_mechanical_fit_check=True))

ssr=[('+5V','DC_PLUS'),(None,'SPACER_NC'),('GND','DC_MINUS'),(None,'SPACER_NC'),('VALVE_IN','CH1')]
socket('J6','SSR CABLE 1x5 USE 1-3-5',
       [(i+1,86.36,50.8+i*pitch,nn,pn) for i,(nn,pn) in enumerate(ssr)],
       [85.09,49.53,87.63,62.23],[[85.09,49.53,87.63,62.23]],
       dict(model='TZT 5V1wayHigh external SSR',geometry_status='module outline, terminal and height unmeasured; no direct docking',
            url='https://aliexpress.ru/item/1005004574175141.html?sku_id=12000057604741628',
            source_notes='Connect shield pins 1/3/5 to DC+/DC-/CH1 using three separate control wires and the original input screw terminal. Pins 2/4 NC. No input-terminal rework or module pitch match required.',
            outline_mm=None,height_mm=None,assembly_reservation_mm=[60,45,40],reservation_is_measured=False,
            placement_on_shield=None,mounting_mode='external_wired',signal_pitch_mm=5.08,socket_height_mm=8.5,requires_header_rework=False))

# Extend only the old lower outline edge and its adjoining vertical edges.
for item in B.GetDrawings():
    if isinstance(item,p.PCB_SHAPE) and item.GetLayer()==p.Edge_Cuts:
        for name in ('Start','End'):
            pos=getattr(item,'Get'+name)()
            if abs(p.ToMM(pos.y)-46)<.01:getattr(item,'Set'+name)(V(p.ToMM(pos.x),HEIGHT))
    elif isinstance(item,p.PCB_TEXT):
        txt=item.GetText()
        if txt=='1' and abs(p.ToMM(item.GetPosition().x)-67)<.1 and abs(p.ToMM(item.GetPosition().y)-8.89)<.1:item.SetPosition(V(68.75,8.89))
        if txt.startswith('GemilaiMate v'): item.SetText(f'GemilaiMate v{REVISION} SHIELD - PROTOTYPE')
        if item.GetLayer()==p.B_SilkS and txt.startswith('GemilaiMate v'):item.SetPosition(V(32,18.3))
        if item.GetLayer()==p.B_SilkS and txt.startswith('github.com/'):item.SetPosition(V(32,27))
        if p.ToMM(item.GetPosition().y)>43:
            item.Move(V(0,HEIGHT-46-1))
for x,y in [(3,72),(87,72)]:
    fp=p.FOOTPRINT(B);fp.SetAttributes(p.FP_BOARD_ONLY | p.FP_EXCLUDE_FROM_POS_FILES | p.FP_EXCLUDE_FROM_BOM);fp.SetPosition(V(x,y));fp.SetReference('');fp.SetValue('');B.Add(fp)
    pa=p.PAD(fp);pa.SetNumber('');pa.SetPosition(V(x,y));pa.SetAttribute(p.PAD_ATTRIB_NPTH)
    pa.SetShape(p.PAD_SHAPE_CIRCLE);pa.SetSize(V(3.2,3.2));pa.SetDrillSize(V(3.2,3.2));pa.SetLayerSet(p.LSET.AllCuMask());fp.Add(pa)
    fp.Reference().SetVisible(False);fp.Value().SetVisible(False)

# Compact legible front labels, grouped on the free strip between MCU and modules.
for txt,x,y in [('ADS1115 BLUE',16.5,43.7),('CJMCU-0102',42,43.7),('MAX31855',65.706,43.5),('PRESSURE',10.3,73.1),('BUTTONS',32,73.1),('NO MAINS ON BOARD',40,41.0)]:
    t=p.PCB_TEXT(B);t.SetText(txt);t.SetPosition(V(x,y));t.SetLayer(p.F_SilkS)
    t.SetTextSize(V(.8,.8));t.SetTextThickness(p.FromMM(.12));B.Add(t)
# A mechanical access envelope, NOT a copper keepout or measured cable model.
# It reserves 30 mm outside the left edge and the full height of both USB
# ports, including a conservative plug-width allowance, in plan projection.
usb_access=dict(name='ESP32 dual USB plug access',rect_mm=[-30,7.62,4.8,35.56],
                status='design allowance; actual plug/cable and enclosure unmeasured',
                access_from='left',owner='U1')
for aa,bb in [((-30,7.62),(4.8,7.62)),((4.8,7.62),(4.8,35.56)),((4.8,35.56),(-30,35.56)),((-30,35.56),(-30,7.62))]:
    shape(B,aa,bb,p.Dwgs_User,.15)
t=p.PCB_TEXT(B);t.SetText('USB PLUG ACCESS - KEEP FREE');t.SetPosition(V(-13,6));t.SetLayer(p.Dwgs_User)
t.SetTextSize(V(1,1));t.SetTextThickness(p.FromMM(.15));B.Add(t)
D.update(revision=f'{REVISION} SHIELD PROTOTYPE 90x75',size_mm=[W,HEIGHT],
         mechanical_access=[usb_access],
         module_headers_unmeasured=True,manufacturing_release=False)
D['mounts_mm'] += [[3,72],[87,72]]
from mechanical_profiles import build_profiles
D['mechanical_profiles']=build_profiles(D)
(H/'design.json').write_text(json.dumps(D,ensure_ascii=False,indent=2)+'\n')
(H/'module-profiles.json').write_text(json.dumps(dict(status='PROTOTYPE - mechanical validation required',profiles=profiles),ensure_ascii=False,indent=2)+'\n')
for fp in fps.values():
    p.FootprintSave(str(H/'GemilaiMate.pretty'),fp)
p.SaveBoard(str(H/'gemilaimate-shield.kicad_pcb'),B)
print('Shield placement generated: 90x75; 3 local module sockets, 2 wired external controls; no mains copper.')
