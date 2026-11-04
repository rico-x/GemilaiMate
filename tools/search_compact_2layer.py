#!/usr/bin/env python3
"""Bounded, isolated layout/routing experiments. Run only on the build host.

Never writes back to the source project. Each trial contains its exact input,
router log, candidate PCB and fresh KiCad DRC, including failed trials.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

SOURCE = Path(__file__).resolve().parents[1]
REL = Path('hardware/shield-compact')


def trial(root, size, mode):
    w, h = size
    name = f'{w:g}x{h:g}-{mode}'
    dest = root / name
    if (dest / 'result.json').exists():
        return json.loads((dest / 'result.json').read_text())
    dest.mkdir(parents=True, exist_ok=True)
    for rel in [REL, Path('hardware/shield/scripts'), Path('tools')]:
        shutil.copytree(SOURCE / rel, dest / rel, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', 'previews', 'manufacturing'))
    carrier = dest / 'hardware/carrier'
    carrier.mkdir(parents=True, exist_ok=True)
    shutil.copy(SOURCE / 'hardware/carrier/gemilaimate-carrier.kicad_pro', carrier)
    board = dest / REL
    config = json.loads((board / 'layout-config.json').read_text())
    config['size_mm'] = [w, h]
    config['native_usb_links']='usb-links' in mode
    if 'clear25' in mode:
        config['signal_clearance_mm']=.25
    config['mounts_mm'] = [[3, 3], [w-3, 3], [17, h-2.5], [w-3, h-3]]
    (board / 'layout-config.json').write_text(json.dumps(config, indent=2)+'\n')
    placement = json.loads((board / 'placement.json').read_text())
    placement['J_USB']['y'] = h-config['usb_edge_offset_mm']
    if 'central-ssr' in mode:
        placement['U_SSR']=dict(x=41,y=12.5,rotation=0)
        placement['C_SSR']=dict(x=49,y=10.5,rotation=0)
    if 'left-usb' in mode:
        updates={'J_USB':(3.65,26,-90),'U_ESD':(11.3,24,90),'J_SCALE':(6.5,34.5,0),
                 'F_USB':(11.5,37,90),'R_CC1':(12,29,180),'R_CC2':(12,32,180),'SW_RESET':(7,51,0)}
        for ref,(x,y,rotation) in updates.items():
            placement[ref]=dict(x=x,y=y,rotation=rotation)
    # Retain reviewed positions, expanding only edge banks by the small delta.
    for ref, item in placement.items():
        if ref == 'J_USB':
            continue
        if ref=='U1':
            continue
        if item['x'] >= 60:
            item['x'] += w-75
        else:
            item['x'] *= w/75
        if item['y'] >= 50:
            item['y'] += h-60
        else:
            item['y'] *= h/60
    (board / 'placement.json').write_text(json.dumps(placement, indent=2)+'\n')
    log = (dest / 'build.log').open('w')
    def run(args, timeout=180):
        subprocess.run(list(map(str, args)), cwd=dest, stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=timeout)
    def py(name):
        run(['python3', board / 'scripts' / name])
    result = dict(name=name, size_mm=[w,h], mode=mode, hardware_tested=False,
                  manufacturing_release=False, source=str(SOURCE))
    started = time.time()
    try:
        py('generate.py')
        if 'opt' in mode:
            seed=int(re.search(r'opt(\d+)',mode)[1])
            run(['python3',board/'scripts/optimize_placement.py','--seed',seed,'--iterations','200000',*(['--lock','U_SSR,C_SSR'] if 'central-ssr' in mode else [])],timeout=300)
            py('generate.py')
        py('make_schematic.py')
        run(['kicad-cli','sch','export','netlist','-o',board/'gemilaimate-compact.net',board/'gemilaimate-compact.kicad_sch'])
        py('prepare_route.py')
        run(['kicad-cli','pcb','drc','--format','json','--output',dest/'preflight.json',board/'gemilaimate-compact.kicad_pcb'])
        pre=json.loads((dest/'preflight.json').read_text())
        bad=pre['violations']
        result['preflight_violations']=len(bad)
        if bad:
            raise RuntimeError('Unrouted input violates fabrication geometry')
        args=['java','-Xmx3g','-jar',os.environ.get('FREEROUTING_JAR','/home/ubuntu/codex-builds/tools/freerouting-2.5.0.jar'),
              '-de',board/'reports/unrouted.dsn','-do',board/'reports/trial.ses',
              '--router.autorouter.max_passes=200','--router.optimizer.enabled=false',
              '--router.neck_width_um=200','--router.automatic_neckdown=false','--router.clearance_tolerance_um=2','--router.layers.routable=true,true',
              '--gui.enabled=false','--usage_and_diagnostic_data.disable_analytics=true']
        if 'v19' in mode:
            args+=['--router.autorouter.algorithm=freerouting-router-v19']
        if 'plane-gnd' in mode:
            args+=['--router.autorouter.ignore_net_classes=gnd']
        if 'no-fanout' in mode:
            args+=['--router.fanout.enabled=false']
        elif mode.startswith('low-via-cost'):
            args+=['--router.scoring.via_costs=5','--router.scoring.start_ripup_costs=200']
        elif mode.startswith('high-ripup'):
            args+=['--router.scoring.start_ripup_costs=500','--router.scoring.via_costs=20']
        with (dest/'router.log').open('w') as f:
            subprocess.run(list(map(str,args)),cwd=dest,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
        router_log=(dest/'router.log').read_text()
        stats=re.findall(r'final score: .*?\((\d+) unrouted and (\d+) violations\)',router_log)
        if stats:
            result['router_unrouted'],result['router_violations']=map(int,stats[-1])
        run(['python3',board/'scripts/capture_route.py',board/'reports/trial.ses'])
        py('import_route.py')
        run(['kicad-cli','pcb','drc','--format','json','--schematic-parity','--output',dest/'candidate-drc.json',board/'gemilaimate-compact.kicad_pcb'])
        drc=json.loads((dest/'candidate-drc.json').read_text())
        result.update(drc_violations=len(drc['violations']),unconnected=len(drc['unconnected_items']),
                      schematic_parity=len(drc['schematic_parity']))
    except Exception as exc:
        result['error']=str(exc)
    result['seconds']=round(time.time()-started,1)
    (dest/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--size',default='75x60')
    ap.add_argument('--modes',default='normal,no-fanout,low-via-cost,high-ripup')
    ap.add_argument('--workers',default=4,type=int)
    a=ap.parse_args()
    size=list(map(float,a.size.split('x')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        jobs=[pool.submit(trial,a.output.resolve(),size,m) for m in a.modes.split(',')]
        for job in concurrent.futures.as_completed(jobs):
            job.result()


if __name__=='__main__':
    main()
