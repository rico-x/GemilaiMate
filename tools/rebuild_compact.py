#!/usr/bin/env python3
"""Reproduce accepted compact routing from a checksum-bound SES on a build host.

No fabrication upload or physical USB device is accessed. A new electrical or
placement change invalidates the routing cache and requires a new routing pass.
"""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield-compact'
def routing_input_hash():
 text=(H/'reports/unrouted.dsn').read_text();text=re.sub(r'^\(pcb "[^"\n]+"','(pcb "compact-input.dsn"',text,count=1)
 text=re.sub(r'\(host_version "[^"\n]+"\)','(host_version "10.0.7")',text)
 return hashlib.sha256(text.encode()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kicad-python',default=sys.executable);ap.add_argument('--no-previews',action='store_true');a=ap.parse_args()
 cache=json.loads((H/'reports/route-cache.json').read_text());ses=H/'reports/routed.ses'
 assert hashlib.sha256(ses.read_bytes()).hexdigest()==cache['ses_sha256'],'Routing session changed'
 def py(name):subprocess.run([a.kicad_python,str(H/'scripts'/name)],check=True)
 py('generate.py');py('make_schematic.py')
 subprocess.run(['kicad-cli','sch','export','netlist','-o',str(H/'gemilaimate-compact.net'),str(H/'gemilaimate-compact.kicad_sch')],check=True)
 py('prepare_route.py')
 assert routing_input_hash()==cache['dsn_normalized_sha256'],'Electrical/geometry input changed: cached route must not be reused'
 py('import_route.py');py('finish.py');py('verify_geometry.py')
 subprocess.run([sys.executable,str(R/'tools/export_compact.py'),*(['--no-previews'] if a.no_previews else [])],check=True)
 subprocess.run([sys.executable,str(R/'tools/check_compact_shield.py')],check=True)
 assert hashlib.sha256((H/'gemilaimate-compact.kicad_pcb').read_bytes()).hexdigest()==cache['accepted_pcb_sha256'],'PCB did not reproduce exactly'
 print('PASS exact compact PCB reproduction from pinned routing input/session; physical tests pending')
if __name__=='__main__':main()
