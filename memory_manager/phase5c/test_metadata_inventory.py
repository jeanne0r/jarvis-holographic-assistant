"""Synthetic metadata fixtures; no personal source access."""
import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from .metadata_inventory import inventory,authorize


class Inventory(unittest.TestCase):
    def test_twenty_metadata_references_without_any_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'synthetic.sqlite';c=sqlite3.connect(db)
            c.executescript('CREATE TABLE docs(id,space,title,kind,updated,body);CREATE TABLE conversation_sessions(id,space,created,channel);CREATE TABLE conversation_turns(session_id,turn,revision,updated,status,user,assistant);')
            c.execute('INSERT INTO conversation_sessions VALUES(?,?,?,?)',('fixture','user',1700000000,'written'))
            for n in range(24):
                c.execute('INSERT INTO docs VALUES(?,?,?,?,?,?)',(f'jarvis:fixture:{n}','user','S19 Hydro','Jarvis',1700000000,'PRIVATE-BODY-SENTINEL'))
                c.execute('INSERT INTO conversation_turns VALUES(?,?,?,?,?,?,?)',('fixture',n,2,1700000000+n,'complete','PRIVATE-USER-SENTINEL','PRIVATE-ASSISTANT-SENTINEL'))
            c.execute('INSERT INTO docs VALUES(?,?,?,?,?,?)',('export','user','S19 Hydro','ChatGPT',1,'PRIVATE-EXPORT-SENTINEL'))
            c.commit();c.close();before=hashlib.sha256(db.read_bytes()).hexdigest()
            folder=Path(tmp)/'private';r=inventory(db,folder)
            self.assertEqual(r['proposed_turns'],20);self.assertEqual(r['metadata_matched_documents'],25)
            output=(folder/'inventory.json').read_text();self.assertNotIn('SENTINEL',output)
            rows=json.loads(output)['proposed_turns'];self.assertEqual(rows[0]['turn'],23)
            self.assertEqual(before,hashlib.sha256(db.read_bytes()).hexdigest())
            self.assertEqual((folder/'SELECTION.md').stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):inventory(db,folder)
    def test_authorizer_denies_bodies_indexes_and_writes(self):
        for table,column in [('docs','body'),('conversation_turns','user'),('conversation_turns','assistant'),('search','title')]:
            self.assertEqual(authorize(sqlite3.SQLITE_READ,table,column),sqlite3.SQLITE_DENY)
        self.assertEqual(authorize(sqlite3.SQLITE_UPDATE,'docs','title'),sqlite3.SQLITE_DENY)
        self.assertEqual(authorize(sqlite3.SQLITE_READ,'docs','title'),sqlite3.SQLITE_OK)

if __name__=='__main__':unittest.main()
