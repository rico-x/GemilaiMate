#!/usr/bin/env python3
"""Independent package-pin and saved-artifact acceptance checks (no hardware)."""
from pathlib import Path
import json,hashlib,math,csv,sexpdata as s
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield-compact'
def children(n,key):return [x for x in n if isinstance(x,list) and str(x[0])==key]
def value(n,key):return children(n,key)[0][1]
def main():
 d=json.loads((H/'design.json').read_text());parts={c['ref']:c for c in d['parts']};aliases={c['designator']:c['ref'] for c in d['parts']}
 pcb=s.loads((H/'gemilaimate-compact.kicad_pcb').read_text());found={}
 for f in children(pcb,'footprint'):
  ref=next(x[2] for x in children(f,'property') if x[1]=='Reference')
  alias=aliases.get(ref,ref)
  for pad in children(f,'pad'):
   if not pad[1]:continue
   nets=children(pad,'net');net=str(nets[0][-1]) if nets else None
   key=(alias,str(pad[1]))
   if key in found:assert found[key]==net,key
   found[key]=net
 # Literal manufacturer package numbers. Deliberately not imported from the
 # generator: DCT/DCU and X2SON have different pins; SO20 != QFN20 for PCA.
 expected={
 'U_LEVEL':{1:'SDA_5V',2:'GND',3:'+3V3',4:'SDA_3V3',5:'SCL_3V3',6:'I2C_OE',7:'+5V_CORE',8:'SCL_5V'},
 'U_LED':{1:'GND',2:'GND',3:'GND',4:'GND',5:'GND',6:'PCA_LED0',7:'PCA_LED1',8:'PCA_LED2',9:'PCA_LED3',10:'GND',11:'PCA_LED4',12:'PCA_LED5',13:'PCA_LED6',14:'PCA_LED7',15:'GND',16:'GND',17:'GND',18:'PCA_SCL',19:'PCA_SDA',20:'+3V3'},
 'U_REG':{1:'+5V_CORE',2:'GND',3:'+3V3'},
 'U_ZC':{2:'ZC_IN',3:'GND',4:'PUMP_ZC',5:'+3V3'},
 'U_PUMP':{1:'OUTPUT_OE_N',2:'PUMP_PWM',3:'GND',4:'PUMP_OUT',5:'+3V3'},
 'U_SSR':{1:'OUTPUT_OE_N',2:'VALVE',3:'VALVE_5V',4:'OUTPUT_OE_N',5:'HEATER',6:'HEATER_5V',7:'GND',8:'ALT_5V',9:'ALT',10:'OUTPUT_OE_N',12:'GND',13:'+5V_EXT',14:'+5V_EXT'},
 'U_ESD':{1:'USB_DM',2:'GND',3:'USB_DP',4:'USB_DP',5:'USB_VBUS',6:'USB_DM'},
 'U1':{1:'GND',2:'+3V3',3:'EN',4:'TC_DO',5:'GPIO5',6:'TC_SCK',7:'TC_CS',8:'GPIO15',9:'GPIO16',10:'SCALE_CLK',11:'SCALE_DAT0',12:'EXT3',13:'USB_DM_MCU',14:'USB_DP_MCU',15:'STRAP3',16:'STRAP46',17:'PUMP_PWM',18:'VALVE',19:'BOARD_ID',20:'EXT4',21:'EXT5',22:'HEATER',23:'PUMP_ZC',24:'ALT',25:'STEAM',26:'STRAP45',27:'BOOT',31:'BREW',32:'SCALE_DAT1',33:'DETECT_EN',34:'SCL_3V3',35:'SDA_3V3',36:'ALBA_SCL',37:'ALBA_SDA',38:'EXT2',39:'EXT1',40:'GND',41:'GND'}}
 for ref,pins in expected.items():
  for pin,net in pins.items():assert found[(ref,str(pin))]==net,(ref,pin,net,found.get((ref,str(pin))))
 for pin in [28,29,30]:assert found[('U1',str(pin))].startswith('unconnected-'),('PSRAM exposed',pin)
 for item in children(pcb,'segment')+children(pcb,'via'):
  net=children(item,'net')
  assert not net or not str(net[0][-1]).startswith('unconnected-'), 'NC/PSRAM fanout must not be routed'
 # A second independent comparison with the actual exported schematic netlist.
 netlist=s.loads((H/'gemilaimate-compact.net').read_text())
 for net in children(netlist,'nets')[0][1:]:
  name=str(value(net,'name'))
  for node in children(net,'node'):
   ref=str(value(node,'ref'));pin=str(value(node,'pin'))
   if ref.startswith('#'):continue
   assert found[(aliases[ref],pin)]==name,(ref,pin,name)
 assert parts['U_LEVEL']['source_footprint'].endswith('TXS0102_DCT_SSOP8')
 assert parts['U_LED']['source_footprint'].endswith('TSSOP-20_4.4x6.5mm_P0.65mm')
 assert parts['R_ID_TOP']['value']=='10k 1%' and parts['R_ID_LOW']['value']=='1.2k 1%'
 vmin=3.3*.95*(1200*.99)/(10000*1.01+1200*.99)
 vmax=3.3*1.05*(1200*1.01)/(10000*.99+1200*1.01)
 assert .3<vmin<vmax<.4
 assert d['size_mm']==[65,50] and d['copper_layers']==4 and d['board_id']==3
 assert d['hardware_tested'] is False and d['manufacturing_release'] is False
 assert d['physical_flash_mb']==16 and d['compatible_partition_flash_mb']==8 and d['psram_mb']==8
 assert d['peripheral_gpio']==dict(sda=43,scl=44)
 for c in parts.values():
  if c['section']=='Connectors':assert c['side']=='back' and 'JST_PH_B' in c['source_footprint']
 erc=json.loads((H/'reports/erc.json').read_text());drc=json.loads((H/'reports/drc.json').read_text())
 assert not any(sh['violations'] for sh in erc['sheets'])
 assert all(not drc[k] for k in ['violations','unconnected_items','schematic_parity'])
 report=json.loads((H/'reports/layout.json').read_text());assert report['minimum_track_mm']>=.2
 assert all(x['via_overlaps']==0 for x in report['visible_labels'])
 # Socket marking order is checked spatially, including the reversed MAX row.
 for ref in ['J_ADS','J_TC']:
  c=parts[ref];owner=c['designator'];pins=sorted(c['pins'],key=lambda x:x['x'])
  words=[]
  for pin in pins:
   label=next((t for t in report['visible_labels'] if t['owner']==owner+'.'+pin['number']),None)
   if label is None:
    assert pin['net'] is None;continue
   assert abs(label['position_mm'][0]-pin['x'])<.01
   words.append(label['text'])
  if ref=='J_TC':assert words[0]=='CLK' and words[-1]=='VIN',words
 placements=list(csv.DictReader((H/'manufacturing/CPL-SMD.csv').open()))
 assert len(placements)==72
 u1=next(p for p in placements if p['Designator']=='U1')
 assert abs(float(u1['Mid X_mm'])-15)<.001 and abs(float(u1['Mid Y_mm'])-5.6)<.001
 assert 'U1' not in {p['Reference'] for p in csv.DictReader((H/'manufacturing/BOM-THT.csv').open())}
 manifest=json.loads((H/'manufacturing/manifest.json').read_text())
 assert manifest['revision']==d['revision']==json.loads((H/'revision.json').read_text())['revision']
 assert manifest['pcb_sha256']==hashlib.sha256((H/'gemilaimate-compact.kicad_pcb').read_bytes()).hexdigest()
 assert manifest['hardware_tested'] is False and manifest['manufacturing_release'] is False
 print('PASS compact: physical package pins, schematic parity, memory/ID, GPIO reservations, marking order, saved ERC/DRC and hashes')
if __name__=='__main__':main()
