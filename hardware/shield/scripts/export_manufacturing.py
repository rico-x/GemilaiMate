from pathlib import Path
import csv,json,hashlib
from kicad_runtime import application
_app=application()
import pcbnew as p
out=Path(__file__).resolve().parents[1];m=out/'manufacturing';d=json.loads((out/'design.json').read_text());board=p.LoadBoard(str(out/'gemilaimate-shield.kicad_pcb'))
# Match the physical KiCad pad coordinates, including alternative ESP rows,
# against the design used for assembly and mechanical access checks.
for c in d['parts']:
 fp=next(fp for fp in board.GetFootprints() if fp.GetReference()==c['ref'])
 expected={(round(pa['x'],5),round(pa['y'],5)):pa for pa in c.get('physical_pads',c['pins'])}
 actual={(round(p.ToMM(pa.GetPosition().x),5),round(p.ToMM(pa.GetPosition().y),5)):pa for pa in fp.Pads()}
 assert actual.keys()==expected.keys(), 'PCB/design pad position mismatch: '+c['ref']
 for xy,pa in actual.items():
  # Unused pins in the alternative ESP row are unnumbered NPTH guides.
  assert pa.GetNumber()==expected[xy]['number'] or (not expected[xy]['net'] and not pa.GetNumber() and pa.GetAttribute()==p.PAD_ATTRIB_NPTH), 'PCB/design pad numbering mismatch: '+c['ref']
for t in board.GetTracks():
 if isinstance(t,p.PCB_VIA):t.SetFrontTentingMode(p.TENTING_MODE_TENTED);t.SetBackTentingMode(p.TENTING_MODE_TENTED)
p.SaveBoard(str(out/'gemilaimate-shield.kicad_pcb'),board)
def csvout(name,columns,rows):
 with (m/name).open('w',newline='') as f:
  w=csv.writer(f);w.writerow(columns);w.writerows(rows)
rows=[
 ['R1 R3 R4 R5 R8 R9 R11',7,'10k 1% >=0.125W','0805','Yageo','RC0805FR-0710KL'],
 ['R2',1,'1.2k 1% >=0.125W','0805','Yageo','RC0805FR-071K2L'],
 ['R6 R7 R10 R12',4,'1k 1% >=0.125W','0805','Yageo','RC0805FR-071KL'],
 ['R13',1,'0 ohm jumper','0805','Yageo','RC0805JR-070RL'],
 ['C1 C2 C3 C4 C5 C6',6,'100nF 50V X7R +/-10%','0805','Samsung','CL21B104KBCNNNC'],
 ['U3',1,'Non-inverting Schmitt; 5.5V input; 3.3V VCC','SOT-23-5 DBV','Texas Instruments','SN74LVC1G17DBVR']]
csvout('BOM-SMD.csv',['Designators','Quantity_per_board','Requirement','Package','Manufacturer_example','MPN_example'],rows)
assert sum(row[1] for row in rows)==20
csvout('BOM-THT.csv',['Reference','Quantity_per_board','Description','Assembly_notes'],[
 ['U1 upper/lower',2,'1x22 female 2.54mm >=8.5mm nominal','Populate ONE of the lower alternatives; verify real DevKit'],
 ['U2',1,'SN74AHCT125N PDIP-14','Same logic as carrier v0.1'],
 ['J2',1,'1x10 female 2.54mm >=8.5mm','ADS1115 Blue; ten pins, ADDR wired GND'],
 ['J7',2,'1x5 female 2.54mm >=8.5mm','CJMCU-0102 rows 12.70mm ASSUMED; extra G left NC'],
 ['J3',1,'1x6 female 2.54mm >=8.5mm','MAX31855 VIN,3Vo NC,GND,DO,CS,CLK'],
 ['J5',1,'1x4 female 2.54mm >=8.5mm','Four-wire control harness to separately retained RobotDyn; pin 1 LEFT; no direct docking'],
 ['J6',1,'1x5 female 2.54mm >=8.5mm','Three-wire control harness, shield pins 1/3/5 to original SSR DC+/DC-/CH1 screw terminal; 2/4 NC'],
 ['J1 J9 JP1',3,'1x2 male 2.54mm','Power/display/USB disconnect'],
 ['J4 J10 JP3',3,'1x3 male 2.54mm','Pressure / unused heater / MAX VIN select'],
 ['J8',1,'1x4 male 2.54mm','Dry contact buttons only'],
 ['JP1 JP3 shunts',2,'2.54mm removable shunt','Open JP1 for USB'],
 ['Module-side headers',1,'1x10 + (2 x 1x5) + 1x6 male 2.54mm','TXS uses TWO independent 1x5 rows; 12.70mm spacing ASSUMED until measured, not a standard 2x5 block'],
 ['J5 J6 control harnesses',1,'4 + 3 flexible control wires; male 2.54mm contacts at shield','RobotDyn original header and SSR original input terminal; do not remove SSR screw terminals'],
 ['Mechanical retention',1,'Insulating tray, adjustable padded keepers and underside supports','Use existing four PCB mounts; retain each module PCB edge independently per docs/retention.md'],
 ['PCB fasteners',4,'M3 nylon or insulated head <=5.5mm; no washers','J4 moved right by 1.27mm; respect mating-plug allowance and check real hardware'],
])

pos=list(csv.DictReader((m/'positions-kicad.csv').open()));byref={c['ref']:c for c in d['parts']};assert len(pos)==20
for r in pos:
 c=byref[r['Ref']];assert abs(float(r['PosX'])-c['x'])<.00001 and abs(float(r['PosY'])+c['y'])<.00001
csvout('CPL-SMD.csv',['Designator','Mid_X_mm','Mid_Y_mm','Layer','Rotation_deg'],[[r['Ref'],f"{float(r['PosX']):.6f}",f"{d['size_mm'][1]+float(r['PosY']):.6f}",'Top',r['Rot']] for r in pos])
tracks=list(board.GetTracks());pads=[pa for fp in board.GetFootprints() for pa in fp.Pads()];stats={'board_size_mm':d['size_mm'],'copper_layers':2,'electronic_components':len(d['parts']),'smd_placements':len(pos),'smd_unique_types':6,'smd_solder_contacts':43,'tht_solder_contacts_selected_socket_rows':112,'track_segments':sum(not isinstance(t,p.PCB_VIA) for t in tracks),'vias':sum(isinstance(t,p.PCB_VIA) for t in tracks),'pth_pad_sites_including_alternative_row':sum(pa.GetAttribute()==p.PAD_ATTRIB_PTH for pa in pads),'npth_sites':sum(pa.GetAttribute()==p.PAD_ATTRIB_NPTH for pa in pads),'all_vias_tented':True,'pcb_sha256':hashlib.sha256((out/'gemilaimate-shield.kicad_pcb').read_bytes()).hexdigest()};(out/'board-stats.json').write_text(json.dumps(stats,indent=2));print(stats)

pth=[pa for fp in board.GetFootprints() for pa in fp.Pads() if pa.GetAttribute()==p.PAD_ATTRIB_PTH]
assert all(pa.GetLayerSet().Contains(p.F_Mask) and pa.GetLayerSet().Contains(p.B_Mask) for pa in pth), 'THT mask openings missing'
stats['pth_mask_front_openings']=len(pth);stats['pth_mask_back_openings']=len(pth)
(out/'board-stats.json').write_text(json.dumps(stats,indent=2))
