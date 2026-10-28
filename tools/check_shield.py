#!/usr/bin/env python3
"""Check the active shield variant and pin-layout invariants without hardware."""
from pathlib import Path
import argparse,csv,hashlib,json,math,subprocess,sys
from collections import Counter
import sexpdata as sx
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
 assert dock['module_profile']['mounting_mode']=='external_wired'
 assert [p['net'] for p in pins]==['+5V','GND','ZC_RAW','PUMP_PWM']
 assert all(abs(p['y']-71.12)<1e-6 for p in pins)
 assert all(abs(p['x']-(41.91+i*2.54))<1e-6 for i,p in enumerate(pins))
 assert dock['rect'][1]-zone[3]>30

def check_mechanical_profiles(d):
 m=d['mechanical_profiles'];items=m['occupied'];owners={i['owner'] for i in items if i['kind']=='mated_plug'}
 assert owners=={'J1','J4','J8','J9','J5','J6'}
 assert all(i['measured'] is False for i in items)
 overlaps=lambda a,b:all(max(a[k],b[k])<min(a[k+3],b[k+3]) for k in range(3))
 for ix,a in enumerate(items):
  assert all(a['bbox_mm'][k]<a['bbox_mm'][k+3] for k in range(3))
  for b in items[ix+1:]:
   if a['owner']!=b['owner']:
    assert not overlaps(a['bbox_mm'],b['bbox_mm']), f"Nominal occupied envelopes collide: {a['id']} / {b['id']}"
  if a['owner']!='U1':
   zone=d['mechanical_access'][0]['rect_mm'];box=a['bbox_mm']
   assert not(max(box[0],zone[0])<min(box[3],zone[2]) and max(box[1],zone[1])<min(box[4],zone[3])),a['id']+' blocks USB'
 fast=m['fasteners'];assert fast['head_diameter_max_mm']==5.5 and fast['washer_allowed'] is False
 for x,y in d['mounts_mm']:
  for a in items:
   b=a['bbox_mm'];distance=math.hypot(max(b[0]-x,0,x-b[3]),max(b[1]-y,0,y-b[4]))
   assert distance-fast['head_diameter_max_mm']/2>=fast['minimum_planar_gap_mm'],f"M3 head / {a['id']} interference"
 for ext in m['external_power_modules']:
  assert ext['mounting_mode']=='external_wired' and ext['placement_mm'] is None
  assert ext['reservation_is_measured'] is False and ext['clearance_result'].startswith('NOT ASSESSED')

def check_markings(board,d):
 tree=sx.loads(board)
 field=lambda node,key:next((v for v in node if isinstance(v,list) and v and str(v[0])==key),None)
 footprints={next(p[2] for p in n if isinstance(p,list) and len(p)>2 and str(p[0])=='property' and p[1]=='Reference'):n for n in tree if isinstance(n,list) and n and str(n[0])=='footprint'}
 for ref in ['J2','J3','J5','J6','J7']:
  fp=footprints[ref];part=next(c for c in d['parts'] if c['ref']==ref)
  pad1=[p for p in fp if isinstance(p,list) and len(p)>3 and str(p[0])=='pad' and p[1]=='1']
  assert len(pad1)==1 and str(pad1[0][3])=='rect',ref+' needs square pad 1'
  texts={n[2] for n in fp if isinstance(n,list) and len(n)>2 and str(n[0])=='fp_text' and field(n,'layer')[1]=='F.SilkS'}
  assert set(part['module_profile']['silk_labels'])<=texts,ref+' missing silk labels'
  at=field(fp,'at');ox,oy=map(float,at[1:3]);assert len(at)<4 or float(at[3])==0
  point=lambda n,key:tuple(round(float(v)+(ox if i==0 else oy),4) for i,v in enumerate(field(n,key)[1:3]))
  lines={frozenset((point(n,'start'),point(n,'end'))) for n in fp if isinstance(n,list) and n and str(n[0])=='fp_line' and field(n,'layer')[1]=='F.SilkS'}
  a,b,c,e=part['rect'];corners=[(a,b),(c,b),(c,e),(a,e)]
  expected={frozenset((tuple(round(v,4) for v in corners[i]),tuple(round(v,4) for v in corners[(i+1)%4]))) for i in range(4)}
  assert expected<=lines,ref+' missing full F.SilkS outline'
  labels={n[2]:n for n in fp if isinstance(n,list) and len(n)>2 and str(n[0])=='fp_text' and field(n,'layer')[1]=='F.SilkS'}
  pad_x={p[1]:float(field(p,'at')[1])+ox for p in fp if isinstance(p,list) and len(p)>3 and str(p[0])=='pad' and p[1]}
  if ref in ['J2','J3']:
   # Derive the endpoint order from physical PCB pad X, independently of
   # the declared list of expected label strings.
   endpoint_labels=[text for text in labels if ' ... ' in text]
   assert len(endpoint_labels)==1
   endpoints=sorted(pad_x,key=pad_x.get)
   names={p['number']:p['name'] for p in part['pins']}
   expected_names=[names[endpoints[0]],names[endpoints[-1]]]
   assert endpoint_labels[0].split(' ... ')==expected_names,ref+' label order disagrees with physical pad X'
   at_label=field(labels[endpoint_labels[0]],'at')
   assert len(at_label)<4 or float(at_label[3])==0,ref+' endpoint label must read left to right'
  if ref in ['J2','J7']:
   # Assembly labels belong inside their own module and next to its row,
   # not over the cable connectors on the bottom edge.
   for text,n in labels.items():
    x,y=point(n,'at')
    assert a<x<c and b<y<e,ref+' label is outside its own module outline'
   x,y=point(labels['1'],'at');pin1=next(p for p in part['pins'] if p['number']=='1')
   assert abs(x-pin1['x'])<.2 and 0<pin1['y']-y<3,ref+' pin-1 label is not next to pad 1'
  if ref=='J7':
   y_a=point(labels['A 3V3'],'at')[1];y_b=point(labels['B 5V'],'at')[1]
   pins={p['number']:p for p in part['pins']}
   assert 0<pins['1']['y']-y_a<3 and 0<y_b-pins['6']['y']<3,'J7 row labels are not next to their rows'

def check_harness_housings():
 for variant,gender,j6_size in [('shield','MALE','1x5'),('carrier','FEMALE','1x3')]:
  rows={r['Reference']:r for r in csv.DictReader((R/'hardware'/variant/'manufacturing/BOM-THT.csv').open())}
  for ref,size in [('J5','1x4'),('J6',j6_size)]:
   row=rows[ref+' harness housing'];desc=row['Description'];note=row['Assembly_notes']
   assert row['Quantity_per_board']=='1' and desc.startswith('Single '+size)
   assert 'with '+gender+' crimp contacts' in desc
   assert 'pin 1 RED' in note and 'Not mechanically keyed' in note
  assert 'positions 2/4 EMPTY' in rows['J6 harness housing']['Assembly_notes'] if variant=='shield' else 'consecutive pins 1,2,3' in rows['J6 harness housing']['Assembly_notes']

def expected_silk_labels(board):
 tree=sx.loads(board)
 field=lambda n,k:next((x for x in n if isinstance(x,list) and x and str(x[0])==k),None)
 def visible(n):
  for group in [n,field(n,'effects') or []]:
   if any((isinstance(x,sx.Symbol) and str(x)=='hide') or (isinstance(x,list) and x and str(x[0])=='hide' and (len(x)==1 or str(x[1])=='yes')) for x in group):return False
  return True
 def key(owner,n,text):
  layer=field(n,'layer')
  return (owner,layer[1],text) if layer and layer[1] in ['F.SilkS','B.SilkS'] and visible(n) else None
 result=[]
 for n in tree:
  if not isinstance(n,list) or not n:continue
  if str(n[0]) in ['gr_text','gr_text_box']:
   k=key('BOARD',n,n[1])
   if k:result.append(k)
  elif str(n[0])=='footprint':
   owner=next(x[2] for x in n if isinstance(x,list) and len(x)>2 and str(x[0])=='property' and x[1]=='Reference')
   for t in n:
    if isinstance(t,list) and len(t)>2 and str(t[0]) in ['property','fp_text','fp_text_box']:
     k=key(owner,t,t[1] if str(t[0])=='fp_text_box' else t[2])
     if k:result.append(k)
 return Counter(result)

def check_silk_report(board,report,pcb_sha):
 assert report['pcb_sha256']==pcb_sha and report['margin_mm']>=.15
 actual=Counter((r['owner'],r['layer'],r['text']) for r in report['labels'])
 assert actual==expected_silk_labels(board),'Silk report must cover every visible PCB/footprint silk text'
 assert all(r['via_overlaps']==0 for r in report['labels']),'A visible silkscreen text overlaps a via'
 checked=[r for r in report['labels'] if r['track_check_required']]
 assert {r['text'] for r in checked}=={'MAX31855','ROBOTDYN CABLE','DC+'}
 assert all(r['side_track_overlaps']==0 for r in checked)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--write-report',action='store_true');args=ap.parse_args()
 d=json.loads((H/'design.json').read_text());parts={c['ref']:c for c in d['parts']}
 check_usb_access(d)
 check_mechanical_profiles(d)
 profiles={p['reference']:p for p in json.loads((H/'module-profiles.json').read_text())['profiles']}
 for ref in ['J5','J6']:
  assert profiles[ref]['body_rect_mm'] is None and profiles[ref]['connector_rect_mm']==parts[ref]['rect']
  assert profiles[ref]['mounting_mode']==parts[ref]['module_profile']['mounting_mode']=='external_wired'
 assert profiles['J6']['requires_header_rework'] is False
 assert d['size_mm']==[90,75] and len(parts)==34
 assert d['module_headers_unmeasured'] is True
 board=(H/'gemilaimate-shield.kicad_pcb').read_text()
 assert 'github.com/Rico-X/GemilaiMate' in board and 'Rico-X' in board
 check_markings(board,d)
 check_harness_housings()
 stats=json.loads((H/'board-stats.json').read_text())
 assert stats['pcb_sha256']==hashlib.sha256((H/'gemilaimate-shield.kicad_pcb').read_bytes()).hexdigest()
 silk=json.loads((H/'silk-clearance.json').read_text())
 check_silk_report(board,silk,stats['pcb_sha256'])
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
 report=dict(revision=d['revision'],pcb_sha256=stats['pcb_sha256'],nominal_module_plug_cable_envelopes='PASS',
             marking_checks='PASS: square pad 1, endpoint words follow physical pad X, labels next to own rows, full outlines; all visible front/back texts clear of vias; selected track checks retained',
             visible_silk_texts_checked=len(silk['labels']),
             harness_housings='Single marked housings: shield J5 1x4 / J6 1x5 (2/4 empty); carrier J5 1x4 / J6 1x3. Unkeyed: verify orientation before power.',
             populated_mating_connector_profiles=['J1','J4','J8','J9','J5','J6'],
             mounting_head_max_diameter_mm=5.5,washers_allowed=False,
             external_power_modules='NOT PLACED: J5 and J6 use control wires; separate retention required',
             real_module_geometry_verified=False,real_connector_geometry_verified=False,
             physical_retention_verified=False,machine_fit_verified=False)
 report_path=H/'mechanical-check.json'
 if args.write_report:report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 else:assert json.loads(report_path.read_text())==report,'Mechanical report is stale'
 print('PASS shield: electrical reports, hardware hash, square pin 1 and silk outlines/labels, nominal module/plug/cable/M3 clearance, shared BOM and 13 GPIOs. Real fit and external power-module layout NOT VERIFIED.')
if __name__=='__main__':main()
