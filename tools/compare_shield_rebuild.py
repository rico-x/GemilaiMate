#!/usr/bin/env python3
"""After tools/rebuild_shield.py: the scripts must reproduce the committed shield.

Compares the working tree with git HEAD. A file may differ only in the KiCad build suffix and
generation timestamps (same normalization as tools/verify_cam.py). If the board file itself
differs, pcbnew compares it semantically: tracks, vias, pads, footprints and texts exactly, filled
zone area within 0.01 mm². Only then may the files derived from it differ: copper Gerbers, the
archive and the recorded hashes. Run with KiCad's Python when the board may differ.
"""
import io, json, subprocess, sys, tempfile, zipfile
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'tools'))
from verify_cam import normalize

PCB = 'hardware/shield/gemilaimate-shield.kicad_pcb'
HASHED_JSON = {'hardware/shield/board-stats.json', 'hardware/shield/silk-clearance.json',
               'hardware/shield/mechanical-check.json', 'hardware/shield/manufacturing/manifest.json'}


def git(*args):
    return subprocess.run(['git', *args], cwd=R, check=True, capture_output=True).stdout


def board_summary(path):
    import pcbnew as p
    mm = p.ToMM
    B = p.LoadBoard(str(path))
    xy = lambda v: (round(mm(v.x), 4), round(mm(v.y), 4))
    tracks = sorted((t.GetNetname(), p.LayerName(t.GetLayer()), round(mm(t.GetWidth()), 4), *sorted([xy(t.GetStart()), xy(t.GetEnd())]))
                    for t in B.GetTracks() if not isinstance(t, p.PCB_VIA))
    vias = sorted((v.GetNetname(), xy(v.GetPosition()), round(mm(v.GetWidth(p.F_Cu)), 4), round(mm(v.GetDrillValue()), 4))
                  for v in B.GetTracks() if isinstance(v, p.PCB_VIA))
    pads = sorted((f.GetReference(), pd.GetNumber(), pd.GetNetname(), xy(pd.GetPosition()), int(pd.GetShape()), xy(pd.GetSize()))
                  for f in B.GetFootprints() for pd in f.Pads())
    texts = sorted((p.LayerName(t.GetLayer()), t.GetText(), xy(t.GetPosition())) for t in B.GetDrawings() if isinstance(t, p.PCB_TEXT))
    texts += sorted((f.GetReference(), p.LayerName(g.GetLayer()), g.GetText(), xy(g.GetPosition()))
                    for f in B.GetFootprints() for g in f.GraphicalItems() if isinstance(g, p.PCB_TEXT))
    zones = {(z.GetNetname(), p.LayerName(l)): z.GetFilledPolysList(l).Area() / 1e12
             for z in B.Zones() if not z.GetIsRuleArea() for l in z.GetLayerSet().Seq()}
    return dict(tracks=tracks, vias=vias, pads=pads, texts=texts), zones


def same_archive(ref, new):
    """Archives match when they hold the same files with equivalent content."""
    a, b = zipfile.ZipFile(io.BytesIO(ref)), zipfile.ZipFile(io.BytesIO(new))
    return sorted(a.namelist()) == sorted(b.namelist()) and all(
        normalize(a.read(n).decode()) == normalize(b.read(n).decode()) for n in a.namelist())


def same_board(new):
    with tempfile.NamedTemporaryFile(suffix='.kicad_pcb') as ref:
        ref.write(git('show', f'HEAD:{PCB}')); ref.flush()
        a, za = board_summary(ref.name)
    b, zb = board_summary(new)
    problems = [f'{k}: {len(set(a[k]) ^ set(b[k]))} differing items ({len(a[k])} -> {len(b[k])})' for k in a if a[k] != b[k]]
    if za.keys() != zb.keys():
        problems.append(f'zones: {sorted(za)} -> {sorted(zb)}')
    problems += [f'zone {k} fill {za[k]:.3f} -> {zb[k]:.3f} mm²' for k in za if k in zb and abs(za[k] - zb[k]) > 0.01]
    return problems


def main():
    status = git('status', '--porcelain', '--untracked-files=all', '--', 'hardware', 'docs', 'tools').decode().splitlines()
    changed = [line[3:] for line in status]
    if not changed:
        print('PASS rebuild is byte-identical to HEAD')
        return
    fail, derived = [], []
    for path in changed:
        try:
            ref = git('show', f'HEAD:{path}')
        except subprocess.CalledProcessError:
            fail.append(f'{path}: not in HEAD'); continue
        new = (R / path).read_bytes() if (R / path).exists() else None
        if new is None:
            fail.append(f'{path}: deleted by the rebuild'); continue
        if path.endswith('.zip'):
            if same_archive(ref, new):
                continue
        else:
            try:
                if normalize(ref.decode()) == normalize(new.decode()):
                    continue
            except UnicodeDecodeError:
                pass
        derived.append(path)
    if PCB in derived:
        derived.remove(PCB)
        problems = same_board(R / PCB)
        fail += [f'{PCB}: {p}' for p in problems]
        print('PCB differs in bytes;', 'geometry identical' if not problems else 'geometry DIFFERS')
        for path in list(derived):
            if path.endswith(('_Cu.gtl', '_Cu.gbl')) or path.endswith('-prototype.zip'):
                derived.remove(path)
    # Hashes of the board or archive: these were compared above, the rest of the record must match.
    drop = lambda d: {k: v for k, v in d.items() if 'sha256' not in k}
    for path in [p for p in derived if p in HASHED_JSON]:
        if drop(json.loads(git('show', f'HEAD:{path}'))) == drop(json.loads((R / path).read_text())):
            derived.remove(path)
    fail += [f'{path}: differs from HEAD' for path in derived]
    if fail:
        sys.exit('FAIL the scripts do not reproduce the committed shield:\n  ' + '\n  '.join(fail))
    print(f'PASS rebuild reproduces HEAD ({len(changed)} files differ only in KiCad build, timestamps or zone-fill tessellation)')


if __name__ == '__main__':
    main()
