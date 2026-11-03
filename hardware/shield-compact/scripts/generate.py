#!/usr/bin/env python3
"""Generate the compact KiCad PCB and circuit data. Execute on the KiCad build host.

Placement is nominal until real breakout modules are measured. Routes/CAM are
separate stages and no fabrication readiness is implied by generation.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application, seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-generate-0.1.0')
from circuit import SPEC, HERE, REV, WROOM_GPIO

for folder in ['GemilaiMateCompact.pretty','GemilaiMateCompact.3dshapes','previews','manufacturing','reports']:
    (HERE/folder).mkdir(parents=True, exist_ok=True)
B=p.BOARD()
B.SetCopperLayerCount(4)
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
names=sorted({n for c in SPEC['parts'] for n in c['nets'].values() if n})
nets={}
for name in names:
    net=p.NETINFO_ITEM(B,name)
    B.Add(net);nets[name]=net
title=B.GetTitleBlock()
title.SetTitle('GemilaiMate Compact Shield - Rico-X')
title.SetRevision(REV['revision']);title.SetDate(REV['date'])
title.SetComment(0,'PROTOTYPE / NOT HARDWARE VALIDATED')
title.SetComment(1,'Native USB / GM Pro LEGO ID=3 / 16MB physical, 8MB partition map')
title.SetComment(2,'github.com/Rico-X/GemilaiMate - no mains on PCB')
B.SetTitleBlock(title)


def line(fp,a,b,layer=p.F_Fab,width=.1):
    item=p.PCB_SHAPE(fp if fp else B)
    item.SetShape(p.SHAPE_T_SEGMENT);item.SetStart(V(*a));item.SetEnd(V(*b))
    item.SetLayer(layer);item.SetWidth(p.FromMM(width))
    (fp if fp else B).Add(item)


def rect(fp,box,layer=p.F_Fab,width=.1):
    a,b,c,d=box
    for x,y in [((a,b),(c,b)),((c,b),(c,d)),((c,d),(a,d)),((a,d),(a,b))]:line(fp,x,y,layer,width)


def socket(part):
    fp=p.FOOTPRINT(B)
    fp.SetReference(part['ref']);fp.SetValue(part['value'])
    fp.SetAttributes(p.FP_THROUGH_HOLE)
    name=part['footprint'].split(':',1)[1]
    fp.SetFPID(p.LIB_ID('GemilaiMateCompact',name))
    if part['ref']=='U_LEVEL':
        fp.SetAttributes(p.FP_SMD)
        for num,x,y in [(1,-1.9,-.975),(2,-1.9,-.325),(3,-1.9,.325),(4,-1.9,.975),
                        (5,1.9,.975),(6,1.9,.325),(7,1.9,-.325),(8,1.9,-.975)]:
            a=p.PAD(fp);a.SetNumber(str(num));a.SetPosition(V(x,y));a.SetAttribute(p.PAD_ATTRIB_SMD)
            a.SetShape(p.PAD_SHAPE_ROUNDRECT);a.SetSize(V(1.1,.4));a.SetRoundRectRadiusRatio(.125);a.SetLayerSet(p.PAD.SMDMask());fp.Add(a)
        rect(fp,[-1.5,-1.5,1.5,1.5]);rect(fp,[-2.7,-1.75,2.7,1.75],p.F_CrtYd,.05)
        return fp
    n=10 if part['ref']=='J_ADS' else 6
    for i in range(n):
        pad=p.PAD(fp);pad.SetNumber(str(i+1));pad.SetPosition(V(i*2.54*(1 if n==10 else -1),0))
        pad.SetAttribute(p.PAD_ATTRIB_PTH);pad.SetShape(p.PAD_SHAPE_RECT if i==0 else p.PAD_SHAPE_CIRCLE)
        pad.SetSize(V(1.65,1.65));pad.SetDrillSize(V(.95,.95));pad.SetLayerSet(p.PAD.PTHMask())
        fp.Add(pad)
    # Only the low socket itself occupies a PCB courtyard. The daughterboard
    # envelope is checked at its actual assembly height, not as a flat keepout.
    box=[-1.27,-1.27,(n-1)*2.54+1.27,1.27] if n==10 else [-(n-1)*2.54-1.27,-1.27,1.27,1.27]
    rect(fp,box,p.F_CrtYd,.05);rect(fp,box,p.F_SilkS,.1)
    return fp


def save_local(fp,c):
    original=c['footprint']
    local_name=original.split(':',1)[1]
    fp.SetFPID(p.LIB_ID('GemilaiMateCompact',local_name))
    c['source_footprint']=original
    c['footprint']='GemilaiMateCompact:'+local_name
    plugin=p.PCB_IO_MGR.FindPlugin(p.PCB_IO_MGR.KICAD_SEXP)
    plugin.FootprintSave(str(HERE/'GemilaiMateCompact.pretty'),fp)


overrides=json.loads((HERE/'placement.json').read_text()) if (HERE/'placement.json').exists() and '--fresh' not in sys.argv else {}
for c in SPEC['parts']:
    c.update(overrides.get(c['ref'],{}))
    lib,name=c['footprint'].split(':',1)
    if lib=='GemilaiMateCompact':fp=socket(c)
    else:
        path=HERE/'GemilaiMateCompact.pretty'
        if not (path/(name+'.kicad_mod')).exists():path=Path('/usr/share/kicad/footprints')/(lib+'.pretty')
        fp=p.FootprintLoad(str(path),name)
        if not fp:raise RuntimeError('Missing footprint: '+c['footprint'])
    fp.SetReference(c['designator']);fp.SetValue(c['value'])
    for pad in fp.Pads():
        # Harness GND pins join both GND layers solidly: routing between connector
        # pins otherwise leaves F.Cu spokes on isolated islands (starved thermals).
        if (c['ref'] in ['J_EXT','J_FREE','J_SCALE'] or c['section']=='Connectors') and c['nets'].get(pad.GetNumber())=='GND':pad.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
        if c['ref']=='J_USB':pad.SetLocalClearance(p.FromMM(.15))
        if c['ref']=='U1' and pad.GetNumber()=='41':
            if pad.GetAttribute()==p.PAD_ATTRIB_PTH:
                pad.SetDrillSize(V(.3,.3));pad.SetSize(V(.65,.65))
            pad.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
    for drawing in fp.GraphicalItems():
        if drawing.GetLayer()==p.F_SilkS:drawing.SetLayer(p.F_Fab)
    save_local(fp,c)
    B.Add(fp)
    fp.SetPosition(V(c['x'],c['y']))
    if c['side']=='back':fp.Flip(fp.GetPosition(),False)
    fp.SetOrientationDegrees(c['rotation'])
    if c['dnp']:fp.SetDNP(True)
    fp.Value().SetVisible(False)
    fp.Reference().SetTextSize(V(.8,.8));fp.Reference().SetTextThickness(p.FromMM(.1))
    # Place compact designators explicitly later, after via placement.
    fp.Reference().SetPosition(V(c['x'],c['y']-2.3))
    fp.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    numbers={pa.GetNumber() for pa in fp.Pads() if pa.GetNumber()}
    assert numbers==set(c['nets']), (c['ref'],numbers,set(c['nets']))
    for pad in fp.Pads():
        nn=c['nets'].get(pad.GetNumber())
        if nn:pad.SetNet(nets[nn])

        if c['ref']=='U1' and pad.GetNumber()=='41' and pad.GetAttribute()==p.PAD_ATTRIB_PTH:
            pad.SetDrillSize(V(.3,.3));pad.SetSize(V(.65,.65))
        if c['ref']=='U1' and pad.GetNumber()=='41':
            pad.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
    # Unused module-side GPIO35-37 are genuinely NC and have no escape traces.
    c['pins']=[]
    for number in sorted(numbers,key=lambda n:(not n.isdigit(),int(n) if n.isdigit() else n)):
        pads=[pa for pa in fp.Pads() if pa.GetNumber()==number]
        pa=pads[0];pos=pa.GetPosition()
        c['pins'].append(dict(number=number,name=c['names'].get(number,number),net=c['nets'][number],
                              type=c['pin_types'].get(number,'passive'),x=p.ToMM(pos.x),y=p.ToMM(pos.y)))
    c['physical_pads']=[dict(number=pa.GetNumber(),x=p.ToMM(pa.GetPosition().x),y=p.ToMM(pa.GetPosition().y),
                             net=c['nets'].get(pa.GetNumber()),smd=pa.GetAttribute()==p.PAD_ATTRIB_SMD)
                         for pa in fp.Pads() if pa.GetNumber()]

W,H=SPEC['size_mm']
rect(None,[0,0,W,H],p.Edge_Cuts,.05)
for index,(x,y) in enumerate(SPEC['mounts_mm'],1):
    fp=p.FOOTPRINT(B);fp.SetPosition(V(x,y));fp.SetReference('H'+str(index));fp.SetValue('M2 NYLON')
    fp.SetAttributes(p.FP_BOARD_ONLY | p.FP_EXCLUDE_FROM_POS_FILES | p.FP_EXCLUDE_FROM_BOM)
    pa=p.PAD(fp);pa.SetNumber('');pa.SetPosition(V(x,y));pa.SetAttribute(p.PAD_ATTRIB_NPTH)
    pa.SetShape(p.PAD_SHAPE_CIRCLE);pa.SetSize(V(2.2,2.2));pa.SetDrillSize(V(2.2,2.2));pa.SetLocalClearance(p.FromMM(.3))
    pa.SetLayerSet(p.LSET.AllCuMask());fp.Add(pa)
    fp.Reference().SetVisible(False);fp.Value().SetVisible(False);B.Add(fp)

for text,x,y,size in [('GemilaiMate COMPACT',33,48.8,.8),('Rico-X  /  v'+REV['revision'],46,1.3,.7),
                      ('NO MAINS',30,44.5,.65),('USB',7.5,39.5,.7)]:
    t=p.PCB_TEXT(B);t.SetText(text);t.SetPosition(V(x,y));t.SetTextSize(V(size,size))
    t.SetTextThickness(p.FromMM(.1));t.SetLayer(p.F_SilkS);B.Add(t)
t=p.PCB_TEXT(B);t.SetText('github.com/Rico-X/GemilaiMate');t.SetPosition(V(34,47.7))
t.SetTextSize(V(.85,.85));t.SetTextThickness(p.FromMM(.12));t.SetLayer(p.B_SilkS);t.SetMirrored(True);B.Add(t)

# Standard footprint includes the antenna rule area. All the antenna is beyond
# the PCB edge. Document its actual overhang rather than claiming a 65x50 assembly.
SPEC['nominal_assembly_bounds_mm']=[0,-7.15,65,50.335]
SPEC['module_sockets']={
 'J_ADS':dict(body_rect_mm=[2.46,22.26,30.46,39.3],socket_height_mm=8.5,male_header_height_mm=2.54,module_underside_mm=11.04,module_thickness_mm=1.6),
 'J_TC':dict(body_rect_mm=[39.99,21.97,60.31,44.83],socket_height_mm=8.5,male_header_height_mm=2.54,module_underside_mm=11.04,module_thickness_mm=1.6)}
SPEC['parts_count']=len(SPEC['parts'])
(HERE/'design.json').write_text(json.dumps(SPEC,ensure_ascii=False,indent=2)+'\n')
(HERE/'circuit.json').write_text(json.dumps(SPEC,ensure_ascii=False,indent=2)+'\n')
with (HERE/'connections.csv').open('w') as f:
    w=csv.writer(f,lineterminator="\n");w.writerow(['Reference','Value','Pin','Pin name','Net','x_mm','y_mm'])
    for c in SPEC['parts']:
        for pa in c['pins']:w.writerow([c['ref'],c['value'],pa['number'],pa['name'],pa['net'] or 'NC',pa['x'],pa['y']])

# Keep genuine power outputs in ERC. Flags mark power delivered through passive
# connector/fuse/diode chains; flags do not waive component pin errors.
SPEC['power_flags']=['GND','EXT_IN','USB_VBUS','USB_FUSED','+5V_EXT','+5V_CORE']
(HERE/'design.json').write_text(json.dumps(SPEC,ensure_ascii=False,indent=2)+'\n')
pro=json.loads((ROOT/'hardware/carrier/gemilaimate-carrier.kicad_pro').read_text())
ds=pro['board']['design_settings']
# Budget-fab margins (typical cheap 4-layer process plus reserve): edge, hole and
# annular clearances and legible silkscreen are enforced by DRC, not by review.
ds['rules'].update(min_clearance=.15,min_track_width=.2,min_via_diameter=.7,min_via_drill=.35,
                   min_through_hole_diameter=.3,min_copper_edge_clearance=.4,min_hole_clearance=.3,
                   min_hole_to_hole=.5,min_via_annular_width=.15,min_text_height=1.0,min_text_thickness=.15)
pro['meta']['filename']='gemilaimate-compact.kicad_pro'
pro['board']['design_settings']['drc_exclusions']=[]
pro['net_settings']['classes'][0].update(clearance=.2,track_width=.35,via_diameter=.7,via_drill=.35)
(HERE/'gemilaimate-compact.kicad_pro').write_text(json.dumps(pro,indent=2)+'\n')
(HERE/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "GemilaiMateCompact") (type "KiCad") (uri "${KIPRJMOD}/GemilaiMateCompact.pretty") (options "") (descr "Local compact board footprints")))\n')
(HERE/'gemilaimate-compact.kicad_dru').write_text("""(version 1)
(rule "USB4085 fixed pin pitch"
 (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.memberOfFootprint('J1') && B.memberOfFootprint('J1')")
 (constraint clearance (min 0.15mm)))
(rule "USB4085 fixed hole pitch"
 (condition "A.memberOfFootprint('J1') && B.memberOfFootprint('J1')")
 (constraint hole_to_hole (min 0.45mm)))
""")
p.SaveBoard(str(HERE/'gemilaimate-compact.kicad_pcb'),B)
print('Generated',SPEC['parts_count'],'components at',HERE,'- unrouted, not a manufacturing release')
