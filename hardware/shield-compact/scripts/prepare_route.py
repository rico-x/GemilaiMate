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
for ref,x,y,angle in [('R_USBM',3.2,15.7,180),('R_USBP',3.2,18.6,180),('U_ESD',7.475,33.5,90)]:
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

# The only pre-routed copper joins the duplicated USB-C data contacts inside the
# USB4085 field (D+ A6-B6 on F.Cu, D- A7-B7 on B.Cu), taken from the actual pad
# positions; everything else is autorouted. USB-FS is not impedance-controlled.
def pad_xy(ref,number):
 q=next(a for a in F[ref].Pads() if a.GetNumber()==number).GetPosition();return q
for net,a,b,layer in [('USB_DP','A6','B6',p.F_Cu),('USB_DM','A7','B7',p.B_Cu)]:
 t=p.PCB_TRACK(B);t.SetStart(pad_xy('J_USB',a));t.SetEnd(pad_xy('J_USB',b));t.SetLayer(layer);t.SetWidth(p.FromMM(.3));t.SetNet(nets[net]);t.SetLocked(True);B.Add(t)
# Budget fabs: copper 0.5 mm from the routed edge on every layer. The router adds
# its 0.30 mm clearance to this 0.25 mm keepout band.
W,board_h=_data['size_mm']
for a,b,c,e in [(0,0,W,.25),(0,board_h-.25,W,board_h),(0,0,.25,board_h),(W-.25,0,W,board_h)]:
 z=p.ZONE(B);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
 z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);z.SetDoNotAllowZoneFills(False)
 z.SetLayerSet(p.LSET.AllCuMask());o=z.Outline();o.NewOutline()
 for x,y in [(a,b),(c,b),(c,e),(a,e)]:o.Append(int(p.FromMM(x)),int(p.FromMM(y)))
 B.Add(z)
# Copper-free disc under each M2 head/standoff on every layer. The polygon is
# circumscribed around the keepout circle; the router sees it as a keepout.
radius=_data['mount_keepout_radius_mm']/math.cos(math.pi/32)
for x,y in _data['mounts_mm']:
 z=p.ZONE(B);z.SetIsRuleArea(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True)
 z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);z.SetDoNotAllowZoneFills(True)
 z.SetLayerSet(p.LSET.AllCuMask());o=z.Outline();o.NewOutline()
 for i in range(32):
  angle=2*math.pi*(i+.5)/32;o.Append(int(p.FromMM(x+radius*math.cos(angle))),int(p.FromMM(y+radius*math.sin(angle))))
 B.Add(z)
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
# Net classes. In1 is reserved for ground with Specctra use_layer: every other
# class routes on F.Cu/In2.Cu/B.Cu, GND may also use In1, so the router drops
# ground vias into In1 and joins them there; the In1 pour fills the rest.
# A plane exported instead is treated by Freerouting 2.5 as a refillable pour
# ("configured for plane routing"): the net is skipped and SMD lands stay open.
import re
dsn=H/'reports/unrouted.dsn';text=dsn.read_text();start=text.index('(class kicad_default ')
level=0
for index in range(start,len(text)):
    if text[index]=='(':level+=1
    if text[index]==')':level-=1
    if level==0:end=index+1;break
old=text[start:end];head,tail=old.split('(circuit',1)
for name in ['GND','+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED','USB_DP','USB_DM','USB_DP_MCU','USB_DM_MCU']:
    head=re.sub(r'(?<!\S)'+re.escape(name)+r'(?=\s)', '',head)
signal_layers='(use_layer F.Cu In2.Cu B.Cu)'
power='(class power +3V3 +5V_CORE +5V_EXT EXT_IN USB_VBUS USB_FUSED (circuit (use_via "Via[0-3]_800:400_um") '+signal_layers+') (rule (width 400) (clearance 300)))'
usb='(class usb USB_DP USB_DM USB_DP_MCU USB_DM_MCU (circuit (use_via "Via[0-3]_800:400_um") '+signal_layers+') (rule (width 300) (clearance 300)))'
gnd='(class gnd GND (circuit (use_via "Via[0-3]_800:400_um")) (rule (width 300) (clearance 300)))'
dsn.write_text(text[:start]+head+'(circuit '+signal_layers+tail+'\n'+power+'\n'+usb+'\n'+gnd+text[end:])
# Per-pin clearance class: USB4085 contacts keep 0.15 mm only to each other
# and 0.20 mm to fan-out copper.
(H/'reports/unrouted-native.dsn').write_text(dsn.read_text())
native=dsn.read_text().replace('(string_quote ")','',1)
# Brackets are legal DSN identifier characters, while sexpdata treats them as
# list delimiters. Protect them while changing the tree, then restore verbatim.
tree=s.loads(native.replace('[','__GM_LB__').replace(']','__GM_RB__'))
network=children(tree,'network')[0]
# KiCad now exports the project classes too. Keep the explicit DSN classes
# below as the single assignment for each rail/USB net.
network[:]=[x for x in network if not (isinstance(x,list) and str(x[0])=='class' and str(x[1]) in ['Power','USB'])]
structure=children(tree,'structure')[0]
rule=children(structure,'rule')[0]
rule.append([s.Symbol('clearance'),150,[s.Symbol('type'),'fine_fine']])
for name in ['fine_default','fine_wire','fine_smd','fine_pin','fine_via','fine_powerwire','fine_usbwire']:
 rule.append([s.Symbol('clearance'),200,[s.Symbol('type'),name]])
for peer in ['powerwire','default','wire','smd','pin','via','usbwire']:
 rule.append([s.Symbol('clearance'),300,[s.Symbol('type'),'powerwire_'+peer]])
rule.append([s.Symbol('clearance'),300,[s.Symbol('type'),'usbwire_usbwire']])
for netclass in children(children(tree,'network')[0],'class'):
 name=str(netclass[1]);cls={'power':'powerwire','usb':'usbwire'}.get(name,'default')
 netclass.append([s.Symbol('clearance_class'),cls])
fine_refs={c['designator'] for c in _data['parts'] if c['ref']=='J_USB'}
for component in children(tree,'placement')[0][1:]:
 if not isinstance(component,list):continue
 for place in children(component,'place'):
  ref=str(place[1]);cls='fine' if ref in fine_refs else None
  if cls:
   part=next(c for c in _data['parts'] if c['designator']==ref)
   for number in part['nets']:place.append([s.Symbol('pin'),number,[s.Symbol('clearance_class'),cls]])
dsn.write_text(s.dumps(tree,str_as='string').replace('__GM_LB__','[').replace('__GM_RB__',']')+'\n')
print('Prepared schematic parity, keepouts, In1 reserved for GND and four-layer stackup.')
