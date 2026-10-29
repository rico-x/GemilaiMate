#!/usr/bin/env python3
"""Check the committed hardware files against fresh KiCad runs.

For carrier and shield: ERC and DRC (schematic parity, all severities) must be clean on the
saved design, and Gerber/Excellon exported now from the saved PCB must equal the committed CAM.
Only generation timestamps and the KiCad distribution build suffix may differ. For the shield
the archive must hold exactly the Gerber folder and the manifest hashes must match.
Needs only kicad-cli; used by CI in the KiCad container.
"""
import argparse, hashlib, json, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

R = Path(__file__).resolve().parents[1]
LAYERS = 'F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
STAMP = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}([+-]\d{2}:?\d{2}|Z)?')
BUILD = re.compile(r'(\d+\.\d+\.\d+)[-~+][\w.~+-]*')
MARKERS = re.compile(r'date|Date|Created|DRILL file|GenerationSoftware|"Version"|"kicad_version"|\(tool ')


def normalize(text):
    """Lines that name the KiCad build or a generation time are compared without them."""
    return [BUILD.sub(r'\1', STAMP.sub('<time>', line)) if MARKERS.search(line) else line for line in text.splitlines()]


def kicad(cli, *args):
    subprocess.run([cli, *map(str, args)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fresh_reports(cli, folder, name, tmp):
    kicad(cli, 'sch', 'erc', '--severity-all', '--format', 'json', '-o', tmp / f'{name}-erc.json', folder / f'{name}.kicad_sch')
    kicad(cli, 'pcb', 'drc', '--schematic-parity', '--severity-all', '--format', 'json', '-o', tmp / f'{name}-drc.json', folder / f'{name}.kicad_pcb')
    erc = json.loads((tmp / f'{name}-erc.json').read_text()); drc = json.loads((tmp / f'{name}-drc.json').read_text())
    counts = dict(erc=sum(len(s['violations']) for s in erc['sheets']),
                  **{k: len(drc[k]) for k in ['violations', 'unconnected_items', 'schematic_parity']})
    assert not any(counts.values()), f'{name}: fresh ERC/DRC is not clean: {counts}'
    return counts


def fresh_cam(cli, pcb, committed, tmp):
    out = tmp / (pcb.stem + '-cam'); out.mkdir()
    kicad(cli, 'pcb', 'export', 'gerbers', '--layers', LAYERS, '-o', f'{out}/', pcb)
    kicad(cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '-o', f'{out}/', pcb)
    fresh = {f.name: f.read_text() for f in out.iterdir()}
    assert sorted(fresh) == sorted(committed), f'{pcb.name}: CAM file set differs: {sorted(fresh)} / {sorted(committed)}'
    stale = [n for n in sorted(fresh) if normalize(fresh[n]) != normalize(committed[n])]
    assert not stale, f'{pcb.name}: committed CAM differs from a fresh export of the committed PCB: {stale}'
    return len(fresh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kicad-cli', default=shutil.which('kicad-cli'))
    a = ap.parse_args()
    if not a.kicad_cli:
        ap.error('Supply --kicad-cli')
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        carrier = R / 'hardware/carrier'
        fresh_reports(a.kicad_cli, carrier, 'gemilaimate-carrier', tmp)
        with zipfile.ZipFile(carrier / 'manufacturing/gerber-drill.zip') as z:
            n = fresh_cam(a.kicad_cli, carrier / 'gemilaimate-carrier.kicad_pcb', {i: z.read(i).decode() for i in z.namelist()}, tmp)
        print(f'PASS carrier: fresh ERC/DRC clean, {n} CAM files match the committed PCB')

        shield = R / 'hardware/shield'
        sys.path.insert(0, str(shield / 'scripts'))
        from revision import ARCHIVE
        m = shield / 'manufacturing'; pcb = shield / 'gemilaimate-shield.kicad_pcb'
        fresh_reports(a.kicad_cli, shield, 'gemilaimate-shield', tmp)
        gerber = {f.name: f.read_text() for f in (m / 'gerber').iterdir()}
        n = fresh_cam(a.kicad_cli, pcb, gerber, tmp)
        with zipfile.ZipFile(m / ARCHIVE) as z:
            assert sorted(z.namelist()) == sorted(gerber) and all(z.read(i).decode() == gerber[i] for i in gerber), f'{ARCHIVE} differs from manufacturing/gerber'
        manifest = json.loads((m / 'manifest.json').read_text())
        assert manifest['archive_sha256'] == hashlib.sha256((m / ARCHIVE).read_bytes()).hexdigest(), 'manifest archive hash is stale'
        assert manifest['pcb_sha256'] == hashlib.sha256(pcb.read_bytes()).hexdigest(), 'manifest PCB hash is stale'
        print(f'PASS shield: fresh ERC/DRC clean, {n} CAM files match the committed PCB, {ARCHIVE} and manifest consistent')


if __name__ == '__main__':
    main()
