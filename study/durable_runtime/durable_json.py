"""Create-exclusive JSON publication without a partially written final name.

POSIX local-filesystem implementation. Successful publication flushes file data
and the containing directory. OS/device durability guarantees still apply;
process-interruption tests are not physical power-loss certification.
"""
from __future__ import annotations
import errno
import json
import os
from pathlib import Path
import secrets


def write_new(path, value, *, _checkpoint=None):
    """Publish complete UTF-8 JSON, never replace an existing destination.

    `_checkpoint` is an in-process fault-injection seam for tests, not a CLI or
    environment option. Pending files from a killed process are not evidence.
    """
    if os.name != 'posix' or not hasattr(os, 'O_DIRECTORY'):
        raise OSError('DURABLE_PUBLICATION_UNSUPPORTED: POSIX directory sync required')
    destination = Path(path)
    if destination.name in ('', '.', '..'):
        raise ValueError('Invalid output filename')
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    directory = destination.parent
    dflags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, 'O_NOFOLLOW', 0)
    dfd = os.open(directory, dflags)
    temporary = '.dosepilot-pending-' + secrets.token_hex(16)
    fd = None
    published = False
    def point(name):
        if _checkpoint is not None:
            _checkpoint(name)
    try:
        # Refuse early when possible, but rely on atomic link exclusivity at
        # publication, not this inherently racy observation.
        try:
            os.stat(destination.name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(errno.EEXIST, 'OUTPUT_EXISTS', str(destination))
        fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                     getattr(os, 'O_NOFOLLOW', 0), 0o600, dir_fd=dfd)
        point('temporary_created')
        view = memoryview(payload)
        first = True
        while view:
            count = os.write(fd, view[:4096])
            if count <= 0:
                raise OSError('Incomplete staged write')
            view = view[count:]
            if first:
                first = False
                point('first_chunk_written')
        point('data_written')
        os.fsync(fd)
        point('file_synced')
        os.close(fd); fd = None
        # Same-directory hard link is atomic and cannot clobber a winner.
        # os.replace is deliberately not used: it could replace evidence.
        os.link(temporary, destination.name, src_dir_fd=dfd, dst_dir_fd=dfd,
                follow_symlinks=False)
        published = True
        point('published')
        os.fsync(dfd)
        point('directory_synced')
        os.unlink(temporary, dir_fd=dfd)
        os.fsync(dfd)
        point('cleaned')
    finally:
        if fd is not None:
            os.close(fd)
        # Best-effort cleanup is only for this invocation's unique staging
        # name. Never enumerate or delete another process's pending files.
        try:
            os.unlink(temporary, dir_fd=dfd)
            os.fsync(dfd)
        except FileNotFoundError:
            pass
        finally:
            os.close(dfd)
