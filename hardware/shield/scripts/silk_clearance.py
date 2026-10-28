"""Check every visible silk text against vias; retain selected track checks.

Tented vias are a cosmetic constraint, separate from the electrical DRC.
Copper planes and tracks under ordinary silkscreen are not forbidden here.
"""
import hashlib,json,math
import pcbnew as p

TRACK_CHECK_TEXTS={'MAX31855','ROBOTDYN CABLE','DC+'}
SILK_TEXT_TYPES=(p.PCB_TEXT,p.PCB_TEXTBOX)

def collect_silk_texts(board):
    labels=[]
    for t in board.GetDrawings():
        if isinstance(t,SILK_TEXT_TYPES) and t.IsVisible() and t.GetLayer() in [p.F_SilkS,p.B_SilkS]:labels.append(('BOARD',t))
    for f in board.GetFootprints():
        # GetFields includes reference, value and any custom visible fields.
        for t in [*list(f.GetFields()),*list(f.GraphicalItems())]:
            if isinstance(t,SILK_TEXT_TYPES) and t.IsVisible() and t.GetLayer() in [p.F_SilkS,p.B_SilkS]:labels.append((f.GetReference(),t))
    return labels

def audit_silkscreen(board,hardware_dir):
    mm=p.ToMM;segments={p.F_SilkS:[],p.B_SilkS:[]};vias=[];margin=.15
    for t in board.GetTracks():
        if isinstance(t,p.PCB_VIA):
            q=t.GetPosition();vias.append((mm(q.x),mm(q.y),mm(t.GetWidth(p.F_Cu))/2))
        elif t.GetLayer() in [p.F_Cu,p.B_Cu]:
            a,b=t.GetStart(),t.GetEnd();side=p.F_SilkS if t.GetLayer()==p.F_Cu else p.B_SilkS
            segments[side].append((mm(a.x),mm(a.y),mm(b.x),mm(b.y),mm(t.GetWidth())/2))
    def crosses(segment,rect):
        ax,ay,bx,by,r=segment;lo,hi=0.,1.;r+=margin
        for start,delta,left,right in [(ax,bx-ax,rect[0]-r,rect[2]+r),(ay,by-ay,rect[1]-r,rect[3]+r)]:
            if abs(delta)<1e-10:
                if not left<=start<=right:return False
            else:
                u,v=sorted(((left-start)/delta,(right-start)/delta));lo=max(lo,u);hi=min(hi,v)
                if lo>hi:return False
        return True
    labels=collect_silk_texts(board);rows=[];failures=[]
    assert labels
    for owner,t in labels:
        bb=t.GetBoundingBox();rect=[mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom())]
        vcount=sum(math.hypot(max(rect[0]-x,0,x-rect[2]),max(rect[1]-y,0,y-rect[3]))<r+margin for x,y,r in vias)
        tcount=sum(crosses(s,rect) for s in segments[t.GetLayer()])
        track_required=t.GetLayer()==p.F_SilkS and t.GetText() in TRACK_CHECK_TEXTS
        if vcount or (track_required and tcount):failures.append(f'{owner} {t.GetText()!r}: {vcount} vias, {tcount} side tracks (track check={track_required})')
        q=t.GetPosition();rows.append(dict(owner=owner,text=t.GetText(),layer='F.SilkS' if t.GetLayer()==p.F_SilkS else 'B.SilkS',position_mm=[mm(q.x),mm(q.y)],bbox_mm=rect,via_overlaps=vcount,side_track_overlaps=tcount,track_check_required=track_required))
    assert {r['text'] for r in rows if r['track_check_required']}==TRACK_CHECK_TEXTS
    assert not failures,'Silkscreen cosmetic overlaps:\n'+'\n'.join(failures)
    pcb=hardware_dir/'gemilaimate-shield.kicad_pcb'
    result=dict(pcb_sha256=hashlib.sha256(pcb.read_bytes()).hexdigest(),margin_mm=margin,
                scope='all visible front/back silkscreen texts, including footprint fields',
                via_check='all labels',track_check='selected front labels only; other track counts are informational',
                labels=sorted(rows,key=lambda r:(r['layer'],r['owner'],r['text'],r['position_mm'])))
    (hardware_dir/'silk-clearance.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS via clearance for all {len(rows)} visible front/back silk texts; selected track checks retained')
