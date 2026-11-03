#!/usr/bin/env python3
"""Reproduce accepted compact routing from a checksum-bound SES on a build host.

No fabrication upload or physical USB device is accessed. A new electrical or
placement change invalidates the routing cache and requires a new routing pass.
"""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
import sexpdata as s
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield-compact'
# Collections whose order follows KiCad's internal object order, not the design:
# head symbol -> number of leading items that stay in place before sorting the rest.
UNORDERED={'placement':1,'network':1,'library':1,'wiring':1,'pins':1,'component':2,'class':2}
def canonical(node):
 if not isinstance(node,list):return node
 node=[canonical(x) for x in node]
 keep=UNORDERED.get(str(node[0])) if node and isinstance(node[0],s.Symbol) else None
 return node[:keep]+sorted(node[keep:],key=s.dumps) if keep else node
def canonical_dsn(tree):
 # KiCad names footprint image variants "::1", "::2" in encounter order: name them by content.
 lib=next(x for x in tree if isinstance(x,list) and str(x[0])=='library')
 alias={str(x[1]):'image-'+hashlib.sha256(s.dumps(canonical(x[2:])).encode()).hexdigest()[:16]
        for x in lib if isinstance(x,list) and str(x[0])=='image'}
 def rename(n):return [rename(x) for x in n] if isinstance(n,list) else alias.get(str(n),n) if isinstance(n,(str,s.Symbol)) else n
 tree=rename(tree)
 # One placement entry per instance; the grouping of instances under images follows the same order.
 tree=[[x[0]]+[[comp[0],comp[1],place] for comp in x[1:] for place in comp[2:]] if isinstance(x,list) and str(x[0])=='placement' else x for x in tree]
 return canonical(tree)
def routing_input_hash():
 text=(H/'reports/unrouted.dsn').read_text();text=re.sub(r'^\(pcb "[^"\n]+"','(pcb "compact-input.dsn"',text,count=1)
 text=re.sub(r'\(host_version "[^"\n]+"\)','(host_version "10.0.7")',text)
 text=text.replace('(string_quote ")','',1)  # a lone quote is not an s-expression token
 return hashlib.sha256(s.dumps(canonical_dsn(s.loads(text))).encode()).hexdigest()
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
