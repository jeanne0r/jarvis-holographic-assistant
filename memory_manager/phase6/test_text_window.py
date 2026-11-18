"""C-window guard unit tests; never runs the administrative lifecycle."""
import importlib.util,json,sqlite3,unittest
from pathlib import Path
from scripts.text_mission_window import result_provenance,gateway_expected

class TextWindowTests(unittest.TestCase):
    def test_profile_limits_and_distinct_consumption(self):
        path=Path(__file__).resolve().parents[2]/'ops/pilot-network/run-worker-window.py'
        spec=importlib.util.spec_from_file_location('window_under_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.read_verified(module.SRC/'docs/HERMES_TEXT_MISSIONS_MANIFEST.json',module.TEXT_REVIEW_SHA)
        module.read_verified(module.SRC/'scripts/text_mission_window.py',module.TEXT_CONTRACT_SHA)
        tokens=dict(zip(module.NAMES,['H'*43,'M'*43,'R'*43]))
        cfg={'bridgeToken':'B'*43,'operations':dict.fromkeys(['admissionEnabled','textEnabled','workerEnabled','voiceEnabled'],False)}
        default,_=module.runtime_config(cfg,tokens,'S'*43,now=100)
        text,window=module.runtime_config(cfg,tokens,'S'*43,now=100,text_enabled=True)
        self.assertFalse(default['operations']['textEnabled']);self.assertTrue(text['operations']['textEnabled'])
        self.assertFalse(text['operations']['voiceEnabled']);self.assertEqual(window['expires_at'],400)
        self.assertEqual(window['limits'],{'calls':6,'missions':1});self.assertEqual(window['local_token_limit'],98304)
        self.assertEqual(text['operations']['runtime']['maxMissions'],1)
        with self.assertRaises(PermissionError):module.runtime_config(cfg,{**tokens,'model.token':'H'*43},'S'*43,now=100,text_enabled=True)

    def test_only_explicitly_reviewed_gateway_preimages(self):
        review={'gateway_assets':{'panel.js':'reviewed'}}
        self.assertEqual(gateway_expected({'target':'panel.js','before':'old','after':'older'},[],review),'reviewed')
        self.assertEqual(gateway_expected({'target':'server.js','before':'safe','after':'changed'},[],review),'safe')

    def test_canonical_receipts_and_known_synthetic_experiences(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript('CREATE TABLE mm_missions(id,owner,scope,state); CREATE TABLE mm_events(owner,scope,event_key);')
            mid='11111111-1111-1111-1111-111111111111'
            db.execute('INSERT INTO mm_missions VALUES(?,?,?,?)',(mid,'phase3-synthetic','private','completed'))
            db.execute('INSERT INTO mm_events VALUES(?,?,?)',('phase3-synthetic','private','mission-result-'+mid))
            projection={'origin':'sqlite','selection_origin':'authenticated_host_tool_receipts','items':[{'source_ref':'synthetic://doselab/correction'},{'source_ref':'mission://'+mid}]}
            refs,cited=result_provenance(projection,'Source synthetic://doselab/correction',db)
            self.assertTrue(cited);self.assertEqual(len(refs),2)
            for bad in [dict(projection,origin='model'),dict(projection,selection_origin='model'),dict(projection,items=[{'source_ref':'file:///private'}]),dict(projection,items=[{'source_ref':'mission://22222222-2222-2222-2222-222222222222'}])]:
                with self.assertRaises(PermissionError):result_provenance(bad,'x',db)
            db.execute("UPDATE mm_missions SET state='paused'")
            with self.assertRaises(PermissionError):result_provenance(projection,'x',db)
