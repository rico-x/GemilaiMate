#!/usr/bin/env python3
"""Check the active shield variant and pin-layout invariants without hardware."""
from pathlib import Path
import csv,hashlib,json,subprocess,sys
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield'
def check_usb_access(d):
 parts={c['ref']:c for c in d['parts']}
 access=d['mechanical_access']
 assert len(access)==1 and access[0]['owner']=='U1'
 zone=access[0]['rect_mm']
 assert zone==[-30,7.62,4.8,35.56] and access[0]['access_from']=='left'
 for ref,c in parts.items():
  if ref=='U1':continue
  b=c['rect']
  assert not (max(b[0],zone[0])<min(b[2],zone[2]) and max(b[1],zone[1])<min(b[3],zone[3])), f'{ref} blocks USB access'
 dock=parts['J5'];pins=dock['pins']
 assert dock['module_profile']['dock_outward']=='bottom'
 assert [p['net'] for p in pins]==['+5V','GND','ZC_RAW','PUMP_PWM']
 assert all(abs(p['y']-71.12)<1e-6 for p in pins)
 assert all(abs(p['x']-(41.91+i*2.54))<1e-6 for i,p in enumerate(pins))
 assert dock['rect'][1]-zone[3]>30

def main():
 d=json.loads((H/'design.json').read_text());parts={c['ref']:c for c in d['parts']}
 check_usb_access(d)
 assert d['size_mm']==[90,75] and len(parts)==34
 assert d['module_headers_unmeasured'] is True
 board=(H/'gemilaimate-shield.kicad_pcb').read_text()
 assert 'github.com/Rico-X/GemilaiMate' in board and 'Rico-X' in board
 stats=json.loads((H/'board-stats.json').read_text())
 assert stats['pcb_sha256']==hashlib.sha256((H/'gemilaimate-shield.kicad_pcb').read_bytes()).hexdigest()
 assert stats['pth_mask_front_openings']==stats['pth_pad_sites_including_alternative_row']
 assert stats['pth_mask_back_openings']==stats['pth_pad_sites_including_alternative_row']
 for suffix in ['F_Mask.gts','B_Mask.gbs']:
  assert (H/'manufacturing/gerber'/('gemilaimate-shield-'+suffix)).read_text().count('D03*')>=stats['pth_pad_sites_including_alternative_row']
 assert stats['smd_placements']==20 and stats['board_size_mm']==[90,75]
 assert (H/'manufacturing/BOM-SMD.csv').read_bytes()==(R/'hardware/carrier/manufacturing/BOM-SMD.csv').read_bytes()
 for fn in ['erc.json','drc.json']:
  report=json.loads((H/fn).read_text())
  if fn=='erc.json':assert all(not s['violations'] for s in report['sheets'])
  else:assert all(not report[k] for k in ['violations','unconnected_items','schematic_parity'])
 pins=lambda ref:{int(p['number']):p for p in parts[ref]['pins']}
 ads=pins('J2');txs=pins('J7');tc=pins('J3');ssr=pins('J6')
 assert len(ads)==10 and len(txs)==10 and len(tc)==6 and len(ssr)==5
 assert ads[5]['net']=='GND' and ads[7]['net']=='PRESSURE'
 assert all(ads[i]['net'] is None for i in [6,8,9,10])
 assert tc[2]['name']=='3VO_NC' and tc[2]['net'] is None
 assert txs[7]['net'] is None and txs[2]['net']==txs[3]['net']=='+3V3'
 assert [ssr[i]['net'] for i in [1,3,5]]==['+5V','GND','VALVE_IN']
 assert ssr[2]['net'] is None and ssr[4]['net'] is None
 assert abs(ssr[3]['y']-ssr[1]['y']-5.08)<.00001
 assert abs(ssr[5]['y']-ssr[3]['y']-5.08)<.00001
 # Nominal local module bodies must fit and not cross one another/RF zone.
 boxes=[parts[r]['rect'] for r in ['J2','J3','J7']]
 overlap=lambda a,b:max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])
 for i,b in enumerate(boxes):
  assert 0<=b[0]<b[2]<=90 and 0<=b[1]<b[3]<=75
  assert not overlap(b,d['rf_keepout'])
  assert all(not overlap(b,c) for c in boxes[i+1:])
 assert parts['J3']['rect'][1]-d['rf_keepout'][3]>=15
 pos=list(csv.DictReader((H/'manufacturing/CPL-SMD.csv').open()))
 assert len(pos)==20
 for row in pos:
  c=parts[row['Designator']]
  assert abs(float(row['Mid_X_mm'])-c['x'])<.00001
  assert abs(float(row['Mid_Y_mm'])-(75-c['y']))<.00001
 subprocess.run([sys.executable,str(H/'scripts/verify_netlist.py')],check=True,stdout=subprocess.DEVNULL)
 subprocess.run([sys.executable,str(R/'tools/build_shield_page.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
 print('PASS shield: electrical reports, hardware hash, shared SMD BOM, NC outputs, socket pinout, nominal fit, CPL and 13 firmware GPIOs')
if __name__=='__main__':main()
