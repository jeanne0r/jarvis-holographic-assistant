"""Only offline guard/backup helpers; no root operation, service or provider."""
import importlib.util,json,os,secrets,sqlite3,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'ops/pilot-network/deploy-private-embedded.py'
spec=importlib.util.spec_from_file_location('lot_R_offline',SCRIPT);lot=importlib.util.module_from_spec(spec);spec.loader.exec_module(lot)
class LotRTests(unittest.TestCase):
 def test_nonroot_main_refuses_before_private_reads_or_service_calls(self):
  if os.geteuid()==0:self.skipTest('Nonroot guard test')
  r=subprocess.run([sys.executable,'-B',str(SCRIPT),'--lot-r-approved'],capture_output=True,text=True)
  self.assertEqual(r.returncode,1);self.assertEqual(r.stdout,'')
  result=json.loads(r.stderr);self.assertFalse(result['passed']);self.assertFalse(result['pilot_stop_requested']);self.assertFalse(result['G_executed'])
  self.assertIn('administrator terminal',result['reason'])
 def test_fresh_access_only_changes_auth_and_embedded_profile(self):
  cfg={'bridgeToken':'old','humanHash':'old','expiresAt':1,'syntheticOnly':True,'dispatchEnabled':False,'frontPort':8796,'bridgePort':8797,'missionLimits':{'calls':6}}
  human='A'*43;bridge='B'*43;fresh=lot.fresh_access(cfg,human,bridge,1000)
  self.assertEqual(fresh['humanHash'],lot.sha(human.encode()));self.assertNotIn(human,json.dumps(fresh))
  self.assertEqual(fresh['expiresAt'],int((1000+30*86400)*1000));self.assertEqual(fresh['embeddedPanel']['origin'],'https://192.0.2.16:8788')
  for name in ['syntheticOnly','dispatchEnabled','frontPort','bridgePort','missionLimits']:self.assertEqual(cfg[name],fresh[name])
  self.assertEqual(cfg['bridgeToken'],'old')
  with self.assertRaises(ValueError):lot.fresh_access(cfg,human,human,1000)
 def test_private_replacement_retains_modes_and_rejects_symlink(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'token';p.write_bytes(b'old');p.chmod(0o600)
   lot.replace_private(p,b'fixture-new',os.getuid(),os.getgid());self.assertEqual(p.read_bytes(),b'fixture-new');self.assertEqual(p.stat().st_mode&0o777,0o600)
   link=Path(tmp)/'link';link.symlink_to(p)
   with self.assertRaises(PermissionError):lot.replace_private(link,b'bad',os.getuid(),os.getgid())
   self.assertEqual(p.read_bytes(),b'fixture-new')
 def test_snapshot_restore_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   a,b,c=[Path(tmp)/n for n in ['a.sqlite','b.sqlite','c.sqlite']]
   with sqlite3.connect(a) as db:db.execute('CREATE TABLE fixture(value)');db.execute('INSERT INTO fixture VALUES(1)')
   original=a.read_bytes();lot.snapshot(a,b);lot.snapshot(b,c)
   self.assertEqual(lot.database_dump(a),lot.database_dump(c));self.assertEqual(a.read_bytes(),original)
   with self.assertRaises(FileExistsError):lot.snapshot(a,b)
 def test_switch_and_tree_fail_closed_without_modifying_inputs(self):
  previous=lot.FLAG
  try:
   with tempfile.TemporaryDirectory() as tmp:
    lot.FLAG=Path(tmp)/'flag';self.assertTrue(lot.switch_off())
    lot.FLAG.write_text('{"enabled":false}');lot.FLAG.chmod(0o600);self.assertTrue(lot.switch_off())
    lot.FLAG.write_text('{"enabled":true}');self.assertFalse(lot.switch_off())
    lot.FLAG.write_text('invalid')
    with self.assertRaises(ValueError):lot.switch_off()
    (Path(tmp)/'link').symlink_to(lot.FLAG)
    with self.assertRaises(PermissionError):lot.tree_size(Path(tmp),{os.getuid()})
  finally:lot.FLAG=previous
if __name__=='__main__':unittest.main()
