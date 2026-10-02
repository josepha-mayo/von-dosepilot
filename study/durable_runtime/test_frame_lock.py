from pathlib import Path
import os
import tempfile
import unittest
from frame_lock import frame_lock

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_same_frame_exclusive(self):
        with frame_lock(self.root,'a'*64):
            with self.assertRaisesRegex(BlockingIOError,'FRAME_BUSY'):
                with frame_lock(self.root,'a'*64):pass
    def test_distinct_frames_do_not_block(self):
        with frame_lock(self.root,'a'*64),frame_lock(self.root,'b'*64):pass
    def test_persistent_filename_not_stale_job(self):
        with frame_lock(self.root,'a'*64):pass
        self.assertTrue((self.root/('a'*64+'.transaction.lock')).exists())
        with frame_lock(self.root,'a'*64):pass
    def test_invalid_id(self):
        for frame in ['../wrong','A'*64,'a'*63,None]:
            with self.subTest(frame=frame),self.assertRaises(ValueError):
                with frame_lock(self.root,frame):pass
    def test_symlink_root_rejected(self):
        p=self.root/'link';p.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):
            with frame_lock(p,'a'*64):pass
    def test_symlink_or_linked_lock_rejected(self):
        target=self.root/'real';target.write_text('not evidence')
        lock=self.root/('a'*64+'.transaction.lock');lock.symlink_to(target)
        with self.assertRaises(OSError):
            with frame_lock(self.root,'a'*64):pass
        lock.unlink();os.link(target,lock)
        with self.assertRaises(ValueError):
            with frame_lock(self.root,'a'*64):pass
if __name__=='__main__':unittest.main(verbosity=2)
