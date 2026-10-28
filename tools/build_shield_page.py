#!/usr/bin/env python3
"""Generate the shield fit template and standalone assembly/pinout page."""
from pathlib import Path
import json,html,base64,argparse,sys
R=Path(__file__).resolve().parents[1];H=R/'hardware/shield'
def build():
 d=json.loads((H/'design.json').read_text());esc=html.escape
 colors={'J2':'#c9e6f0','J3':'#d1e7f4','J7':'#e6d5ee','U1':'#d8dedb','U2':'#dce3e5'}
 svg=['<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="110mm" viewBox="0 0 120 110">',
 '<rect width="120" height="110" fill="white"/>',
 '<g font-family="Arial,sans-serif" fill="#183132">',
 '<text x="7" y="4" font-size="2.6">GemilaiMate shield v0.2 - 90 x 75 mm</text>',
 '<text x="7" y="8" font-size="1.7">PRINT 100% - NOMINAL CLONE GEOMETRY - Rico-X</text>',
 '<g transform="translate(15,12)"><rect width="90" height="75" fill="#f6f9f3" stroke="#1d4b40" stroke-width=".2"/>']
 for c in d['parts']:
  a,b,e,f=c['rect'];ref=c['ref'];smd=ref.startswith(('R','C')) or ref=='U3'
  svg.append(f'<rect data-ref="{ref}" x="{a}" y="{b}" width="{e-a}" height="{f-b}" fill="{colors.get(ref,"#f0f2e8")}" stroke="#65776e" stroke-width=".12"/>')
  if not smd:svg.append(f'<text x="{(a+e)/2}" y="{(b+f)/2}" text-anchor="middle" font-size="1.4">{ref}</text>')
  for pin in c.get('physical_pads',c['pins']):
   svg.append(f'<circle cx="{pin["x"]}" cy="{pin["y"]}" r=".5" fill="white" stroke="{"#ba3a20" if pin["number"]=="1" else "#3f4b44"}" stroke-width=".15"/>')
 for x,y in d['mounts_mm']:
  svg.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="white" stroke="#1d4b40" stroke-width=".18"/>')
 a,b,e,f=d['rf_keepout'];svg.append(f'<rect x="{a}" y="{b}" width="{e-a}" height="{f-b}" fill="none" stroke="#238d89" stroke-dasharray="1,.7" stroke-width=".18"/>')
 svg+=['</g><text x="15" y="92" font-size="1.9">1:1 fit template. Red ring: pin 1. Module geometry must be checked.</text>',
 '<path d="M10 98v4 M10 100h100 M110 98v4" stroke="#183132" stroke-width=".2" fill="none"/>',
 '<text x="60" y="105" text-anchor="middle" font-size="2">100 mm calibration line</text></g></svg>']
 svg=''.join(svg)
 rows=[]
 for c in d['parts']:
  if not c['ref'].startswith('J'):continue
  lines=''.join(f'<tr><td>{p["number"]}</td><td>{esc(p["name"])}</td><td>{esc(p["net"] or "NC - не подключать")}</td></tr>' for p in c['pins'])
  rows.append(f'<section id="{c["ref"]}"><h3>{c["ref"]} · {esc(c["value"])}</h3><table><tr><th>Контакт</th><th>Вывод модуля</th><th>Цепь</th></tr>{lines}</table></section>')
 def img(name):
  p=H/'previews'/name
  if not p.exists():return '<p>Рендер пока не экспортирован.</p>'
  return '<img alt="Номинальная сборка shield" src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'">'
 page=(R/'tools/shield_template.html').read_text()
 page=page.replace('%%FRONT%%',img('assembled-3d-front.png')).replace('%%TOP%%',img('assembled-3d-top.png')).replace('%%FIT%%',svg).replace('%%TABLES%%',''.join(rows))
 return svg,page
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
 svg,page=build()
 outputs={H/'mounting-template-1to1.svg':svg,R/'docs/shield.html':page}
 for path,text in outputs.items():
  if a.check:
   if not path.exists() or path.read_text()!=text:sys.exit(str(path)+' is stale')
  else:path.write_text(text)
 print('PASS shield page and 1:1 SVG match current geometry' if a.check else 'Shield page and 1:1 SVG written')
if __name__=='__main__':main()
