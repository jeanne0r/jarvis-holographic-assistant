"""Synthetic local sources only; never opens Jarvis databases."""
import hashlib,json
from pathlib import Path
import sqlite3,tempfile,unittest
from unittest.mock import patch
from .local_review import review


class Review(unittest.TestCase):
    def test_twenty_source_readonly_private_report_and_secret_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'synthetic.sqlite';c=sqlite3.connect(db)
            c.executescript('CREATE TABLE docs(id,title,body,kind,source,updated,fingerprint,space); CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,title,body);')
            for i in range(25):
                body='S19 Hydro refroidissement\nInstallation pompe 5 L/min, température 35 °C.\nCorrection à relire.\npassword=synthetic-secret-never-export'
                c.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?)',(str(i),'test',body,'Mémoire','synthetic://source',1700000000,'hash','user'))
                c.execute('INSERT INTO search VALUES(?,?,?)',(str(i),'test',body))
            c.commit();c.close();before=hashlib.sha256(db.read_bytes()).hexdigest()
            folder=Path(tmp)/'private';result=review(db,folder)
            self.assertEqual(result['examined_sources'],20);self.assertEqual(result['source_database_writes'],0)
            self.assertEqual(before,hashlib.sha256(db.read_bytes()).hexdigest())
            self.assertNotIn('synthetic-secret-never-export',(folder/'import-review.json').read_text())
            data=json.loads((folder/'import-review.json').read_text());self.assertTrue(data['requires_human_review'])
            self.assertTrue(all(s['proposed_status']=='inferred' and s['observation_time'] is None for s in data['sources']))
            self.assertEqual((folder/'import-review.json').stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):review(db,folder)
    def test_conversation_document_is_rejected_before_body_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'synthetic.sqlite';c=sqlite3.connect(db)
            c.executescript("CREATE TABLE docs(id,title,body,kind,source,updated,fingerprint,space);CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,title,body);")
            c.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?)',('id','title','Toi: S19 Hydro\nChatGPT: answer','ChatGPT','synthetic',1,'hash','user'))
            c.execute('INSERT INTO search VALUES(?,?,?)',('id','title','S19 Hydro'));c.commit();c.close()
            with self.assertRaisesRegex(PermissionError,'turn-level'):review(db,Path(tmp)/'blocked')
            self.assertFalse((Path(tmp)/'blocked/import-review.json').exists())
    def test_explicit_turn_selection_is_bounded_revision_checked_and_owner_bound(self):
        from .local_review import review_selected_turns
        with self.assertRaises(ValueError):review_selected_turns('/missing',[{}]*21,'/unused')
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'synthetic.sqlite';c=sqlite3.connect(db)
            c.executescript('CREATE TABLE conversation_sessions(id,space);CREATE TABLE conversation_turns(session_id,turn,revision,user,assistant,updated);')
            c.execute('INSERT INTO conversation_sessions VALUES(?,?)',('one','user'))
            c.execute('INSERT INTO conversation_turns VALUES(?,?,?,?,?,?)',('one',1,3,'S19 Hydro','synthetic answer',1700000000))
            c.commit();c.close();ref={'session_id':'one','turn':1,'revision':3}
            self.assertEqual(review_selected_turns(db,[ref],Path(tmp)/'ok')['examined_turns'],1)
            with self.assertRaises(PermissionError):review_selected_turns(db,[{**ref,'revision':2}],Path(tmp)/'stale')
            c=sqlite3.connect(db);c.execute("UPDATE conversation_sessions SET space='other'");c.commit();c.close()
            with self.assertRaises(PermissionError):review_selected_turns(db,[ref],Path(tmp)/'denied')

    def test_bounds_before_source_open(self):
        with self.assertRaises(ValueError):review('/does-not-exist','/unused',limit=21)
        with self.assertRaises(ValueError):review('/does-not-exist','/unused',scope='other')

    def test_twenty_turns_including_exclusions_are_not_backfilled(self):
        from .local_review import review_selected_turns
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'fixture.sqlite';c=sqlite3.connect(db)
            c.executescript('CREATE TABLE conversation_sessions(id,space);CREATE TABLE conversation_turns(session_id,turn,revision,user,assistant,updated);')
            c.execute('INSERT INTO conversation_sessions VALUES(?,?)',('s','user'))
            for n in range(25):
                c.execute('INSERT INTO conversation_turns VALUES(?,?,?,?,?,?)',
                          ('s',n,1,'S19 Hydro' if n<19 else 'Mission Codex JARVIS 2.0','synthetic',1))
            c.commit();c.close();before=hashlib.sha256(db.read_bytes()).hexdigest()
            refs=[{'session_id':'s','turn':n,'revision':1} for n in range(20)]
            folder=Path(tmp)/'twenty';result=review_selected_turns(db,refs,folder)
            self.assertEqual(result['examined_turns'],20)
            report=json.loads((folder/'import-review.json').read_text())
            self.assertEqual(len(report['sources']),20)
            self.assertEqual(report['sources'][-1]['review_state'],'possible_meta_project_instructions')
            self.assertEqual(before,hashlib.sha256(db.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError):review_selected_turns(db,refs,folder)
            with self.assertRaises(ValueError):review_selected_turns('/missing',refs+[{'session_id':'s','turn':20,'revision':1}],Path(tmp)/'too-many')
            with self.assertRaises(ValueError):review_selected_turns('/missing',[refs[0],{**refs[0],'revision':2}],Path(tmp)/'duplicate')

    def test_preflight_all_references_before_any_content_projection(self):
        from .local_review import review_selected_turns
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'fixture.sqlite';c=sqlite3.connect(db)
            c.executescript('CREATE TABLE conversation_sessions(id,space);CREATE TABLE conversation_turns(session_id,turn,revision,user,assistant,updated);')
            c.execute('INSERT INTO conversation_sessions VALUES(?,?)',('s','user'))
            c.execute('INSERT INTO conversation_turns VALUES(?,?,?,?,?,?)',('s',0,1,'synthetic','synthetic',1))
            c.commit();c.close()
            connect=sqlite3.connect;projections=[]
            def monitored(*a,**kw):
                conn=connect(*a,**kw)
                def authorize(action,table,column,*unused):
                    if action==sqlite3.SQLITE_READ and table=='conversation_turns' and column in ('user','assistant'):
                        projections.append(column)
                    return sqlite3.SQLITE_OK
                conn.set_authorizer(authorize);return conn
            refs=[{'session_id':'s','turn':0,'revision':1},{'session_id':'s','turn':1,'revision':1}]
            with patch('memory_manager.phase5c.local_review.sqlite3.connect',side_effect=monitored):
                with self.assertRaises(PermissionError):review_selected_turns(db,refs,Path(tmp)/'stale')
            self.assertEqual(projections,[])


if __name__=='__main__':unittest.main()
