"""Cosmetic track/via clearance for selected assembly labels (not a DRC waiver)."""
import hashlib,json,math
import pcbnew as p

def audit_protected_labels(board,hardware_dir):
    mm=p.ToMM;segments=[];vias=[];margin=.15
    for t in board.GetTracks():
        if isinstance(t,p.PCB_VIA):
            q=t.GetPosition();vias.append((mm(q.x),mm(q.y),mm(t.GetWidth(p.F_Cu))/2))
        elif t.GetLayer()==p.F_Cu:
            a,b=t.GetStart(),t.GetEnd();segments.append((mm(a.x),mm(a.y),mm(b.x),mm(b.y),mm(t.GetWidth())/2))
    def crosses(segment,rect):
        ax,ay,bx,by,r=segment;lo,hi=0.,1.;r+=margin
        for start,delta,left,right in [(ax,bx-ax,rect[0]-r,rect[2]+r),(ay,by-ay,rect[1]-r,rect[3]+r)]:
            if abs(delta)<1e-10:
                if not left<=start<=right:return False
            else:
                u,v=sorted(((left-start)/delta,(right-start)/delta));lo=max(lo,u);hi=min(hi,v)
                if lo>hi:return False
        return True
    labels=[t for t in board.GetDrawings() if isinstance(t,p.PCB_TEXT) and t.GetText() in ['MAX31855','ROBOTDYN CABLE']]
    fp=next(f for f in board.GetFootprints() if f.GetReference()=='J6')
    labels.extend(t for t in fp.GraphicalItems() if isinstance(t,p.PCB_TEXT) and t.GetText()=='DC+')
    assert len(labels)==3
    rows=[]
    for t in labels:
        bb=t.GetBoundingBox();rect=[mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom())]
        vcount=sum(math.hypot(max(rect[0]-x,0,x-rect[2]),max(rect[1]-y,0,y-rect[3]))<r+margin for x,y,r in vias)
        tcount=sum(crosses(s,rect) for s in segments)
        assert not vcount and not tcount,f'{t.GetText()} overlaps {vcount} vias / {tcount} front tracks'
        q=t.GetPosition();rows.append(dict(text=t.GetText(),position_mm=[mm(q.x),mm(q.y)],bbox_mm=rect,via_overlaps=vcount,front_track_overlaps=tcount))
    pcb=hardware_dir/'gemilaimate-shield.kicad_pcb'
    result=dict(pcb_sha256=hashlib.sha256(pcb.read_bytes()).hexdigest(),margin_mm=margin,protected_labels=sorted(rows,key=lambda x:x['text']))
    (hardware_dir/'silk-clearance.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS selected label clearance from front tracks and all vias')
