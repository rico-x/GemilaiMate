#!/usr/bin/env python3
"""Apply schematic parity, native USB and plane constraints on the build host."""
import gc
gc.disable()  # KiCad 10 SWIG ownership on the build host Python 3.14
import json,sys,math,sexpdata as s
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-preroute')
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
_data=json.loads((H/'design.json').read_text());aliases={c['designator']:c['ref'] for c in _data['parts']}
F={aliases.get(f.GetReference(),f.GetReference()):f for f in B.GetFootprints()}
V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
# Move only components in the reserved USB corridor, not the nominal sockets.
for ref,x,y,angle in [('R_USBM',3.5,16.33,180),('R_USBP',3.5,18.1,180),('U_ESD',7.475,33.5,90)]:
 f=F[ref];f.SetPosition(V(x,y));f.SetOrientationDegrees(angle)
placement=json.loads((H/'placement.json').read_text())
for r in ['R_USBM','R_USBP','U_ESD']:
 f=F[r];placement[r].update(x=p.ToMM(f.GetPosition().x),y=p.ToMM(f.GetPosition().y),rotation=f.GetOrientationDegrees())
(H/'placement.json').write_text(json.dumps(placement,indent=2)+'\n')

def children(node,key):return [x for x in node if isinstance(x,list) and str(x[0])==key]
def val(node,key):return children(node,key)[0][1]
d=s.loads((H/'gemilaimate-compact.net').read_text());pinmap={};nets={}
for n in children(d,'nets')[0][1:]:
 name=str(val(n,'name'));net=B.FindNet(name)
 if not net or net.GetNetCode()<0:
  net=p.NETINFO_ITEM(B,name);B.Add(net)
 nets[name]=net
 for nd in children(n,'node'):pinmap[(aliases.get(str(val(nd,'ref')),str(val(nd,'ref'))),str(val(nd,'pin')))]=(net,str(val(nd,'pinfunction')),str(val(nd,'pintype')))
paths=json.loads((H/'schematic-paths.json').read_text())
for ref,f in F.items():
 if ref in paths:f.SetPath(p.KIID_PATH(paths[ref]))
 for a in f.Pads():
  if (ref,a.GetNumber()) in pinmap:
   net,func,typ=pinmap[(ref,a.GetNumber())];a.SetNet(net);a.SetPinFunction(func);a.SetPinType(typ)
 # Silkscreen is placed after routing, including every assembly marking.
 f.Reference().SetLayer(p.B_Fab if f.IsFlipped() else p.F_Fab)
 for a in list(f.GraphicalItems()):
  if a.GetLayer() in [p.F_SilkS,p.B_SilkS]:a.SetLayer(p.B_Fab if f.IsFlipped() else p.F_Fab)
for x in list(B.GetDrawings()):
 if x.GetLayer() in [p.F_SilkS,p.B_SilkS]:x.SetLayer(p.B_Fab if x.IsMirrored() else p.F_Fab)

def route(net,points,layer=p.F_Cu,width=.28):
 for a,b in zip(points,points[1:]):
  t=p.PCB_TRACK(B);t.SetStart(V(*a));t.SetEnd(V(*b));t.SetLayer(layer);t.SetWidth(p.FromMM(width));t.SetNet(nets[net]);t.SetLocked(True);B.Add(t)
def via(net,xy):
 t=p.PCB_VIA(B);t.SetPosition(V(*xy));t.SetWidth(p.FromMM(.7));t.SetDrill(p.FromMM(.35));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetNet(nets[net]);t.SetLocked(True);B.Add(t)
# 0.25/0.15 mm main pair, continuous In1.Cu reference. Short package/connector
# fanouts differ in spacing; don't present this as a field-solver certificate.
route('USB_DM_MCU',[(6.25,16.33),(4.325,16.33)])
route('USB_DP_MCU',[(6.25,17.6),(5.825,18.025),(4.4,18.025),(4.325,18.1)])
route('USB_DM',[(2.675,16.33),(1.2,17.805),(1.2,29.05),(4.5125,32.3625),(6.525,32.3625)])
route('USB_DP',[(2.675,18.1),(1.68,19.095),(1.68,28.8512),(3.6288,30.8),(8.425,30.8),(8.425,32.3625)])
route('USB_DM',[(6.525,34.6375),(6.27,34.8925),(6.27,38),(6.4,38.13),(6.4,38.4)])
via('USB_DM',(6.4,38.4))
route('USB_DM',[(6.4,38.4),(7.2,39.2),(7.9,39.2),(7.9,41.2),(7.05,42.55)],p.B_Cu)
route('USB_DP',[(8.425,34.6375),(8.81,35.0225),(8.81,38.8),(8.21,39.4),(7.05,39.4),(7.05,41.2),(7.9,42.55)])
route('USB_DM',[(6.525,32.3625),(6.525,34.6375)])
route('USB_DP',[(8.425,32.3625),(8.425,34.6375)])
# Ground return for the ESD array, next to its ground pad and layer transition.
route('GND',[(7.475,34.6375),(7.475,35.75)],width=.4);via('GND',(7.475,35.75))
# Budget fabs: copper 0.4 mm from the routed edge on every layer. The router adds
# its 0.2 mm clearance to this 0.2 mm keepout band.
for a,b,c,e in [(0,0,65,.2),(0,49.8,65,50),(0,0,.2,50),(64.8,0,65,50)]:
 z=p.ZONE(B);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
 z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);z.SetDoNotAllowZoneFills(False)
 z.SetLayerSet(p.LSET.AllCuMask());o=z.Outline();o.NewOutline()
 for x,y in [(a,b),(c,b),(c,e),(a,e)]:o.Append(int(p.FromMM(x)),int(p.FromMM(y)))
 B.Add(z)
# Reserve a full ground layer. The autorouter may use F.Cu, In2.Cu and B.Cu.
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
text=(H/'gemilaimate-compact.kicad_pcb').read_text()
stack='''(stackup
 (layer "F.SilkS" (type "Top Silk Screen"))
 (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "core") (thickness 1.06) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035))
 (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste"))
 (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "ENIG") (dielectric_constraints yes))'''
text=text.replace('(setup\n','(setup\n'+stack+'\n',1)
(H/'gemilaimate-compact.kicad_pcb').write_text(text)
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'))
p.ExportSpecctraDSN(B,str(H/'reports/unrouted.dsn'))
# Wider low-voltage distribution; pin neckdowns remain governed by the actual
# footprint and are independently checked by KiCad after SES import.
import re
dsn=H/'reports/unrouted.dsn';text=dsn.read_text();start=text.index('(class kicad_default ')
level=0
for index in range(start,len(text)):
    if text[index]=='(':level+=1
    if text[index]==')':level-=1
    if level==0:end=index+1;break
old=text[start:end];head,tail=old.split('(circuit',1)
for name in ['+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED']:
    head=re.sub(r'(?<!\S)'+re.escape(name)+r'(?=\s)', '',head)
power='(class power +3V3 +5V_CORE +5V_EXT EXT_IN USB_VBUS USB_FUSED (circuit (use_via "Via[0-3]_700:350_um")) (rule (width 350) (clearance 200)))'
dsn.write_text(text[:start]+head+'(circuit'+tail+'\n'+power+text[end:])
print('Prepared schematic parity, locked USB routes and nominal 4-layer stackup.')
