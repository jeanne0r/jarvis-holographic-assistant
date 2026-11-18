"""Synthetic only; no private-source reads, Windows, GPU or live Qdrant."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from memory_manager.mcp_utf8 import configure_stdio
from memory_manager.phase3 import mcp, lab
from memory_manager.phase4.windows import profile
from memory_manager.phase2 import database
from memory_manager.phase2.memory_tools import MemoryTools
from memory_manager.phase5 import database as p5, vector
from memory_manager.phase5.test_memory import FakeEmbeddings, FakeQdrant, ART
from memory_manager.store import Memory, Principal
from . import semantic, personal


class Unicode(unittest.TestCase):
    def test_mcp_wire_roundtrip_with_cp1252_stdio(self):
        for text in ('expérience, fraîcheur et refroidissement', 'S19 XP Hydro Ø12 mm — 35 °C, µS/cm',
                     '« vérifier l’eau » et "révision"', '中文 🚰 e\u0301 Ω HX711'):
            with self.subTest(text=text):
                raw=json.dumps({'jsonrpc':'2.0','id':7,'method':'tools/call','params':{
                    'name':'jarvis_memory_knowledge','arguments':{'q':text}}},ensure_ascii=False).encode('utf-8')+b'\n'
                # This reproduces the broken decoding without touching any stored row.
                self.assertNotEqual(json.loads(raw.decode('cp1252',errors='replace'))['params']['arguments']['q'],text)
                incoming=io.TextIOWrapper(io.BytesIO(raw),encoding='cp1252')
                outgoing_bytes=io.BytesIO();outgoing=io.TextIOWrapper(outgoing_bytes,encoding='cp1252')
                calls=[]
                def http(method,path,body=None,**kw):
                    calls.append(body);return {'result':{'quoted':text}}
                with patch('sys.stdin',incoming),patch('sys.stdout',outgoing),patch('sys.stderr',io.StringIO()),patch('sys.argv',['mcp','--token-file','unused']),patch.object(mcp,'PrivateHTTP',return_value=http):
                    mcp.main(token_reader=lambda _: 'synthetic-only-token')
                self.assertEqual(calls[0]['arguments']['q'],text)
                self.assertEqual(json.loads(json.loads(outgoing_bytes.getvalue())['result']['content'][0]['text'])['result']['quoted'],text)
                self.assertEqual(incoming.errors,'strict')
    def test_bad_utf8_fails_instead_of_repairing_input(self):
        stream=io.TextIOWrapper(io.BytesIO(b'\xff\n'),encoding='cp1252')
        with patch('sys.stdin',stream),patch('sys.stdout',io.StringIO()),patch('sys.stderr',io.StringIO()):configure_stdio()
        with self.assertRaises(UnicodeDecodeError):stream.readline()
    def test_windows_profile_explicitly_reinjects_encoding(self):
        env=profile()['mcp_servers']['jarvis']['env']
        self.assertEqual(env['PYTHONUTF8'],'1');self.assertEqual(env['PYTHONIOENCODING'],'utf-8:strict')


class Semantic(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.m=Memory(Path(self.tmp.name)/'lab.sqlite',create=True)
        database.migrate(self.m);p5.migrate(self.m);self.ids=lab.seed(self.m)
        self.p=Principal(lab.OWNER,frozenset({'private'}),lab.HOST.roles|{'indexer'})
        self.q=vector.Qdrant(FakeQdrant());self.e=vector.Embeddings(FakeEmbeddings(),ART)
        vector.index(self.m,self.p,self.q,self.e)
    def tearDown(self):self.m.close();self.tmp.cleanup()
    def test_actual_mcp_discovery_is_admitted_by_the_runtime_relay(self):
        from memory_manager.phase4.native_trial import validate_advertised_tools
        tools=mcp.dispatch({'id':1,'method':'tools/list'},None)['result']['tools']
        body={'tools':[{'function':{'name':'mcp__jarvis__'+t['name']}} for t in tools]}
        self.assertIn('mcp__jarvis__jarvis_memory_knowledge',[t['function']['name'] for t in body['tools']])
        validate_advertised_tools(body)
        for name in ('shell','ha.pump','jarvis_skill_publish','jarvis_skill_propose'):
            with self.assertRaises(PermissionError):validate_advertised_tools({'tools':[{'function':{'name':'mcp__jarvis__'+name}}]})
        validate_advertised_tools({'tools':[{'function':{'name':'mcp__jarvis__jarvis_skill_propose'}}]},skill_mode=True)

    def test_filtered_tool_and_independent_runtime_evidence(self):
        traces=[]
        def searcher(memory,principal,q,**filters):
            self.assertEqual(filters,{'memory_type':'knowledge'})
            rows,trace=semantic.observe(memory,principal,q,self.q,self.e,mission_id='synthetic-run')
            traces.append(trace);return rows
        tools=MemoryTools(self.m,self.p,searcher=searcher)
        wire=mcp.dispatch({'id':1,'method':'tools/call','params':{'name':'jarvis_memory_knowledge','arguments':{'q':semantic.QUERY}}},
                          lambda method,path,body: {'result':tools.call(body['name'],body['arguments'])})
        self.assertNotIn('error',wire);trace=traces[0];self.assertEqual(trace['fts_count'],0)
        args=dict(mission_id='synthetic-run',native_status='completed',successful_tools=['mcp__jarvis__jarvis_memory_knowledge'],
                  output='source synthetic://doselab/correction',expected_id=self.ids['configuration_memory_id'],
                  expected_revision=self.ids['current_revision'],expected_source='synthetic://doselab/correction')
        self.assertTrue(semantic.verify(trace,**args))
        for change in ({'successful_tools':[]},{'mission_id':'other'},{'output':'invented source'}, {'expected_revision':'obsolete'}):
            self.assertFalse(semantic.verify(trace,**{**args,**change}))
        for field,value in (('fts_count',1),('memory_type','episode'),('query',semantic.QUERY+' DoseLab')):
            self.assertFalse(semantic.verify({**trace,field:value},**args))
        degraded=copy.deepcopy(trace);degraded['rows'][0]['mode']='fts_only_degraded'
        self.assertFalse(semantic.verify(degraded,**args))
    def test_knowledge_tool_cannot_supply_owner_or_permissions(self):
        for extra in ({'owner':'other'},{'type':'episode'},{'shell':True}):
            with self.assertRaises(ValueError):MemoryTools(self.m,self.p).call('memory.knowledge',{'q':'x',**extra})
        other=Principal('other',frozenset({'private'}),frozenset({'reader'}))
        self.assertEqual(MemoryTools(self.m,other).call('memory.knowledge',{'q':'DoseLab'}),[])

    def test_semantic_result_provenance_and_history_identifiers(self):
        rows,trace=semantic.observe(self.m,self.p,semantic.QUERY,self.q,self.e,mission_id='fixture')
        row=next(r for r in rows if r['memory_id']==self.ids['configuration_memory_id'])
        self.assertEqual(row['source']['ref'],'synthetic://doselab/correction')
        tools=MemoryTools(self.m,self.p)
        history=tools.call('memory.history',{'memory_id':row['memory_id']})
        self.assertEqual({r['source']['ref'] for r in history},
                         {'synthetic://doselab/old','synthetic://doselab/correction'})
        for wrong in (row['id'],row['source']['ref']):
            with self.assertRaises(KeyError):tools.call('memory.history',{'memory_id':wrong})
        args=dict(mission_id='fixture',native_status='completed',
                  successful_tools=['mcp__jarvis__jarvis_memory_knowledge'],
                  expected_id=row['memory_id'],expected_revision=row['id'],expected_source=row['source']['ref'])
        self.assertFalse(semantic.verify(trace,output=row['id']+' '+row['memory_id'],**args))
        self.assertTrue(semantic.verify(trace,output=row['source']['ref'],**args))

    def test_wire_contract_and_ordered_history_lookup(self):
        from urllib.parse import parse_qs,urlsplit
        from memory_manager.hermes_mcp import TOOLS
        original=copy.deepcopy(TOOLS)
        advertised=mcp.dispatch({'id':1,'method':'tools/list'},None)['result']['tools']
        history=next(t for t in advertised if t['name']=='jarvis_memory_history')
        knowledge=next(t for t in advertised if t['name']=='jarvis_memory_knowledge')
        self.assertIn('First await',history['description'])
        self.assertIn('source.ref verbatim',knowledge['description'])
        self.assertEqual(history['inputSchema']['required'],['memory_id'])
        self.assertFalse(history['inputSchema']['additionalProperties'])
        self.assertEqual(TOOLS,original)  # Discovery does not mutate the shared base.
        backend=MemoryTools(self.m,self.p,searcher=lambda m,p,q,**kw:
                            semantic.observe(m,p,q,self.q,self.e,mission_id='fixture')[0])
        def http(method,path,body=None):
            if method=='POST':return {'result':backend.call(body['name'],body['arguments'])}
            args=parse_qs(urlsplit(path).query)
            return {'history':backend.call('memory.history',{'memory_id':args['memory_id'][0]})}
        def call(name,args):
            return mcp.dispatch({'id':2,'method':'tools/call','params':{'name':name,'arguments':args}},http)
        result=call('jarvis_memory_knowledge',{'q':semantic.QUERY})
        row=json.loads(result['result']['content'][0]['text'])['result'][0]
        for wrong in ('synthetic://doselab/old',row['id'],row['source']['ref']):
            self.assertEqual(call('jarvis_memory_history',{'memory_id':wrong})['error']['message'],
                             'MEMORY_DENIED_OR_UNAVAILABLE')
        response=call('jarvis_memory_history',{'memory_id':row['memory_id']})
        revisions=json.loads(response['result']['content'][0]['text'])['history']
        self.assertEqual(revisions[-1]['source']['ref'],row['source']['ref'])
        self.assertEqual(revisions[0]['effective_status'],'superseded')


class Import(unittest.TestCase):
    def rows(self):
        row={'source_db':'synthetic.sqlite','table':'docs','id':'one','space':'private-user','observed_at':1700000000,
             'type':'knowledge','subject':personal.PROJECT,'predicate':'cooling','content':{'component':'synthetic-only'},'speaker':'user','replaces':None}
        selection={'project':personal.PROJECT,'sources':[{k:row[k] for k in ('source_db','table','id')}]}
        return row,selection,{'private-user':('test-user','private')}
    def test_plan_is_bounded_inferred_and_preserves_provenance(self):
        row,selection,identities=self.rows();r=personal.dry_run([row,row],selection,identities)
        self.assertEqual(r['source_count'],1);self.assertEqual(r['writes'],0)
        self.assertIsNotNone(r['proposals'][1]['candidate']['duplicate_of'])
        self.assertEqual(r['proposals'][0]['candidate']['proposed_status'],'inferred')
        self.assertEqual(r['proposals'][0]['candidate']['source']['observed_at'],1700000000)
        bad={**row,'content':{'component':'incompatible'},'speaker':'assistant','replaces':'untrusted-reference'}
        r=personal.dry_run([row,bad],selection,identities)
        self.assertTrue(r['proposals'][0]['candidate']['contradicts']);self.assertFalse(r['proposals'][1]['candidate']['automatic_supersession'])
        for changed in ({**row,'id':'unselected'},{**row,'subject':'another project'}):
            with self.assertRaises(PermissionError):personal.dry_run([changed],selection,identities)
        selection['sources']=[{'source_db':'s','table':'t','id':str(i)} for i in range(21)]
        with self.assertRaises(ValueError):personal.dry_run([],selection,identities)
    def test_private_report_exclusive_and_no_outside_worktree_write(self):
        row,selection,identities=self.rows();result=personal.dry_run([row],selection,identities)
        root=Path(__file__).resolve().parents[2]/'data/phase5c';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            folder=Path(tmp)/'review';p=personal.write_private(folder,result)
            self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertEqual(folder.stat().st_mode&0o777,0o700)
            with self.assertRaises(FileExistsError):personal.write_private(folder,result)
        with self.assertRaises(PermissionError):personal.write_private(Path('/tmp/unapproved'),result)


class Launcher(unittest.TestCase):
    def test_single_mission_launcher_wires_canonical_search_and_runtime_proof(self):
        from scripts import pilot_phase5c_semantic as pilot
        from memory_manager.phase5.native_lab import prepare
        from memory_manager import missions
        from types import SimpleNamespace
        from urllib.parse import urlsplit
        with tempfile.TemporaryDirectory() as tmp,patch.object(lab,'ROOT',Path(tmp)):
            folder=Path(tmp)/'data/phase5/fresh';prepare(folder)
            eq=FakeEmbeddings();qd=FakeQdrant()
            def native(config,upstream,telemetry,**kwargs):
                self.assertEqual(kwargs['mission_numbers'],(1,))
                self.assertEqual(kwargs['required_search_tool'],'jarvis_memory_knowledge')
                m=Memory(folder/'memory.sqlite');p=Principal(lab.OWNER,frozenset({'private'}),frozenset({'reader','mission_writer'}))
                try:
                    mid=missions.create(m,p,'fixture',{'objective':'synthetic','trigger':'test','priority':1,'memory_context':[],
                        'plan':['read'],'allowed_tools':['memory.search'],'budget':{'tokens':0,'cost_micros':0,'seconds':180,'attempts':1}})
                    with m.db:m.db.execute("UPDATE mm_missions SET state='running' WHERE id=?",(mid,))
                    body=json.dumps({'name':'memory.knowledge','arguments':{'q':semantic.QUERY}}).encode()
                    request=SimpleNamespace(command='POST',headers={'Content-Length':str(len(body))},rfile=io.BytesIO(body))
                    response=kwargs['memory_extension'](m,p,request,urlsplit('/v1/tools/call'),{})
                    self.assertEqual(response[1]['result'][0]['source']['ref'],'synthetic://doselab/correction')
                    stable=response[1]['result'][0]['memory_id']
                    request.command='GET'
                    with self.assertRaises(KeyError):
                        kwargs['memory_extension'](m,p,request,urlsplit('/v1/history'),{'memory_id':'synthetic://doselab/old'})
                    history=kwargs['memory_extension'](m,p,request,urlsplit('/v1/history'),{'memory_id':stable})
                    self.assertTrue({'synthetic://doselab/old','synthetic://doselab/correction'}<=
                                    {r['source']['ref'] for r in history[1]['items']})
                    return {'passed':True,'missions':[{'mission_id':mid,'native_status':{'status':'completed','output':'synthetic://doselab/correction'},
                        'successful_native_tools':['mcp__jarvis__jarvis_memory_knowledge']}]}
                finally:m.close()
            with patch.object(pilot,'CT205',side_effect=lambda service,*a,**kw:eq if service=='embedding' else qd),patch.object(pilot,'native_run',side_effect=native):
                result=pilot.execute(None,None,None,folder=folder,private_state='unused',artifact=ART)
                self.assertTrue(result['passed']);self.assertTrue(result['strict_semantic_verified'])
                self.assertTrue(result['stable_history_id_verified'])
                self.assertFalse(result['history_traces'][0]['accepted'])
    def test_no_approval_never_probes_windows(self):
        from scripts import pilot_phase5c_semantic as pilot
        with patch('sys.argv',['pilot']),patch.object(pilot,'read_only_preflight') as probe,patch('sys.stderr',io.StringIO()):
            with self.assertRaises(SystemExit):pilot.main()
            probe.assert_not_called()


class Backup(unittest.TestCase):
    def test_plan_only_capacity_and_integrity_requirements(self):
        from .backup import plan, SIZE, SHA256
        with self.assertRaises(ValueError):plan('/private/backup',1460101120)
        r=plan('/private/backup',4*1024**3)
        self.assertEqual(r['archive_bytes'],SIZE);self.assertEqual(r['archive_sha256'],SHA256)
        self.assertFalse(r['transfer_authorized']);self.assertFalse(r['restore_authorized'])
        with self.assertRaises(ValueError):plan('../escape',4*1024**3)


if __name__=='__main__':unittest.main()
