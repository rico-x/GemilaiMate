#!/usr/bin/env python3
"""Local two-layer grid completion, followed by fresh KiCad DRC.

The raster is conservative and is not an acceptance checker. No clearance
waivers are added: only KiCad's final saved-board DRC can accept the result.
"""
import gc
gc.disable()
import argparse
import heapq
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString, Point, box

R=Path(__file__).resolve().parents[3];H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'hardware/shield/scripts'))
from kicad_runtime import application,seed_uuids
app=application();seed_uuids('compact-grid-completion')
import pcbnew as p
ap=argparse.ArgumentParser();ap.add_argument('--grid',type=float,default=.1)
ap.add_argument('--rounds',type=int,default=3);a=ap.parse_args()
pcb=H/'gemilaimate-compact.kicad_pcb';D=json.loads((H/'design.json').read_text())
W,HEIGHT=D['size_mm'];G=a.grid;SS=4;NX=int(round(W/G))+1;NY=int(round(HEIGHT/G))+1;N=NX*NY
power={'+3V3','+5V_CORE','+5V_EXT','EXT_IN','USB_VBUS','USB_FUSED'}
usb={'USB_DP','USB_DM','USB_DP_MCU','USB_DM_MCU'}
signal_clear=json.loads((H/'layout-config.json').read_text()).get('signal_clearance_mm',.3)
mm=p.ToMM;V=lambda x,y:p.VECTOR2I(p.FromMM(x),p.FromMM(y))

def bounds(item):
    b=item.GetBoundingBox();return tuple(map(mm,[b.GetLeft(),b.GetTop(),b.GetRight(),b.GetBottom()]))

def paint(draw,geom):
    if geom.is_empty:return
    if geom.geom_type=='Polygon':
        draw.polygon([(x/G*SS,y/G*SS) for x,y in geom.exterior.coords],fill=1)
    elif hasattr(geom,'geoms'):
        for q in geom.geoms:paint(draw,q)

def clearance(net):return .3 if net in power|usb else signal_clear

def masks(B,net,width):
    trace=[Image.new('1',(NX*SS,NY*SS)) for _ in range(2)];via=Image.new('1',(NX*SS,NY*SS))
    td=[ImageDraw.Draw(im) for im in trace];vd=ImageDraw.Draw(via)
    half=width/2
    margin=G/SS+.005
    portals={}
    for draw,radius in [(td[0],half+margin),(td[1],half+margin),(vd,.41)]:
        draw.rectangle((0,0,NX*SS-1,NY*SS-1),fill=1)
        draw.rectangle(((.5+radius)/G*SS,(.5+radius)/G*SS,(W-.5-radius)/G*SS,(HEIGHT-.5-radius)/G*SS),fill=0)
        for x,y in D['mounts_mm']:paint(draw,Point(x,y).buffer(2.5+radius))
    for f in B.GetFootprints():
        for pad in f.Pads():
            geom=box(*bounds(pad));foreign=pad.GetNetname()!=net
            th=pad.GetAttribute()!=p.PAD_ATTRIB_SMD
            layers=[0,1] if th else [0 if pad.IsOnLayer(p.F_Cu) else 1]
            if pad.GetAttribute()==p.PAD_ATTRIB_NPTH:
                gap=.4 if f.GetReference()=='J1' else .5
                for i in layers:paint(td[i],geom.buffer(gap+half+margin))
                paint(vd,geom.buffer(.86))
            elif foreign:
                gap=.2 if f.GetReference()=='J1' else max(clearance(net),clearance(pad.GetNetname()))
                for i in layers:paint(td[i],geom.buffer(gap+half+(.005 if f.GetReference()=='J1' else margin)))
                paint(vd,geom.buffer(max(gap,.3)+.4+margin))
            if pad.GetAttribute()==p.PAD_ATTRIB_SMD:
                # An ordinary cheap-fab drilled via may not wick solder from
                # a surface land, even when the copper is the same net.
                paint(vd,geom.buffer(.21))
            elif th:
                if pad.GetNetname()==net:
                    q=pad.GetPosition();portals[(round(mm(q.x)/G),round(mm(q.y)/G))]=(mm(q.x),mm(q.y))
                # Include same-net holes in the hole-to-hole constraint too.
                q=pad.GetPosition();rad=max(mm(pad.GetDrillSize().x),mm(pad.GetDrillSize().y))/2
                paint(vd,Point(mm(q.x),mm(q.y)).buffer(rad+.2+.66))
    for t in B.GetTracks():
        if t.GetNetname()==net:
            if isinstance(t,p.PCB_VIA):
                q=t.GetPosition();x,y=mm(q.x),mm(q.y)
                paint(vd,Point(x,y).buffer(mm(t.GetDrillValue())/2+.2+.66))
                portals[(round(x/G),round(y/G))]=(x,y)
            continue
        gap=max(clearance(net),clearance(t.GetNetname()))
        if isinstance(t,p.PCB_VIA):
            q=t.GetPosition();geom=Point(mm(q.x),mm(q.y)).buffer(mm(t.GetWidth(p.F_Cu))/2)
            gap=max(gap,.3)
            for draw in td:paint(draw,geom.buffer(gap+half+margin))
        else:
            u,v=t.GetStart(),t.GetEnd()
            geom=LineString([(mm(u.x),mm(u.y)),(mm(v.x),mm(v.y))]).buffer(mm(t.GetWidth())/2)
            paint(td[0 if t.GetLayer()==p.F_Cu else 1],geom.buffer(gap+half+margin))
        paint(vd,geom.buffer(max(gap,.3)+.4+margin))
    blocked=np.stack([np.array(im,dtype=bool)[::SS,::SS] for im in trace]);vm=np.array(via,dtype=bool)[::SS,::SS].copy()
    for x,y in portals:
        if 0<=x<NX and 0<=y<NY and not blocked[:,y,x].any():vm[y,x]=False
    return blocked,vm,portals

def cells(x,y,layers,blocked):
    out=[];ix,iy=round(x/G),round(y/G)
    for l in layers:
        for dy in [-1,0,1]:
            for dx in [-1,0,1]:
                u,v=ix+dx,iy+dy
                if 0<=u<NX and 0<=v<NY and not blocked[l,v,u] and math.hypot(u*G-x,v*G-y)<G*1.45:
                    out.append((l,u,v))
    return out

def cluster_endpoints(B, net, first_uuid, last_uuid):
    """Use every accessible land/track in each real copper component.

    A DRC track position is its first endpoint, not necessarily the end facing
    the gap. Restricting A* to that point can falsely report a closed pocket.
    Fresh KiCad DRC remains the acceptance criterion for this geometric graph.
    """
    items=[q for f in B.GetFootprints() for q in f.Pads() if q.GetNetname()==net]
    items += [q for q in B.GetTracks() if q.GetNetname()==net]
    shapes=[];layers=[];points=[]
    for q in items:
        if isinstance(q,p.PCB_VIA):
            pos=q.GetPosition();xy=(mm(pos.x),mm(pos.y))
            shapes.append(Point(*xy).buffer(mm(q.GetWidth(p.F_Cu))/2));layers.append({0,1});points.append([xy])
        elif isinstance(q,p.PAD):
            pos=q.GetPosition();xy=(mm(pos.x),mm(pos.y));bb=bounds(q)
            shapes.append(Point(*xy).buffer(mm(q.GetSize().x)/2) if q.GetShape()==p.PAD_SHAPE_CIRCLE else box(*bb))
            layers.append({0,1} if q.GetAttribute()!=p.PAD_ATTRIB_SMD else {0 if q.IsOnLayer(p.F_Cu) else 1});points.append([xy])
        else:
            u,v=q.GetStart(),q.GetEnd();line=LineString([(mm(u.x),mm(u.y)),(mm(v.x),mm(v.y))])
            shapes.append(line.buffer(mm(q.GetWidth())/2));layers.append({0 if q.GetLayer()==p.F_Cu else 1})
            count=max(1,math.ceil(line.length/.5));points.append([(line.interpolate(i/count,normalized=True).x,line.interpolate(i/count,normalized=True).y) for i in range(count+1)])
    parent=list(range(len(items)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i in range(len(items)):
        for j in range(i):
            if layers[i]&layers[j] and shapes[i].distance(shapes[j])<.001:
                parent[find(i)]=find(j)
    ids={str(q.m_Uuid.AsString()):i for i,q in enumerate(items)}
    return [[(xy,layers[i]) for i in range(len(items)) if find(i)==find(ids[uuid]) for xy in points[i]] for uuid in [first_uuid,last_uuid]]

def astar(blocked,via,sources,targets):
    target_ids={l*N+y*NX+x for l,x,y in targets}
    tx=sum(x for l,x,y in targets)/len(targets);ty=sum(y for l,x,y in targets)/len(targets)
    def heur(x,y):return max(abs(x-tx),abs(y-ty))+.41421356*min(abs(x-tx),abs(y-ty))
    dist=np.full(2*N,np.inf);parent=np.full(2*N,-1,dtype=np.int32);queue=[]
    for l,x,y in sources:
        node=l*N+y*NX+x;dist[node]=0;heapq.heappush(queue,(heur(x,y),0,node))
    steps=[(1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,1.41421356),(1,-1,1.41421356),(-1,1,1.41421356),(-1,-1,1.41421356)]
    visited=0;started=time.time()
    while queue:
        _,cost,node=heapq.heappop(queue)
        if cost!=dist[node]:continue
        if node in target_ids:
            path=[]
            while node>=0:
                l,k=divmod(node,N);y,x=divmod(k,NX);path.append((l,x,y));node=int(parent[node])
            return path[::-1]
        visited+=1
        if visited>4000000 or time.time()-started>240:
            print('GRID_LIMIT',visited,round(time.time()-started,2),flush=True);return None
        l,k=divmod(node,N);y,x=divmod(k,NX)
        for dx,dy,step in steps:
            u,v=x+dx,y+dy
            if not (0<=u<NX and 0<=v<NY) or blocked[l,v,u]:continue
            if dx and dy and (blocked[l,y,u] or blocked[l,v,x]):continue
            dest=l*N+v*NX+u;new=cost+step
            if new<dist[dest]:
                dist[dest]=new;parent[dest]=node;heapq.heappush(queue,(new+heur(u,v),new,dest))
        if not via[y,x] and not blocked[1-l,y,x]:
            dest=(1-l)*N+k;new=cost+50
            if new<dist[dest]:
                dist[dest]=new;parent[dest]=node;heapq.heappush(queue,(new+heur(x,y),new,dest))
    finite=np.flatnonzero(np.isfinite(dist));ys=(finite%N)//NX;xs=finite%NX
    print('GRID_NO_PATH',visited,'bounds_mm',([float(xs.min()*G),float(ys.min()*G),float(xs.max()*G),float(ys.max()*G)] if len(finite) else []),flush=True)
    np.savez_compressed(H/'reports/grid-reachable.npz',blocked=blocked,reachable=np.isfinite(dist).reshape(2,NY,NX))
    return None

def check(B):
    p.ZONE_FILLER(B).Fill(B.Zones());p.SaveBoard(str(pcb),B)
    report=H/'reports/completion-drc.json'
    subprocess.run(['kicad-cli','pcb','drc','--format','json','--schematic-parity','--output',str(report),str(pcb)],check=True,stdout=subprocess.DEVNULL)
    return json.loads(report.read_text())

B=p.LoadBoard(str(pcb));history=[]
for round_no in range(a.rounds):
    report=check(B)
    objects={str(q.m_Uuid.AsString()):q for f in B.GetFootprints() for q in f.Pads()}
    objects.update({str(q.m_Uuid.AsString()):q for q in B.GetTracks()})
    jobs=sorted(report['unconnected_items'],key=lambda v:math.dist(list(v['items'][0]['pos'].values()),list(v['items'][1]['pos'].values())))
    completed=0
    for job in jobs:
        first,last=job['items'];source=objects.get(first['uuid']);target=objects.get(last['uuid'])
        if source is None or target is None:continue
        net=source.GetNetname();width=.3 if net in power else .2
        def layers(item):
            return [0,1] if isinstance(item,p.PCB_VIA) or isinstance(item,p.PAD) and item.GetAttribute()!=p.PAD_ATTRIB_SMD else [0 if item.IsOnLayer(p.F_Cu) else 1]
        blocked,via,portals=masks(B,net,width)
        groups=cluster_endpoints(B,net,first['uuid'],last['uuid'])
        start=list({cell for xy,ls in groups[0] for cell in cells(*xy,ls,blocked)})
        end=list({cell for xy,ls in groups[1] for cell in cells(*xy,ls,blocked)})
        path=astar(blocked,via,start,end) if start and end else None
        entry=dict(round=round_no,net=net,success=bool(path),start=first['pos'],end=last['pos'])
        history.append(entry);print(json.dumps(entry),flush=True)
        if not path:continue
        ni=B.FindNet(net);segments=[]
        def track(u,v,l):
            if math.dist(u,v)<1e-6:return
            t=p.PCB_TRACK(B);t.SetStart(V(*u));t.SetEnd(V(*v));t.SetLayer(p.F_Cu if l==0 else p.B_Cu);t.SetWidth(p.FromMM(width));t.SetNet(ni);B.Add(t);segments.append(t)
        def vertex(q):return (q[1]*G,q[2]*G)
        # Grid endpoints lie within existing copper; no artificial DRC-position lead.
        anchor=prev=path[0];direction=None
        for q in path[1:]:
            if q[0]!=prev[0]:
                track(vertex(anchor),vertex(prev),prev[0])
                if (q[1],q[2]) in portals:
                    pos=portals[(q[1],q[2])];track(vertex(q),pos,0);track(vertex(q),pos,1)
                else:
                    v=p.PCB_VIA(B);v.SetPosition(V(*vertex(q)));v.SetWidth(p.FromMM(.8));v.SetDrill(p.FromMM(.4));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(ni);B.Add(v);segments.append(v)
                anchor=q;direction=None
            else:
                step=(q[1]-prev[1],q[2]-prev[2])
                if direction is not None and step!=direction:track(vertex(anchor),vertex(prev),prev[0]);anchor=prev
                direction=step
            prev=q
        track(vertex(anchor),vertex(path[-1]),path[-1][0])
        # The last grid cell overlaps the target copper component.
        completed+=1
    if not completed:break
final=check(B)
(H/'reports/completion.json').write_text(json.dumps(dict(grid_mm=G,attempts=history,unconnected=len(final['unconnected_items']),violations=len(final['violations'])),indent=2)+'\n')
print('Completion result',len(final['unconnected_items']),'unconnected',len(final['violations']),'DRC violations; review is mandatory')
