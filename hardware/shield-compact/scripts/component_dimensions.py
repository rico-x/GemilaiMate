#!/usr/bin/env python3
"""Export a traceable mechanical inventory for every board component.

Run with KiCad's Python on the build host after generate.py. Manufacturer body
sizes are separated from module-board outlines, which remain clone-dependent.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
H = Path(__file__).resolve().parents[1]
D = json.loads((H / 'design.json').read_text())
OUT = H / 'reports'
OUT.mkdir(exist_ok=True)

# Dimensions are body L x W x H in mm. For passives the selected footprints
# follow the package code; individual makers may use a smaller body within it.
profiles = {
    'ESP32-S3-WROOM-1': ('25.5 x 18.0 x 3.1', 'Espressif module drawing', 'manufacturer'),
    'TYPE-C-31-M-12': ('8.94 x 7.35 x 3.26 max (3.16 nominal)', 'HRO product page and manufacturer drawing', 'manufacturer'),
    'R_0805_2012Metric': ('2.0 x 1.25 x 0.5', 'Yageo RC0805 drawing; resistor class', 'manufacturer'),
    'C_0805_2012Metric': ('2.0 x 1.25 x 1.35', 'Murata GRM21 max body; capacitor class', 'manufacturer'),
    'C_1206_3216Metric': ('3.2 x 1.6 x 1.8', 'Murata GRM31 max body; capacitor class', 'manufacturer'),
    'Fuse_1206_3216Metric': ('3.4 x 1.8 x 0.85', 'Littelfuse 1206L package drawing', 'manufacturer'),
    'D_SMA': ('4.6 x 2.92 x 2.62', 'SMA package outline; verify approved source alternate', 'package nominal'),
    'SOT-23-6': ('2.9 x 1.6 x 1.1', 'ST USBLC6 package drawing', 'manufacturer'),
    'SOT-23-5': ('2.9 x 1.3 x 1.1', 'TI DBV package outline', 'manufacturer'),
    'SOT-23': ('2.9 x 1.3 x 1.1', 'Diodes Inc./selected SOT-23 drawing', 'manufacturer'),
    'SOT-223-3_TabPin2': ('6.5 x 3.5 x 1.8', 'Diodes Inc. SOT-223 drawing', 'manufacturer'),
    'SOIC-14_3.9x8.7mm': ('8.65 x 3.9 x 1.75', 'TI D package drawing', 'manufacturer'),
    'SOIC-20W_7.5x12.8mm': ('12.8 x 7.5 x 2.65', 'NXP SO20 package drawing', 'manufacturer'),
    'SW_SPST_TL3342': ('5.2 x 5.2 x 3.5', 'E-Switch TL3342 product drawing', 'manufacturer'),
    'JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical': ('5.9 x 5.9 x 6.0', 'JST PH top-entry header drawing', 'manufacturer'),
    'JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical': ('7.9 x 5.9 x 6.0', 'JST PH top-entry header drawing', 'manufacturer'),
    'JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical': ('9.9 x 5.9 x 6.0', 'JST PH top-entry header drawing', 'manufacturer'),
    'JST_PH_B5B-PH-K_1x05_P2.00mm_Vertical': ('11.9 x 5.9 x 6.0', 'JST PH top-entry header drawing', 'manufacturer'),
    'JST_PH_B6B-PH-K_1x06_P2.00mm_Vertical': ('13.9 x 5.9 x 6.0', 'JST PH top-entry header drawing', 'manufacturer'),
    'JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical': ('7.0 x 5.5 x 9.8', 'JST XH top-entry header drawing', 'manufacturer'),
    'PinHeader_1x05_P2.54mm_Vertical': ('12.7 x 2.54 x 8.5', 'generic 2.54 mm header envelope', 'nominal'),
    'PinHeader_1x06_P2.54mm_Vertical': ('15.24 x 2.54 x 8.5', 'generic 2.54 mm header envelope', 'nominal'),
    'PinHeader_2x05_P2.54mm_Vertical': ('10.16 x 5.08 x 8.5', 'generic 2.54 mm header envelope', 'nominal'),
    'TestPoint_Pad_D1.0mm': ('1.0 x 1.0 x 0.0', 'PCB copper test point', 'board feature'),
}

def profile(c):
    fp = c.get('source_footprint', c['footprint']).split(':')[-1]
    mpn = c.get('mpn', '')
    for key, item in profiles.items():
        if fp == key or key in fp or key in mpn:
            return item
    if c['ref'] in ['J_ADS', 'J_TC', 'J_LEVEL']:
        m = D['module_sockets'][c['ref']]
        b = m['body_rect_mm']
        dims = f"{b[2]-b[0]:.2f} x {b[3]-b[1]:.2f} x varies"
        return dims, m.get('geometry_status', 'nominal breakout outline; actual clone not measured'), 'unverified module'
    if c['section'] == 'Connectors':
        return 'see courtyard / nominal mating stack', 'custom or generic connector; supplier alternate not fixed', 'nominal'
    return 'see KiCad footprint', 'no manufacturer body outline assigned', 'needs review'

rows=[]
for c in D['parts']:
    dims, source, status = profile(c)
    rows.append([c['designator'], c['ref'], c['value'], c.get('mpn',''), c.get('source_footprint',c['footprint']), dims, source, status, c.get('side','front'), int(c.get('dnp',False))])

with (OUT/'component-dimensions.csv').open('w', newline='') as f:
    w=csv.writer(f,lineterminator='\n')
    w.writerow(['Reference','Function_alias','Value','MPN_example','KiCad_footprint','Body_LxWxH_mm','Dimension_source_or_basis','Confidence','Side','DNP'])
    w.writerows(rows)

modules = [
    ['ADS1115 Blue', '28 x 17 x varies', 'typical clone outline; not tied to maker/MPN', 'unmeasured', '1x10 2.54 mm row; actual pin geometry and board thickness required'],
    ['MAX31855 breakout', '20.32 x 22.86 x varies', 'Adafruit reference outline; selected clone unverified', 'unmeasured', 'measure terminal, board edge, hole pattern, thickness and header location'],
    ['CJMCU-0102 TXS0102', '15.24 x 15.24 x varies', 'selected listing outline; 2 rows at 12.70 mm assumed', 'unmeasured', 'measure row spacing and pin orientation before soldering header strips'],
]
with (OUT/'component-dimensions.csv').open('a', newline='') as f:
    w=csv.writer(f,lineterminator='\n')
    for name,dims,source,status,note in modules:
        w.writerow([name,'external module','','', '',dims,source,status,'plug-in',note])

doc = '''# Component dimensions and mechanical fit\n\n'''
doc += f"PCB outline: **{D['size_mm'][0]} x {D['size_mm'][1]} mm**, {D['copper_layers']} copper layers. This report covers every fitted footprint and the three plug-in daughterboards.\n\n"
doc += '## Fit status\n\n'
doc += '- The component body sizes in the CSV come from manufacturer package drawings when a fixed MPN is selected; generic package envelopes are explicitly marked nominal. KiCad DRC checks the routed footprints and board-edge clearances.\n'
doc += '- The HRO USB-C body dimensions come from its manufacturer drawing. Its bundled 3D model is a nominal maximum envelope, not a detailed STEP; pad/anchor geometry follows the selected KiCad footprint and drawing.\n'
doc += '- The ADS1115, MAX31855 and CJMCU-0102 are breakout boards, not fixed bare components. Their clones have not been measured. Their nominal outlines are included in the CAD, but mechanical fit is **not confirmed** until the actual boards, pin rows, terminal, and headers are measured.\n'
doc += '- The Harwin M20 sockets provide an 8.5 mm socket body above the carrier PCB. The matching 2.54 mm header plastic gives a nominal daughterboard underside height of about 11.04 mm. Check the selected male headers and actual parts together before building. Optional expansion headers use standard 2.54 mm pitch for easier hand assembly.\n'
doc += '- RobotDyn and SSR remain off-board, separately mounted modules. Their footprints and 230 V conductors are intentionally not placed on this low-voltage shield.\n'
doc += f"- Overall height in the Gemilai case is not cleared: no case-envelope measurement exists. The {D['size_mm'][0]} x {D['size_mm'][1]} mm outline is a design choice, not proof it fits the machine.\n\n"
doc += '## PCB components\n\nSee [component-dimensions.csv](../hardware/shield-compact/reports/component-dimensions.csv) for all references, MPN examples, footprints, body envelopes, side, and confidence. Values describe component bodies, not the larger KiCad courtyard.\n\n'
doc += '## Before ordering\n\n1. Print [assembly-top.svg](../hardware/shield-compact/previews/assembly-top.svg) and [board-bottom.svg](../hardware/shield-compact/previews/board-bottom.svg) at 1:1.\n2. Measure the received ADS1115, MAX31855, and CJMCU boards including soldered headers, thermocouple terminal, and component overhangs. Confirm CJMCU row pitch and polarity.\n3. Place the real modules in the print and check clearances above and below the shield, cable exits, USB access, mounts, and machine-case envelope.\n4. Only then freeze mechanical dimensions for fabrication.\n'
(ROOT/'docs/component-dimensions.md').write_text(doc)
print(f"Wrote dimensions for {len(D['parts'])} PCB footprints and {len(modules)} unmeasured modules")
