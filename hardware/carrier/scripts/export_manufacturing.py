from pathlib import Path
import csv,json,hashlib
import pcbnew as p
out=Path(__file__).resolve().parents[1];m=out/'manufacturing';d=json.loads((out/'design.json').read_text());board=p.LoadBoard(str(out/'gemilaimate-carrier.kicad_pcb'))
for t in board.GetTracks():
 if isinstance(t,p.PCB_VIA):t.SetFrontTentingMode(p.TENTING_MODE_TENTED);t.SetBackTentingMode(p.TENTING_MODE_TENTED)
p.SaveBoard(str(out/'gemilaimate-carrier.kicad_pcb'),board)
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
 ['U1 socket upper',1,'1x22 female 2.54mm; height >=8.5mm nominal','Verify >=5mm free under actual DevKit; use only one lower row'],
 ['U1 socket lower A OR B',1,'1x22 female 2.54mm; matching height','Row spacing 22.86 OR 25.40mm; one only'],
 ['U2',1,'SN74AHCT125N PDIP-14','Pin1/orientation from assembly drawing'],
 ['J1 J9 JP1',3,'1x2 male 2.54mm','JP1 removable jumper'],
 ['J4 J6 J10 JP3',4,'1x3 male 2.54mm','J10 unused; JP3 one removable jumper'],
 ['J5 J8',2,'1x4 male 2.54mm','Cable pin order in connections.csv'],
 ['J5 harness housing',1,'Single 1x4 Dupont 2.54mm housing with FEMALE crimp contacts','Populate 1,2,3,4; mark pin 1 RED on housing and align with PCB pin 1. One housing, no loose single-pole plugs. Not mechanically keyed.'],
 ['J6 harness housing',1,'Single 1x3 Dupont 2.54mm housing with FEMALE crimp contacts','Carrier J6 uses consecutive pins 1,2,3; NOT the shield 1/3/5 housing. Mark pin 1 RED; no loose single-pole plugs. Not mechanically keyed.'],
 ['J3',1,'1x5 male 2.54mm','MAX module VIN selection'],
 ['J2',1,'1x6 male 2.54mm','ADS1115 A0; ADDR=GND'],
 ['J7',1,'1x8 male 2.54mm','One TXS0102 for I2C only'],
 ['JP1 JP3 shunts',2,'2.54mm removable shunt','JP1 open for USB; JP3 match MAX module'],
 ['U1 DevKit (installed after test)',1,'ESP32-S3 DevKitC-1 N8R8 44 pins','Owner-supplied external module; not included in automatic SMD placement'],
 ])
pos=list(csv.DictReader((m/'positions-kicad.csv').open()));byref={c['ref']:c for c in d['parts']};assert len(pos)==20
for r in pos:
 c=byref[r['Ref']];assert abs(float(r['PosX'])-c['x'])<.00001 and abs(float(r['PosY'])+c['y'])<.00001
csvout('CPL-SMD.csv',['Designator','Mid_X_mm','Mid_Y_mm','Layer','Rotation_deg'],[[r['Ref'],f"{float(r['PosX']):.6f}",f"{46+float(r['PosY']):.6f}",'Top',r['Rot']] for r in pos])
tracks=list(board.GetTracks());pads=[pa for fp in board.GetFootprints() for pa in fp.Pads()];stats={'board_size_mm':[90,46],'copper_layers':2,'electronic_components':len(d['parts']),'smd_placements':len(pos),'smd_unique_types':6,'smd_solder_contacts':43,'tht_solder_contacts_selected_socket_rows':103,'track_segments':sum(not isinstance(t,p.PCB_VIA) for t in tracks),'vias':sum(isinstance(t,p.PCB_VIA) for t in tracks),'pth_pad_sites_including_alternative_row':sum(pa.GetAttribute()==p.PAD_ATTRIB_PTH for pa in pads),'npth_sites':sum(pa.GetAttribute()==p.PAD_ATTRIB_NPTH for pa in pads),'all_vias_tented':True,'pcb_sha256':hashlib.sha256((out/'gemilaimate-carrier.kicad_pcb').read_bytes()).hexdigest()};(out/'board-stats.json').write_text(json.dumps(stats,indent=2));print(stats)
