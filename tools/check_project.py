#!/usr/bin/env python3
"""Validate the current project structure and manufacturing inputs without hardware access."""
from pathlib import Path
import json,re,hashlib,csv,urllib.parse,subprocess,sys
R=Path(__file__).resolve().parents[1];H=R/'hardware/carrier'
assert (R/'VERSION').read_text().strip()=='0.1.0'
assert 'Проект пока не воспроизводился в железе' in (R/'README.md').read_text()
assert not any((R/p).exists() for p in ['history','upstream','gaggimate-carrier-revA','gaggimate-firmware-gemilai-revB'])
for path in [R/'README.md']+list((R/'docs').glob('*.md')):
 for url in re.findall(r'\]\(([^)]+)\)',path.read_text()):
  if '://' in url or url.startswith('#'):continue
  assert (path.parent/urllib.parse.unquote(url.split('#')[0])).exists(),(path,url)
for file in list((R/'firmware/src').rglob('*.cpp'))+list((R/'firmware/src').rglob('*.h')):
 text=file.read_text()
 assert 'github.com/jniebuhr/gaggimate/releases' not in text,file
 assert 'https://gaggimate.eu' not in text,file
board=(H/'gemilaimate-carrier.kicad_pcb').read_text();assert 'github.com/Rico-X/GemilaiMate' in board and 'Rico-X' in board
stats=json.loads((H/'board-stats.json').read_text());assert stats['pcb_sha256']==hashlib.sha256((H/'gemilaimate-carrier.kicad_pcb').read_bytes()).hexdigest()
assert stats['board_size_mm']==[90,46] and stats['smd_placements']==20
assert len(list(csv.DictReader((H/'manufacturing/CPL-SMD.csv').open())))==20
assert sum(int(row['Quantity_per_board']) for row in csv.DictReader((H/'manufacturing/BOM-SMD.csv').open()))==20
e=json.loads((H/'erc.json').read_text());assert all(not x['violations'] for x in e['sheets'])
d=json.loads((H/'drc.json').read_text());assert all(not d[x] for x in ['violations','unconnected_items','schematic_parity'])
subprocess.run([sys.executable,str(R/'tools/build_wiring_page.py'),'--check'],check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,str(R/'tools/check_shield.py')],check=True)
print('PASS current project: links, branding, prototype notice, hardware hashes, BOM/CPL, stored ERC/DRC, wiring page')
