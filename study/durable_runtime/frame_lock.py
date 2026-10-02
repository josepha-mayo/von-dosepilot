"""Local POSIX advisory serialization for one DosePilot measurement frame.

Locks coordinate this runtime's cooperating processes. They cannot stop a user
or another program from manually editing the filesystem. Persistent .lock names
are arbitration files, not evidence and not stale jobs. Kernel locks are released
when their owning process exits, so a killed worker needs no lock-file deletion.
"""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat


@contextmanager
def frame_lock(directory, frame):
    if os.name != 'posix':
        raise OSError('LOCAL_POSIX_FRAME_LOCK_REQUIRED')
    import fcntl
    if (not isinstance(frame, str) or len(frame) != 64
            or any(ch not in '0123456789abcdef' for ch in frame)):
        raise ValueError('INVALID_FRAME_ID')
    dfd = os.open(Path(directory), os.O_RDONLY|os.O_DIRECTORY|getattr(os, 'O_NOFOLLOW', 0))
    fd = None
    acquired = False
    try:
        fd = os.open(frame+'.transaction.lock', os.O_RDWR|os.O_CREAT|
                     getattr(os, 'O_NOFOLLOW', 0), 0o600, dir_fd=dfd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('LOCK_MUST_BE_SINGLE_REGULAR_FILE')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise BlockingIOError('FRAME_BUSY_RETRY_LATER') from exc
            raise
        yield
    finally:
        if fd is not None:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        os.close(dfd)
