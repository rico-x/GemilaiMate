#!/usr/bin/env python3
"""Build this repository and export a current, self-contained USB firmware package."""
from pathlib import Path
import os,sys,subprocess,shutil,json,hashlib,zipfile,argparse
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--skip-web',action='store_true',help='Reuse an already built current Web UI');a=ap.parse_args()
    fw=ROOT/'firmware';dest=ROOT/'releases/firmware';dest.mkdir(parents=True,exist_ok=True)
    if not a.skip_web:subprocess.run(['bash','scripts/build_webui.sh'],cwd=fw,check=True)
    core=Path(os.environ.get('PLATFORMIO_CORE_DIR',str(Path.home()/'.platformio')))
    targets={}
    for target,size in [('controller',8),('display',16)]:
        subprocess.run([sys.executable,'-m','platformio','run','--project-dir',str(fw),'-e',target],check=True)
        build=fw/'.pio/build'/target;folder=dest/target;folder.mkdir(exist_ok=True)
        for name in ['firmware.bin','bootloader.bin','partitions.bin']:shutil.copy2(build/name,folder/name)
        boot=core/'packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin';shutil.copy2(boot,folder/'boot_app0.bin')
        parts=[('bootloader.bin',0,True),('partitions.bin',0x8000,True),('boot_app0.bin',0xe000,True),('firmware.bin',0x10000,False)]
        if target=='display':
            subprocess.run([sys.executable,'-m','platformio','run','--project-dir',str(fw),'-e','display','-t','buildfs'],check=True)
            shutil.copy2(build/'littlefs.bin',folder/'littlefs.bin');parts.append(('littlefs.bin',0xc90000,True))
        entries=[]
        for name,offset,initial in parts:
            data=(folder/name).read_bytes();entries.append(dict(path=target+'/'+name,offset=offset,size=len(data),sha256=hashlib.sha256(data).hexdigest(),initial_only=initial))
        info=subprocess.check_output([sys.executable,'-m','esptool','--chip','esp32s3','image_info',str(folder/'firmware.bin')],text=True)
        if info.count('(valid)')<2:raise RuntimeError('Invalid ESP32 image: '+target)
        (folder/'image-info.txt').write_text(info)
        targets[target]=dict(flash_mb=size,parts=entries,checksum_and_app_hash_valid=True)
    version='v'+ROOT.joinpath('VERSION').read_text().strip()
    source_sha=hashlib.sha256()
    for item in sorted(fw.rglob('*')):
        rel=item.relative_to(ROOT)
        if not item.is_file() or any(x in rel.parts for x in ['.pio','node_modules','dist','__pycache__','webassets']) or rel.as_posix()=='firmware/src/version.h':continue
        source_sha.update(str(rel).encode()+b'\0'+item.read_bytes()+b'\0')
    source_sha.update(ROOT.joinpath('VERSION').read_bytes())
    manifest=dict(project='GemilaiMate',version=version,repository='https://github.com/Rico-X/GemilaiMate',chip='esp32s3',hardware_upload_performed=False,hardware_assembled=False,targets=targets,
                  source_tree_sha256=source_sha.hexdigest(),
                  source_hash_scope='firmware source excluding installed dependencies, build outputs and generated version/Web assets; plus root VERSION',
                  generated_web_assets_sha256=hashlib.sha256(fw.joinpath('src/display/webassets/web_ui.bin').read_bytes()).hexdigest())
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    shutil.copy2(ROOT/'tools/flash.py',dest/'flash.py');shutil.copy2(ROOT/'docs/flashing.md',dest/'README.md')
    with zipfile.ZipFile(ROOT/'releases'/('GemilaiMate-'+version+'-firmware.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(dest.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(dest)))
    print('Built',version,'at',dest,'; no serial port accessed')
if __name__=='__main__':main()
