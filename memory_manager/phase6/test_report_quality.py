"""Prod 17.11: one unverifiable mission report among the sources read must be declared, not hide a correct citation."""
import sqlite3,unittest
from scripts.text_mission_window import result_provenance
from memory_manager.phase6.demand_queue import report_quality

OK='11111111-1111-1111-1111-111111111111';FAILED='22222222-2222-2222-2222-222222222222'

class ReportQuality(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE mm_missions(id,owner,scope,state); CREATE TABLE mm_events(owner,scope,event_key);')
        for mid,state in [(OK,'completed'),(FAILED,'failed')]:          # the failed one still wrote its report (prod e1a94db6)
            self.db.execute('INSERT INTO mm_missions VALUES(?,?,?,?)',(mid,'phase3-synthetic','private',state))
            self.db.execute('INSERT INTO mm_events VALUES(?,?,?)',('phase3-synthetic','private','mission-result-'+mid))
        self.p={'origin':'sqlite','selection_origin':'authenticated_host_tool_receipts','items':[
            {'source_ref':'synthetic://doselab/correction'},{'source_ref':'mission://'+OK},{'source_ref':'mission://'+FAILED},{'source_ref':'mission://'+FAILED}]}
    def q(self,output,projection=None):return report_quality(projection or self.p,output,self.db,result_provenance)

    def test_strict_check_alone_still_refuses_the_whole_answer(self):
        with self.assertRaisesRegex(PermissionError,'Unverified synthetic mission source'):result_provenance(self.p,'Source : synthetic://doselab/correction',self.db)

    def test_correct_citation_with_an_unverifiable_report_read_is_declared(self):
        self.assertEqual(self.q('Source : `synthetic://doselab/correction`'),(True,['mission://'+FAILED],False))

    def test_citing_the_unverifiable_report_is_never_quality(self):
        self.assertEqual(self.q('synthetic://doselab/correction et mission://'+FAILED),(False,['mission://'+FAILED],True))

    def test_uuid_only_or_no_synthetic_citation_stays_false(self):
        self.assertFalse(self.q('Mémoire '+OK)[0]);self.assertFalse(self.q('mission://'+OK)[0])

    def test_only_unverifiable_sources_is_false(self):
        p=dict(self.p,items=[{'source_ref':'mission://'+FAILED}])
        self.assertEqual(self.q('mission://'+FAILED,p),(False,['mission://'+FAILED],True))

    def test_every_other_refusal_still_propagates(self):
        for bad in [dict(self.p,origin='model'),dict(self.p,selection_origin='model'),dict(self.p,items=[{'source_ref':'file:///private'}])]:
            with self.assertRaises(PermissionError):self.q('synthetic://doselab/correction',bad)
        unknown='mission://33333333-3333-3333-3333-333333333333'       # unknown mission: same strict refusal, declared as unverified
        self.assertEqual(self.q('x',dict(self.p,items=[{'source_ref':unknown}])),(False,[unknown],False))
