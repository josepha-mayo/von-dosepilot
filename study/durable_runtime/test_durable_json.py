import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from durable_json import write_new

HERE=Path(__file__).resolve().parent
VALUE={'schema':'fictional_receipt','items':[{'id':f'q{i}','value':'v'*600} for i in range(64)]}
PHASES=('temporary_created','first_chunk_written','data_written','file_synced','published','directory_synced','cleaned')

class Tests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'receipt.json'
    def tearDown(self):self.temp.cleanup()
    def test_matches_original_serialization(self):
        write_new(self.path,VALUE)
        self.assertEqual(self.path.read_bytes(),(json.dumps(VALUE,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())
    def test_exclusive_no_overwrite(self):
        write_new(self.path,VALUE);before=self.path.read_bytes()
        with self.assertRaises(FileExistsError):write_new(self.path,{'wrong':1})
        self.assertEqual(self.path.read_bytes(),before)
    def test_invalid_json_no_files(self):
        with self.assertRaises(ValueError):write_new(self.path,{'bad':float('nan')})
        self.assertEqual(list(self.root.iterdir()),[])
    def test_missing_parent_rejected(self):
        with self.assertRaises(OSError):write_new(self.root/'absent'/'receipt.json',VALUE)
        self.assertFalse((self.root/'absent').exists())
    def test_symlink_target_does_not_overwrite(self):
        victim=self.root/'other';victim.write_text('unchanged');self.path.symlink_to(victim)
        with self.assertRaises(FileExistsError):write_new(self.path,VALUE)
        self.assertEqual(victim.read_text(),'unchanged')
    def test_symlink_parent_rejected(self):
        target=self.root/'actual';target.mkdir();alias=self.root/'link';alias.symlink_to(target,target_is_directory=True)
        with self.assertRaises(OSError):write_new(alias/'receipt.json',VALUE)
        self.assertEqual(list(target.iterdir()),[])
    def test_interruption_at_each_phase(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                folder=self.root/phase;folder.mkdir();p=folder/'receipt.json'
                result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'child',str(p),phase],cwd=HERE,capture_output=True,timeout=10)
                self.assertEqual(result.returncode,73,result.stderr.decode())
                if phase in PHASES[:4]:
                    self.assertFalse(p.exists());write_new(p,VALUE)
                else:
                    self.assertEqual(json.loads(p.read_bytes()),VALUE)
                    with self.assertRaises(FileExistsError):write_new(p,VALUE)
                self.assertEqual(json.loads(p.read_bytes()),VALUE)
    def test_simultaneous_writers_only_one_wins(self):
        children=[]
        for i in range(8):
            children.append(subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'race',str(self.path),str(i)],cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        results=[]
        for p in children:
            p.communicate(timeout=15);results.append(p.returncode)
        self.assertEqual(results.count(0),1);self.assertEqual(results.count(17),7)
        result=json.loads(self.path.read_text());self.assertIn(result['writer'],range(8));self.assertEqual(result['payload'],VALUE)
        self.assertFalse(list(self.root.glob('.dosepilot-pending-*')))
    def test_late_competing_destination_not_overwritten(self):
        def hook(phase):
            if phase=='file_synced':self.path.write_text('{"winner":"other"}')
        with self.assertRaises(FileExistsError):write_new(self.path,VALUE,_checkpoint=hook)
        self.assertEqual(json.loads(self.path.read_text()),{'winner':'other'})
    def test_cleanup_not_other_pending_file(self):
        other=self.root/'.dosepilot-pending-other';other.write_text('belongs to other process')
        write_new(self.path,VALUE);self.assertEqual(other.read_text(),'belongs to other process')
    def test_fail_before_publication_exposes_nothing(self):
        def hook(phase):
            if phase=='file_synced':raise OSError('simulated')
        with self.assertRaises(OSError):write_new(self.path,VALUE,_checkpoint=hook)
        self.assertFalse(self.path.exists());self.assertFalse(list(self.root.glob('.dosepilot-pending-*')))
    def test_fail_after_publication_remains_complete(self):
        def hook(phase):
            if phase=='published':raise OSError('simulated')
        with self.assertRaises(OSError):write_new(self.path,VALUE,_checkpoint=hook)
        self.assertEqual(json.loads(self.path.read_text()),VALUE)
    def test_success_has_private_permissions(self):
        write_new(self.path,VALUE);self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='child':
        p,phase=Path(sys.argv[2]),sys.argv[3]
        def stop(at):
            if at==phase:os._exit(73)
        write_new(p,VALUE,_checkpoint=stop)
        raise SystemExit(4)
    elif len(sys.argv)>1 and sys.argv[1]=='race':
        try:write_new(Path(sys.argv[2]),{'writer':int(sys.argv[3]),'payload':VALUE})
        except FileExistsError:raise SystemExit(17)
    else:unittest.main(verbosity=2)
