#!/usr/bin/env python3
"""Continue a saved trial in an isolated copy; accept only fresh KiCad results."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ap=argparse.ArgumentParser()
ap.add_argument('--source',required=True,type=Path)
ap.add_argument('--output',required=True,type=Path)
ap.add_argument('--mode',default='normal')
a=ap.parse_args()
src=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
rel=Path('hardware/shield-compact')
for r in [rel,Path('hardware/shield/scripts')]:
    shutil.copytree(src/r,out/r,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__','previews','manufacturing'))
h=out/rel;log=(out/'build.log').open('w');started=time.time()
def run(args,timeout=180):
    subprocess.run(list(map(str,args)),cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
# Capture imports a complete SES. Clear the old copper to avoid retaining
# obsolete tracks when the resumed router has ripped up and replaced them.
sys.path.insert(0,str(out/'hardware/shield/scripts'))
from kicad_runtime import application
app=application()
import pcbnew as p
b=p.LoadBoard(str(h/'gemilaimate-compact.kicad_pcb'))
for item in list(b.GetTracks()):
    if not item.IsLocked():b.Remove(item);item.thisown=False
for z in list(b.Zones()):
    if not z.GetIsRuleArea():b.Remove(z);z.thisown=False
p.SaveBoard(str(h/'gemilaimate-compact.kicad_pcb'),b)
args=['java','-Xmx3g','-jar',os.environ.get('FREEROUTING_JAR','/home/ubuntu/codex-builds/tools/freerouting-2.5.0.jar'),
      '-de',h/'reports/unrouted.dsn',src/rel/'reports/trial.ses','-do',h/'reports/trial.ses',
      '--router.autorouter.max_passes=200','--router.optimizer.enabled=false','--router.fanout.enabled=false',
      '--router.neck_width_um=200','--router.automatic_neckdown=false',
      '--router.clearance_tolerance_um=2','--router.layers.routable=true,true',
      '--gui.enabled=false','--usage_and_diagnostic_data.disable_analytics=true']
if 'v19' in a.mode:args+=['--router.autorouter.algorithm=freerouting-router-v19']
if 'ripup' in a.mode:args+=['--router.scoring.start_ripup_costs=500','--router.scoring.via_costs=10']
result=dict(source=str(src),mode=a.mode,hardware_tested=False,manufacturing_release=False)
try:
    with (out/'router.log').open('w') as f:
        subprocess.run(list(map(str,args)),cwd=out,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
    text=(out/'router.log').read_text();stats=re.findall(r'final score: .*?\((\d+) unrouted and (\d+) violations\)',text)
    if stats:result['router_unrouted'],result['router_violations']=map(int,stats[-1])
    run(['python3',h/'scripts/capture_route.py',h/'reports/trial.ses'])
    run(['python3',h/'scripts/import_route.py'])
    run(['kicad-cli','pcb','drc','--format','json','--schematic-parity','--output',out/'candidate-drc.json',h/'gemilaimate-compact.kicad_pcb'])
    d=json.loads((out/'candidate-drc.json').read_text())
    result.update(drc_violations=len(d['violations']),unconnected=len(d['unconnected_items']),schematic_parity=len(d['schematic_parity']))
except Exception as exc:result['error']=str(exc)
result['seconds']=round(time.time()-started,1)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
