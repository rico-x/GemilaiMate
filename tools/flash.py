#!/usr/bin/env python3
"""Verify firmware and print a flash plan; serial access only with explicit --flash."""
import argparse,hashlib,importlib.metadata,json,shlex,subprocess,sys
from pathlib import Path

def main(argv=None, root=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target',choices=['controller','display'])
    ap.add_argument('--port',required=True)
    ap.add_argument('--package',type=Path,help='Firmware package directory containing manifest.json')
    ap.add_argument('--fresh',action='store_true',help='Initialize bootloader/partitions/OTA/app/filesystem. Does not erase NVS by itself.')
    ap.add_argument('--erase-all',action='store_true',help='Erase ALL flash before a --fresh installation, including NVS, settings and profiles.')
    ap.add_argument('--flash',action='store_true',help='Actually execute the printed plan. Without it, no serial device is accessed.')
    a=ap.parse_args(argv)
    if a.erase_all and not a.fresh:ap.error('--erase-all requires --fresh')
    root=Path(root) if root else (a.package if a.package else Path(__file__).resolve().parent)
    m=json.loads((root/'manifest.json').read_text());target=m['targets'][a.target]
    parts=target['parts'] if a.fresh else [x for x in target['parts'] if not x['initial_only']]
    prefix=[sys.executable,'-m','esptool','--chip','esp32s3','--port',a.port,'--baud','460800']
    write=prefix+['write_flash','--flash_mode','keep','--flash_freq','keep','--flash_size',str(target['flash_mb'])+'MB']
    # Validate every selected part before even planning an erase.
    for x in parts:
        p=root/x['path'];data=p.read_bytes()
        if len(data)!=x['size'] or hashlib.sha256(data).hexdigest()!=x['sha256']:raise SystemExit('Size/hash mismatch: '+str(p))
        write.extend([hex(x['offset']),str(p)])
    commands=([prefix+['erase_flash']] if a.erase_all else [])+[write]
    if a.erase_all:print('ERASE ALL: NVS, Wi-Fi/BLE settings, profiles and history will be destroyed if --flash is added.')
    for cmd in commands:print(shlex.join(cmd))
    if not a.flash:
        print('CHECK ONLY. Add --flash to execute. No serial device has been accessed.')
        return 0
    try:version=importlib.metadata.version('esptool')
    except importlib.metadata.PackageNotFoundError:raise SystemExit('Install esptool==4.9.0 in this Python environment first.')
    if version!='4.9.0':raise SystemExit('This package is validated with esptool==4.9.0; select the matching Python environment.')
    for cmd in commands:subprocess.check_call(cmd)
    return 0
if __name__=='__main__':raise SystemExit(main())
