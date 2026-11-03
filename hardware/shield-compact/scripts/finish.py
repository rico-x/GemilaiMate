#!/usr/bin/env python3
"""Maximise copper widths, bundle models and place collision-checked labels.
Execute with KiCad Python and Shapely on the remote build host.
"""
import gc;gc.disable()
import sys,json,math,shutil,hashlib,collections
from pathlib import Path
from shapely.geometry import LineString,Point,box as shape_box
ROOT=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
_app=application()
import pcbnew as p
seed_uuids('compact-final')
B=p.LoadBoard(str(H/'gemilaimate-compact.kicad_pcb'));D=json.loads((H/'design.json').read_text())
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
power={'+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED'}
changed=0
for obj in objects[:len(tracks)]:
 t=obj['item']
 if isinstance(t,p.PCB_VIA) or t.IsLocked():continue
 a,b=t.GetStart(),t.GetEnd();line=LineString([(mm(a.x),mm(a.y)),(mm(b.x),mm(b.y))])
 limit=.8 if t.GetNetname() in power else .35
 bounds=line.bounds;edge=min(bounds[0],bounds[1],65-bounds[2],50-bounds[3]);limit=min(limit,2*(edge-.31))
 for other in objects:
  if other['net']==obj['net'] or other is obj or (other['layer'] is not None and other['layer']!=obj['layer']):continue
  # 0.01mm extra geometric margin beyond the nominal net-class clearance.
  distance=line.distance(other['shape']);clear=.27 if isinstance(other['item'],p.PAD) and other['item'].GetAttribute()==p.PAD_ATTRIB_NPTH else .21
  limit=min(limit,2*(distance-clear))
 width=max(mm(t.GetWidth()),math.floor((limit+1e-8)/.05)*.05)
 if width>mm(t.GetWidth())+.001:
  t.SetWidth(p.FromMM(width));obj['shape']=polygon(t);changed+=1
for t in tracks:
 if isinstance(t,p.PCB_VIA):t.SetFrontTentingMode(p.TENTING_MODE_TENTED);t.SetBackTentingMode(p.TENTING_MODE_TENTED)
p.ZONE_FILLER(B).Fill(B.Zones())

# Self-contained copies of the KiCad standard 3D models.
models=H/'GemilaiMateCompact.3dshapes';models.mkdir(exist_ok=True)
for f in B.GetFootprints():
 for model in f.Models():
  filename=model.m_Filename
  if filename.startswith('${KICAD10_3DMODEL_DIR}/'):
   src=Path('/usr/share/kicad/3dmodels')/filename.split('}/',1)[1]
   if src.exists():shutil.copyfile(src,models/src.name)
   elif not (models/src.name).exists():raise RuntimeError('Missing 3D model '+str(src))
   model.m_Filename='${KIPRJMOD}/GemilaiMateCompact.3dshapes/'+src.name
# Box envelopes are explicit nominal daughterboards, including header plastic.
def box(center,size,color):
 x,y,z=center;sx,sy,sz=size;u=2.54
 return f'Transform {{ translation {x/u} {y/u} {z/u} children Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} }} }} geometry Box {{ size {sx/u} {sy/u} {sz/u} }} }} }}\n'
for alias in ['J_ADS','J_TC']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']];mod=D['module_sockets'][alias];a,b,e,g=mod['body_rect_mm'];cx=(a+e)/2-c['x'];cy=-((b+g)/2-c['y'])
 text='#VRML V2.0 utf8\n'+box((cx,cy,11.84),(e-a,g-b,1.6),'0.05 0.20 0.55' if alias=='J_ADS' else '0.45 0.12 0.08')
 n=10 if alias=='J_ADS' else 6
 for i in range(n):
  x=i*2.54*(1 if alias=='J_ADS' else -1)
  text+=box((x,0,4.25),(2.54,2.54,8.5),'0.08 0.08 0.08')
  text+=box((x,0,9.77),(.64,.64,2.54),'0.8 0.7 0.2')
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
obstacles[p.F_SilkS].append([2.175,40.115,12.775,50.335])  # USB metal housing must not hide assembly labels
labels=[]
def overlaps(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
def label(text,layer,candidates,size=.7,required=True,owner='BOARD'):
 t=p.PCB_TEXT(B);t.SetText(text);t.SetLayer(layer);t.SetTextSize(V(size,size));t.SetTextThickness(p.FromMM(.12));t.SetMirrored(layer==p.B_SilkS)
 for x,y,angle in candidates:
  t.SetPosition(V(x,y));t.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T));b=rect(t)
  if b[0]<.35 or b[1]<.35 or b[2]>64.65 or b[3]>49.65:continue
  if any(overlaps(b,o) for o in obstacles[layer]):continue
  B.Add(t);obstacles[layer].append([b[0]-.16,b[1]-.16,b[2]+.16,b[3]+.16]);labels.append(dict(text=text,owner=owner,layer=B.GetLayerName(layer),position_mm=[x,y],rotation=angle,bbox_mm=b,via_overlaps=0));return True
 if required:raise RuntimeError('No legible silkscreen location for '+owner+' '+text)
 return False

def near(x,y,angle=0,radius=3):
 return [(x+dx,y+dy,angle) for dy in [0,-1,1,-2,2,-3,3,-4,4,-5,5] for dx in [0,-.5,.5,-1,1,-2,2,-3,3] if abs(dx)<=radius and abs(dy)<=radius]
def wide(x,y):
 return near(x,y,radius=3)+sorted([(ix*.5,iy*.5,0) for ix in range(2,129) for iy in range(2,99)],key=lambda a:(a[0]-x)**2+(a[1]-y)**2)

# Branding on the reverse is visible despite the WROOM body on the front.
label('GemilaiMate COMPACT '+D['revision'],p.B_SilkS,wide(14,15),.85)
label('Rico-X',p.B_SilkS,wide(14,17),.8)
label('github.com/Rico-X/GemilaiMate',p.B_SilkS,wide(15,19),.7)
label('NO MAINS',p.B_SilkS,wide(14,21),.75)
label('U1 N16R8',p.F_SilkS,near(15,20.7,radius=3),.7,required=False,owner='U1')
# Socket words are sorted by the real X coordinate, with VIN at pad 1 only.
for alias in ['J_ADS','J_TC']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']]
 for pad in sorted(f.Pads(),key=lambda a:a.GetPosition().x):
  num=pad.GetNumber();name=c['names'][num];name={'3Vo_NC':'NC','ADDR':'ADR','ALRT':'NC','SCK':'CLK'}.get(name,name)
  if c['nets'][num] is None:name='NC'
  # The square pad and a separate nearby 1 mark the first contact.
  x,y=mm(pad.GetPosition().x),mm(pad.GetPosition().y)
  candidates=[(x,y+sign*dy/10,angle) for angle in [0,90] for dy in range(16,80) for sign in [-1,1]]
  label(name,p.F_SilkS,candidates,.6,required=name!='NC',owner=c['designator']+'.'+num)
for alias in ['J_ADS','J_TC']:
 c=next(c for c in D['parts'] if c['ref']==alias);f=F[c['designator']];a=next(a for a in f.Pads() if a.GetNumber()=='1');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
 label('1',p.F_SilkS,near(x+(-1.8 if alias=='J_ADS' else 1.8),y,radius=1),.6,owner=c['designator']+'.PIN1')
for c in D['parts']:
 if c['section']!='Connectors':continue
 f=F[c['designator']];a=next(a for a in f.Pads() if a.GetNumber()=='1');x,y=mm(a.GetPosition().x),mm(a.GetPosition().y)
 label(c['designator']+':1',p.B_SilkS,near(x,y-1.8,radius=3),.65,owner=c['designator']+'.1')
# Several harnesses share a PH size: name the function next to each header.
FUNCTION={'J_PWR':'5V IN','J_DISPLAY':'DISPLAY','J_PRESS':'PRESSURE','J_BUTTONS':'BUTTONS',
          'J_PUMP':'ROBOTDYN','J_VALVE':'VALVE','J_HEAT':'HEATER DNP','J_ALT':'ALT',
          'J_TOF':'TOF 3V3','J_ALBA':'ALBA','J_RGBW':'RGBW','J_LIGHT':'LIGHTS'}
for c in D['parts']:
 if c['section']!='Connectors':continue
 f=F[c['designator']];xs=[mm(a.GetPosition().x) for a in f.Pads()];ys=[mm(a.GetPosition().y) for a in f.Pads()]
 cx,cy=(min(xs)+max(xs))/2,(min(ys)+max(ys))/2;text=c['designator']+' '+FUNCTION[c['ref']]
 row=[(cx,cy+d,0) for d in [-3.4,3.4,-4.4,4.4]] if max(xs)-min(xs)>=max(ys)-min(ys) else [(cx+d,cy,90) for d in [-3.4,3.4,-4.4,4.4]]
 candidates=[q for x,y,angle in row for q in near(x,y,angle,radius=4)]
 label(text,p.B_SilkS,candidates,.7,owner=c['designator']+'.FUNCTION')
# Add compact designators when there is space; the full assembly map always
# includes every reference even when a small resistor has no clear silk site.
missing=[]
for c in D['parts']:
 if c['ref'] in ['U1','J_ADS','J_TC'] or c['section']=='Connectors':continue
 f=F[c['designator']];x,y=mm(f.GetPosition().x),mm(f.GetPosition().y);layer=p.B_SilkS if f.IsFlipped() else p.F_SilkS
 if not label(c['designator'],layer,near(x,y-1.5,radius=2),.65,False,c['designator']):missing.append(c['designator'])

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
