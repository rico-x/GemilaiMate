#!/usr/bin/env python3
"""Maximise copper widths, bundle models and place collision-checked labels.
Execute with KiCad Python and Shapely on the remote build host.
"""
import gc;gc.disable()
import sys,json,math,shutil,hashlib,collections,re,itertools
from pathlib import Path
from shapely.geometry import LineString,Point,box as shape_box
from shapely.strtree import STRtree
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-final')
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'));D=json.loads((H/'design.json').read_text())
W,H_MM=D['size_mm']
parts={c['designator']:c for c in D['parts']};F={f.GetReference():f for f in B.GetFootprints()}
mm=p.ToMM;V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))
tracks=list(B.GetTracks());pads=[a for f in B.GetFootprints() for a in f.Pads()]

def rect(a):
 b=a.GetBoundingBox();return [mm(b.GetLeft()),mm(b.GetTop()),mm(b.GetRight()),mm(b.GetBottom())]
def polygon(t):
 if isinstance(t,p.PCB_VIA):return Point(mm(t.GetPosition().x),mm(t.GetPosition().y)).buffer(mm(t.GetWidth(p.F_Cu))/2)
 a,b=t.GetStart(),t.GetEnd();return LineString([(mm(a.x),mm(a.y)),(mm(b.x),mm(b.y))]).buffer(mm(t.GetWidth())/2)
objects=[dict(item=t,net=t.GetNetCode(),shape=polygon(t),layer=None if isinstance(t,p.PCB_VIA) else t.GetLayer()) for t in tracks]
objects +=[dict(item=a,net=a.GetNetCode(),shape=shape_box(*rect(a)),layer=a.GetLayer() if a.GetAttribute()==p.PAD_ATTRIB_SMD else None) for a in pads]
# A large annulus does not substitute for drill-to-copper clearance.
# Include every foreign drill independently so widening cannot reintroduce
# the 0.50 mm hole violations repaired during routing.
for pad in pads:
 if pad.GetAttribute()==p.PAD_ATTRIB_SMD:continue
 pos=pad.GetPosition();radius=max(mm(pad.GetDrillSize().x),mm(pad.GetDrillSize().y))/2
 objects.append(dict(item=pad,net=pad.GetNetCode(),shape=Point(mm(pos.x),mm(pos.y)).buffer(radius),layer=None,drill=True))
# M2 mounts are copper-free discs on every layer, not just their 2.2 mm drills.
keepout=D['mount_keepout_radius_mm']
objects +=[dict(item=None,net=-1,shape=Point(x,y).buffer(keepout,64),layer=None) for x,y in D['mounts_mm']]
power={'+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED'}
# The largest widening adds <=0.5 mm per side. A 2 mm query margin
# includes all objects that can limit a <=1.2 mm track at <=0.51 mm gap,
# even after their own widths increase; acceptance remains fresh KiCad DRC.
spatial=STRtree([o['shape'] for o in objects])
changed=0
for obj in objects[:len(tracks)]:
 t=obj['item']
 if isinstance(t,p.PCB_VIA) or t.IsLocked():continue
 a,b=t.GetStart(),t.GetEnd();line=LineString([(mm(a.x),mm(a.y)),(mm(b.x),mm(b.y))])
 limit=1.2 if t.GetNetname() in power else .8
 bounds=line.bounds;edge=min(bounds[0],bounds[1],W-bounds[2],H_MM-bounds[3]);limit=min(limit,2*(edge-.51))
 for object_index in spatial.query(line.buffer(2.0)):
  other=objects[int(object_index)]
  if other['net']==obj['net'] or other is obj or (other['layer'] is not None and other['layer']!=obj['layer']):continue
  # 0.01 mm extra geometric margin beyond the 0.30 mm signal and power rule;
  # widening never enters a mount keepout disc.
  distance=line.distance(other['shape'])
  foreign=other['item']
  if other.get('drill'):clear=.51
  elif foreign is None:clear=.02
  elif isinstance(foreign,p.PAD) and foreign.GetAttribute()==p.PAD_ATTRIB_NPTH:clear=.51
  elif isinstance(foreign,p.PCB_VIA) or t.GetNetname() in power or foreign.GetNetname() in power or t.GetNetname().startswith('USB_') or foreign.GetNetname().startswith('USB_'):clear=.31
  else:clear=json.loads((H/'layout-config.json').read_text()).get('signal_clearance_mm',.3)+.01
  limit=min(limit,2*(distance-clear))
 width=max(mm(t.GetWidth()),math.floor((limit+1e-8)/.05)*.05)
 if width>mm(t.GetWidth())+.001:
  t.SetWidth(p.FromMM(width));obj['shape']=polygon(t);changed+=1
for t in tracks:
 if isinstance(t,p.PCB_VIA):t.SetFrontTentingMode(p.TENTING_MODE_TENTED);t.SetBackTentingMode(p.TENTING_MODE_TENTED)
p.ZONE_FILLER(B).Fill(B.Zones())

# The upstream HRO footprint references a STEP that packages3D does not ship.
# Use an explicitly nominal envelope from the manufacturer 2D drawing rather
# than disguising another connector model as this part.
usb_envelope=H/'GemilaiMateCompact.3dshapes'/'USB_C_HRO_nominal.wrl'
def envelope_box(x,y,z,w,h,t,color):
 u=2.54
 return f'Transform {{ translation {x/u} {y/u} {z/u} children Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} }} }} geometry Box {{ size {w/u} {h/u} {t/u} }} }} }}\n'
usb_envelope.write_text('#VRML V2.0 utf8\n# HRO TYPE-C-31-M-12: nominal maximum envelope, not a detailed STEP.\n'+envelope_box(0,.025,1.63,8.94,7.35,3.26,'0.70 0.70 0.72'))
# Self-contained copies of the KiCad standard 3D models.
models=H/'GemilaiMateCompact.3dshapes';models.mkdir(exist_ok=True)
for f in B.GetFootprints():
 original_models=list(f.Models());f.Models().clear()
 for model in original_models:
  filename=model.m_Filename
  model.m_Show=not parts.get(f.GetReference(),{}).get('dnp',False)
  if filename.endswith('USB_C_Receptacle_HRO_TYPE-C-31-M-12.step'):
   model.m_Filename='${KIPRJMOD}/GemilaiMateCompact.3dshapes/USB_C_HRO_nominal.wrl';f.Add3DModel(model);continue
  if filename.startswith('${KICAD10_3DMODEL_DIR}/'):
   src=Path('/usr/share/kicad/3dmodels')/filename.split('}/',1)[1]
   if src.exists():shutil.copyfile(src,models/src.name)
   elif not (models/src.name).exists():raise RuntimeError('Missing 3D model '+str(src))
   model.m_Filename='${KIPRJMOD}/GemilaiMateCompact.3dshapes/'+src.name
  f.Add3DModel(model)
for lib in (H/'GemilaiMateCompact.pretty').glob('*.kicad_mod'):
 text=lib.read_text()
 text=re.sub(r'\$\{KICAD10_3DMODEL_DIR\}/[^\"]*/([^/\"]+)',r'${KIPRJMOD}/GemilaiMateCompact.3dshapes/\1',text)
 text=text.replace('USB_C_Receptacle_HRO_TYPE-C-31-M-12.step','USB_C_HRO_nominal.wrl')
 lib.write_text(text)
# Daughterboard headers use exact Harwin housing sizes; unmeasured breakout
# envelopes remain conservative nominal rectangles and are flagged in geometry.
def box(center,size,color):
 x,y,z=center;sx,sy,sz=size;u=2.54
 return f'Transform {{ translation {x/u} {y/u} {z/u} children Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} }} }} geometry Box {{ size {sx/u} {sy/u} {sz/u} }} }} }}\n'
for alias in ['J_ADS','J_TC','J_LEVEL']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']];mod=D['module_sockets'][alias];bw,bh=mod['body_size_mm'];cx,cy=mod['body_center_local_mm'];cy=-cy
 text='#VRML V2.0 utf8\n'+box((cx,cy,11.84),(bw,bh,1.6),'0.05 0.20 0.55' if alias=='J_ADS' else '0.45 0.12 0.08')
 socket_len, socket_w, socket_h=mod['socket_body_mm']
 header_len, header_w, header_h=mod['male_header_body_mm']
 if alias=='J_LEVEL':
  # Two Harwin sockets, one for each 1x5 row on the CJMCU daughterboard.
  for row_y in [-6.35,6.35]:
   text+=box((0,row_y,socket_h/2),(socket_len,socket_w,socket_h),'0.08 0.08 0.08')
   text+=box((0,row_y,socket_h+header_h/2),(header_len,header_w,header_h),'0.08 0.08 0.08')
   for i in range(5):
    x=(i-2)*2.54
    text+=box((x,row_y,socket_h-6.1/2),(.64,.64,6.1),'0.8 0.7 0.2')
 else:
  n=10 if alias=='J_ADS' else 6
  pitch_dir=1 if alias=='J_ADS' else -1
  row_cx=(n-1)*2.54*pitch_dir/2
  # Female M20 housing above the carrier; male header plastic below the module.
  text+=box((row_cx,0,socket_h/2),(socket_len,socket_w,socket_h),'0.08 0.08 0.08')
  text+=box((row_cx,0,socket_h+header_h/2),(header_len,header_w,header_h),'0.08 0.08 0.08')
  for i in range(n):
   x=i*2.54*pitch_dir
   text+=box((x,0,socket_h-6.1/2),(.64,.64,6.1),'0.8 0.7 0.2')
 if alias=='J_TC':text+=box((cx,cy-7.5,15.64),(11,7,6),'0.1 0.5 0.2')
 path=models/(alias+'-nominal.wrl');path.write_text(text)
 model=p.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/GemilaiMateCompact.3dshapes/'+path.name;f.Add3DModel(model)

# Tented vias are still forbidden below all visible assembly text (cosmetic
# check stricter than the KiCad solder-mask DRC).
via_boxes=[]
for t in tracks:
 if isinstance(t,p.PCB_VIA):
  pos=t.GetPosition();r=mm(t.GetWidth(p.F_Cu))/2+.16;x,y=mm(pos.x),mm(pos.y);via_boxes.append([x-r,y-r,x+r,y+r])
obstacles={p.F_SilkS:list(via_boxes),p.B_SilkS:list(via_boxes)}
for a in pads:
 b=rect(a);b=[b[0]-.21,b[1]-.21,b[2]+.21,b[3]+.21]
 if a.GetAttribute()!=p.PAD_ATTRIB_SMD:obstacles[p.F_SilkS].append(b);obstacles[p.B_SilkS].append(b)
 else:obstacles[p.F_SilkS if a.GetLayer()==p.F_Cu else p.B_SilkS].append(b)
for c in D['parts']:
 if c['section']!='Connectors' or c['dnp']:continue
 for a in F[c['designator']].GraphicalItems():
  if a.GetLayer()==p.B_CrtYd:obstacles[p.B_SilkS].append(rect(a))
usb_y=next(c['y'] for c in D['parts'] if c['ref']=='J_USB')
usb_fp=next(f for f in B.GetFootprints() if f.GetReference()==next(c['designator'] for c in D['parts'] if c['ref']=='J_USB'))
for drawing in usb_fp.GraphicalItems():
 if drawing.GetLayer()==p.F_CrtYd:obstacles[p.F_SilkS].append(rect(drawing))
labels=[]
def overlaps(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
def label(text,layer,candidates,size=.7,required=True,owner='BOARD'):
 size=max(size,1.0)  # budget fabs: 1.0 mm characters with 0.15 mm strokes stay legible
 t=p.PCB_TEXT(B);t.SetText(text);t.SetLayer(layer);t.SetTextSize(V(size,size));t.SetTextThickness(p.FromMM(.15));t.SetMirrored(layer==p.B_SilkS)
 for x,y,angle in candidates:
  t.SetPosition(V(x,y));t.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T));b=rect(t)
  if b[0]<.35 or b[1]<.35 or b[2]>W-.35 or b[3]>H_MM-.35:continue
  if any(overlaps(b,o) for o in obstacles[layer]):continue
  B.Add(t);obstacles[layer].append([b[0]-.16,b[1]-.16,b[2]+.16,b[3]+.16]);labels.append(dict(text=text,owner=owner,layer=B.GetLayerName(layer),position_mm=[x,y],rotation=angle,bbox_mm=b,via_overlaps=0));return True
 if required:raise RuntimeError('No legible silkscreen location for '+owner+' '+text)
 return False

def near(x,y,angle=0,radius=3):
 return [(x+dx,y+dy,angle) for dy in [0,-1,1,-2,2,-3,3,-4,4,-5,5] for dx in [0,-.5,.5,-1,1,-2,2,-3,3] if abs(dx)<=radius and abs(dy)<=radius]
def wide(x,y):
 return near(x,y,radius=3)+sorted([(ix*.5,iy*.5,0) for ix in range(2,int(W*2)-1) for iy in range(2,int(H_MM*2)-1)],key=lambda a:(a[0]-x)**2+(a[1]-y)**2)

label('U1 N16R8',p.F_SilkS,near(15,20.7,radius=3),.7,required=False,owner='U1')
# Socket words are sorted by the real X coordinate, with VIN at pad 1 only.
for alias in ['J_ADS','J_TC','J_LEVEL']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']]
 # Place module pin legends on the reverse side so the inserted daughterboard
 # cannot cover them; the pad row remains readable from the assembly side.
 silk_layer=p.B_SilkS
 for pad in sorted(f.Pads(),key=lambda a:a.GetPosition().x):
  num=pad.GetNumber();name=c['names'][num];name={'3Vo_NC':'NC','ADDR':'ADR','ALRT':'NC','SCK':'CLK'}.get(name,name)
  if c['nets'][num] is None:name='NC'
  # The square pad and a separate nearby 1 mark the first contact.
  x,y=mm(pad.GetPosition().x),mm(pad.GetPosition().y)
  # Directly above/below the pin first; a sideways shift below half the 2.54 mm
  # pitch still names this pin when vias crowd it (USB corridor at the ADS row).
  candidates=[(x+dx,y+sign*dy/10,angle) for dx in [0,.25,-.25,.5,-.5,.75,-.75,1,-1,1.5,-1.5,2,-2,2.5,-2.5,3,-3,3.5,-3.5,4,-4] for angle in [0,90] for dy in range(16,80) for sign in [-1,1]]
  if alias=='J_ADS':
   side=[(x+sign*offset,y+shift,0) for sign in [-1,1] for offset in [2.5,2.4,2.3,2.2,2.1,2.0] for shift in [0,.2,-.2,.4,-.4]]
   candidates=side+candidates
  if alias in ['J_ADS','J_TC']:
   # Within one pitch of the pin, or further out on the line through the pin
   # across the row, so the legend never sits beside a neighbouring contact.
   b2=next(a for a in f.Pads() if a.GetNumber()=='2');b1=next(a for a in f.Pads() if a.GetNumber()=='1')
   rx,ry=mm(b2.GetPosition().x-b1.GetPosition().x),mm(b2.GetPosition().y-b1.GetPosition().y);rl=math.hypot(rx,ry)
   candidates=[q for q in candidates if math.dist(q[:2],(x,y))<2.6 or (abs((q[0]-x)*rx+(q[1]-y)*ry)/rl<=.5 and math.dist(q[:2],(x,y))<5.5)]
  label(name,silk_layer,candidates,.6,required=name!='NC',owner=c['designator']+'.'+num)
for alias in ['J_ADS','J_TC','J_LEVEL']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']];a=next(a for a in f.Pads() if a.GetNumber()=='1');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
 side=-1.8 if alias=='J_ADS' else 1.8  # outside the row first, then above/below pin 1
 layer=p.B_SilkS
 label('1',layer,near(x+side,y,radius=1)+near(x+side,y,radius=2)+near(x,y-1.9,radius=.5)+near(x,y+1.9,radius=.5),.6,owner=c['designator']+'.PIN1')
 if alias=='J_LEVEL':
  a=next(a for a in f.Pads() if a.GetNumber()=='6');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
  label('1',layer,near(x-1.8,y,radius=1)+near(x-1.8,y,radius=2)+near(x,y-1.9,radius=.5)+near(x,y+1.9,radius=.5),.6,owner=c['designator']+'.ROW_B_PIN1')
# The module name inside its body outline shows which side of the socket the
# board goes: a module turned by 180 degrees covers the wrong area.
for alias,name in [('J_ADS','ADS1115'),('J_TC','MAX31855'),('J_LEVEL','CJMCU-0102')]:
 a,b,e,g=D['module_sockets'][alias]['body_rect_mm'];cx,cy=(a+e)/2,(b+g)/2
 inside=sorted([(a+ix*.5,b+iy*.5,angle) for angle in [0,90] for ix in range(int((e-a)*2)+1) for iy in range(int((g-b)*2)+1)],key=lambda q:(q[0]-cx)**2+(q[1]-cy)**2+q[2]/100)
 des=next(c for c in D['parts'] if c['ref']==alias)['designator']
 if not label(name,p.B_SilkS,inside,1.0,required=False,owner=des+'.BODY'):
  if not label(name.replace('-','\n'),p.B_SilkS,inside,1.0,required=False,owner=des+'.BODY'):
   label(name.replace('-','\n'),p.F_SilkS,inside,1.0,owner=des+'.BODY')
# Several harnesses share a PH size: name the function next to each header.
FUNCTION={'J_PWR':'5V IN','J_DISPLAY':'DISP','J_PRESS':'BAR','J_BUTTONS':'BTN',
          'J_PUMP':'PUMP','J_VALVE':'VALVE','J_HEAT':'HEAT DNP','J_ALT':'ALT',
          'J_TOF':'TOF 3V3','J_ALBA':'ALBA 3V3','J_RGBW':'RGBW','J_LIGHT':'LIGHT'}
for c in D['parts']:
 if c['section']!='Connectors':continue
 f=F[c['designator']];xs=[mm(a.GetPosition().x) for a in f.Pads()];ys=[mm(a.GetPosition().y) for a in f.Pads()]
 cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2;text=c['designator']+' '+FUNCTION[c['ref']]
 along=0 if max(xs)-min(xs)>=max(ys)-min(ys) else 90
 row=[(cx,cy+d,along) for d in [-3.4,3.4,-4.4,4.4]] if along==0 else [(cx+d,cy,along) for d in [-3.4,3.4,-4.4,4.4]]
 candidates=[q for x,y,angle in row for q in near(x,y,angle,radius=4)]+[q for x,y,angle in row for q in near(x,y,90-along,radius=6)]
 candidates+=sorted([(cx+ix*.25,cy+iy*.25,angle) for angle in [0,90] for ix in range(-40,41) for iy in range(-40,41)],key=lambda q:(q[0]-cx)**2+(q[1]-cy)**2)
 if not label(text,p.B_SilkS,candidates,.7,required=False,owner=c['designator']+'.FUNCTION'):
  label(c['designator']+'\n'+FUNCTION[c['ref']],p.B_SilkS,candidates,.7,owner=c['designator']+'.FUNCTION')
def dot(layer,candidates,owner):
 # Filled 1 mm pin-1 dot: the function label already carries the designator.
 for x,y,_ in candidates:
  b=[x-.575,y-.575,x+.575,y+.575]
  if b[0]<.35 or b[1]<.35 or b[2]>W-.35 or b[3]>H_MM-.35 or any(overlaps(b,o) for o in obstacles[layer]):continue
  s=p.PCB_SHAPE(B);s.SetShape(p.SHAPE_T_CIRCLE);s.SetCenter(V(x,y));s.SetEnd(V(x+.5,y));s.SetFilled(True);s.SetWidth(p.FromMM(.15));s.SetLayer(layer);B.Add(s)
  obstacles[layer].append([b[0]-.16,b[1]-.16,b[2]+.16,b[3]+.16])
  labels.append(dict(text='PIN1 DOT',owner=owner,layer=B.GetLayerName(layer),position_mm=[x,y],rotation=0,bbox_mm=b,via_overlaps=0));return
 raise RuntimeError('No room for pin-1 mark '+owner)
for c in D['parts']:
 if c['section']!='Connectors':continue
 f=F[c['designator']];a=next(a for a in f.Pads() if a.GetNumber()=='1');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
 a2=next(a for a in f.Pads() if a.GetNumber()=='2');x2,y2=mm(a2.GetPosition().x),mm(a2.GetPosition().y)
 positions=near(x,y,radius=3)+[(x+ix*.25,y+iy*.25,0) for ix in range(-24,25) for iy in range(-24,25)]
 closer=[q for q in positions if math.dist(q[:2],(x,y))+.5<math.dist(q[:2],(x2,y2))]
 dot(p.B_SilkS,sorted(closer,key=lambda q:math.dist(q[:2],(x,y))),c['designator']+'.1')
def bar(layer,x,y,ux,uy,half,owner):
 # Cathode bar beside pad 1 (K), across the diode axis, outside the body.
 for length,offset,tangent in itertools.product([2.0,1.5,1.0],[.45,.6,.75,.9,1.05,1.2,1.4,1.65,1.9],[0,.25,-.25,.5,-.5,.75,-.75,1,-1]):
  cx,cy=x+ux*(half+offset)+uy*tangent,y+uy*(half+offset)-ux*tangent;ax,ay,bx,by=cx+uy*length/2,cy-ux*length/2,cx-uy*length/2,cy+ux*length/2
  b=[min(ax,bx)-.15,min(ay,by)-.15,max(ax,bx)+.15,max(ay,by)+.15]
  if b[0]<.35 or b[1]<.35 or b[2]>W-.35 or b[3]>H_MM-.35 or any(overlaps(b,o) for o in obstacles[layer]):continue
  s=p.PCB_SHAPE(B);s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(V(ax,ay));s.SetEnd(V(bx,by));s.SetWidth(p.FromMM(.3));s.SetLayer(layer);B.Add(s)
  obstacles[layer].append([b[0]-.16,b[1]-.16,b[2]+.16,b[3]+.16])
  labels.append(dict(text='CATHODE BAR',owner=owner,layer=B.GetLayerName(layer),position_mm=[cx,cy],rotation=0,bbox_mm=b,via_overlaps=0));return
 raise RuntimeError('No room for cathode mark '+owner)
# Every polarised SMD part gets an orientation mark on its own side: a dot at
# pin 1 of ICs and transistors, a cathode bar at diodes (KiCad pad 1 = K).
# The WROOM module is excluded: its antenna must overhang the board edge.
for c in D['parts']:
 if c['dnp'] or c['ref']=='U1' or not c['ref'].startswith(('U','Q_','D_')):continue
 f=F[c['designator']];layer=p.B_SilkS if f.IsFlipped() else p.F_SilkS
 a=next(a for a in f.Pads() if a.GetNumber()=='1');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
 a2=next(a for a in f.Pads() if a.GetNumber()=='2');x2,y2=mm(a2.GetPosition().x),mm(a2.GetPosition().y)
 if c['ref'].startswith('D_'):
  d=math.dist((x,y),(x2,y2));ux,uy=(x-x2)/d,(y-y2)/d;r=rect(a)
  bar(layer,x,y,ux,uy,abs(ux)*(r[2]-r[0])/2+abs(uy)*(r[3]-r[1])/2,c['designator']+'.POL');continue
 positions=near(x,y,radius=3)+[(x+ix*.25,y+iy*.25,0) for ix in range(-16,17) for iy in range(-16,17)]
 closer=[q for q in positions if math.dist(q[:2],(x,y))+.5<math.dist(q[:2],(x2,y2))]
 dot(layer,sorted(closer,key=lambda q:math.dist(q[:2],(x,y))),c['designator']+'.POL')
# Function and pin legends take priority over branding.
label('GemilaiMate COMPACT '+D['revision'],p.B_SilkS,wide(14,15),.85)
for text,x,y in [('NO MAINS',14,21),('Rico-X',14,17),('github.com/Rico-X/GemilaiMate',15,19)]:
 if not label(text,p.B_SilkS,wide(x,y),.8,required=False):label(text,p.F_SilkS,wide(x,y),.8,required=False)
# Add compact designators when there is space; the full assembly map always
# includes every reference even when a small resistor has no clear silk site.
missing=[]
for c in D['parts']:
 if c['ref'] in ['U1','J_ADS','J_TC'] or c['section']=='Connectors':continue
 f=F[c['designator']];x,y=mm(f.GetPosition().x),mm(f.GetPosition().y);layer=p.B_SilkS if f.IsFlipped() else p.F_SilkS
 if not label(c['designator'],layer,near(x,y-1.5,radius=2),.65,False,c['designator']):missing.append(c['designator'])

# DNP remains visible as an assembly outline, never as a fitted 3D part.
for c in D['parts']:
 if not c['dnp']:continue
 f=F[c['designator']];q=f.GetPosition();t=p.PCB_TEXT(B);t.SetText('DNP');t.SetPosition(q);t.SetTextSize(V(1,1));t.SetTextThickness(p.FromMM(.15));t.SetLayer(p.B_Fab if f.IsFlipped() else p.F_Fab);t.SetMirrored(f.IsFlipped());B.Add(t)

# Refresh all physical coordinates; the board, not a stale nominal placement,
# is the source of assembly positions.
for c in D['parts']:
 f=F[c['designator']];c.update(x=mm(f.GetPosition().x),y=mm(f.GetPosition().y),rotation=f.GetOrientationDegrees(),side='back' if f.IsFlipped() else 'front')
 for entry in c['pins']:
  a=next(a for a in f.Pads() if a.GetNumber()==entry['number']);entry.update(x=mm(a.GetPosition().x),y=mm(a.GetPosition().y))
 c['physical_pads']=[dict(number=a.GetNumber(),x=mm(a.GetPosition().x),y=mm(a.GetPosition().y),net=c['nets'].get(a.GetNumber()),smd=a.GetAttribute()==p.PAD_ATTRIB_SMD) for a in f.Pads() if a.GetNumber()]
(H/'design.json').write_text(json.dumps(D,ensure_ascii=False,indent=2)+'\n')
p.SaveBoard(str(H/'gemilaimate-compact.kicad_pcb'),B)
widths=collections.defaultdict(float)
for t in B.GetTracks():
 if not isinstance(t,p.PCB_VIA):widths[round(mm(t.GetWidth()),3)]+=mm(t.GetLength())
report=dict(widened_segments=changed,minimum_track_mm=min(widths),track_length_by_width_mm=dict(sorted(widths.items())),visible_labels=labels,small_references_only_in_assembly_map=missing,via_text_clearance_mm=.16,hardware_tested=False)
(H/'reports/layout.json').write_text(json.dumps(report,indent=2)+'\n')
print('Widened',changed,'segments; placed',len(labels),'labels; all visible text avoids vias and exposed pads.')
