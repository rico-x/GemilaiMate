#!/usr/bin/env python3
"""Regression checks; needs KiCad's pcbnew and sexpdata, no DISPLAY required."""
from pathlib import Path
import copy,hashlib,json,sys,unittest

R=Path(__file__).resolve().parents[1];H=R/'hardware/shield'
sys.path.insert(0,str(H/'scripts'))
from kicad_runtime import application
_app=application()
import pcbnew as p
from silk_clearance import audit_silkscreen,collect_silk_texts
from check_shield import check_silk_report

class SilkRegressionTests(unittest.TestCase):
    def setUp(self):
        self.board=p.LoadBoard(str(H/'gemilaimate-shield.kicad_pcb'))

    def assert_bad_position(self,owner,text,x,y):
        label=next(t for ref,t in collect_silk_texts(self.board) if ref==owner and t.GetText()==text)
        label.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
        with self.assertRaisesRegex(AssertionError,'Silkscreen cosmetic overlaps'):
            audit_silkscreen(self.board,H)

    def test_old_ads_label_position_rejected(self):
        self.assert_bad_position('J2','VDD ... A3',16.51,61)

    def test_old_ch1_position_rejected(self):
        self.assert_bad_position('J6','CH1',82.5,60.96)

    def test_new_unlisted_back_label_rejected(self):
        label=p.PCB_TEXT(self.board);label.SetText('NEW ASSEMBLY LABEL')
        label.SetLayer(p.B_SilkS);label.SetTextSize(p.VECTOR2I(p.FromMM(.8),p.FromMM(.8)))
        label.SetPosition(p.VECTOR2I(p.FromMM(15.24),p.FromMM(60.96)))
        self.board.Add(label)
        with self.assertRaisesRegex(AssertionError,'NEW ASSEMBLY LABEL'):
            audit_silkscreen(self.board,H)

    def test_report_must_include_every_visible_label(self):
        pcb=H/'gemilaimate-shield.kicad_pcb';report=json.loads((H/'silk-clearance.json').read_text())
        sha=hashlib.sha256(pcb.read_bytes()).hexdigest()
        check_silk_report(pcb.read_text(),report,sha)
        incomplete=copy.deepcopy(report);incomplete['labels'].pop()
        with self.assertRaisesRegex(AssertionError,'every visible'):
            check_silk_report(pcb.read_text(),incomplete,sha)

if __name__=='__main__':unittest.main()
