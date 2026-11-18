"""Real patch/rollback on disposable files; no gateway state or services."""
import hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from scripts.prepare_human_missions import human_assets,prepare

class HumanAssetsTests(unittest.TestCase):
    def test_exact_patch_apply_and_restore_on_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);gateway=root/'gateway';assets=gateway/'public/jarvis';assets.mkdir(parents=True)
            before={'hermes-embedded.js':b'// synthetic previous UI\n','hermes-embedded.css':b'/* synthetic previous CSS */\n'}
            for name,raw in before.items():(assets/name).write_bytes(raw)
            dest=root/'candidate';manifest=prepare(dest,gateway)
            for row in manifest['files']:
                name=row['artifact'];patch=(dest/(name+'.patch')).read_bytes()
                subprocess.run(['git','apply','--check','-'],cwd=gateway,input=patch,check=True,capture_output=True)
                subprocess.run(['git','apply','-'],cwd=gateway,input=patch,check=True,capture_output=True)
                self.assertEqual(row['after_sha256'],hashlib.sha256((assets/name).read_bytes()).hexdigest())
                subprocess.run(['git','apply','--reverse','-'],cwd=gateway,input=patch,check=True,capture_output=True)
                self.assertEqual(before[name],(assets/name).read_bytes())
            with self.assertRaises(FileExistsError):prepare(dest,gateway)

    def test_private_and_unified_use_existing_protocols(self):
        private,_=human_assets();unified,_=human_assets(unified=True)
        self.assertIn('/api/jarvis/hermes-panel/session',private)
        self.assertNotIn('/api/jarvis/hermes-panel/session',unified)
        self.assertIn('const commonAuth=globalThis.JarvisAuth',unified)
        self.assertIn("path==='session'?'session':'hermes-panel/'+path",unified)
        self.assertEqual(unified.count("const dialog=make('dialog',null,document.body);dialog.id='jarvisAccountDialog'"),1)
        for text in [private,unified]:
            self.assertNotIn('innerHTML',text)
            self.assertNotIn('localStorage',text)
            self.assertIn('crypto.randomUUID()',text)
            self.assertIn('hermesOriginalResult',text)

    def test_refuses_symlink_to_active_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);assets=root/'gateway/public/jarvis';assets.mkdir(parents=True)
            target=root/'other';target.write_text('synthetic')
            (assets/'hermes-embedded.js').symlink_to(target)
            with self.assertRaises(PermissionError):prepare(root/'candidate',root/'gateway')
