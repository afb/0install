"""
Useful support routines (for internal use).

These functions aren't really Zero Install specific; they're things we might
wish were in the standard library.

@since: 0.27
"""

# Copyright (C) 2009, Thomas Leonard
# See the README file for details, or visit http://0install.net.

from zeroinstall import _, logger
import sys, os

def find_in_path(prog):
	"""Search $PATH for prog.
	If prog is an absolute path, return it unmodified.
	@param prog: name of executable to find
	@type prog: str
	@return: the full path of prog, or None if not found
	@rtype: str
	@since: 0.27"""
	if os.path.isabs(prog): return prog
	if os.name == "nt":
		prog += '.exe'
	for d in os.environ.get('PATH', '/bin:/usr/bin').split(os.pathsep):
		path = os.path.join(d, prog)
		if os.path.isfile(path):
			return path
	return None

def read_bytes(fd, nbytes, null_ok = False):
	"""Read exactly nbytes from fd.
	@param fd: file descriptor to read from
	@type fd: int
	@param nbytes: number of bytes to read
	@type nbytes: int
	@param null_ok: if True, it's OK to receive EOF immediately (we then return None)
	@type null_ok: bool
	@return: the bytes read
	@rtype: bytes
	@raise Exception: if we received less than nbytes of data"""
	data = b''
	while nbytes:
		got = os.read(fd, nbytes)
		if not got:
			if null_ok and not data:
				return None
			raise Exception(_("Unexpected end-of-stream. Data so far %(data)s; expecting %(bytes)d bytes more.")
					% {'data': repr(data), 'bytes': nbytes})
		data += got
		nbytes -= len(got)
	logger.debug(_("Message received: %r"), data)
	return data

def pretty_size(size):
	"""Format a size for printing.
	@param size: the size in bytes
	@type size: int (or None)
	@return: the formatted size
	@rtype: str
	@since: 0.27"""
	if size is None:
		return '?'
	if size < 2048:
		return _('%d bytes') % size
	size = float(size)
	for unit in (_('KB'), _('MB'), _('GB'), _('TB')):
		size /= 1024
		if size < 2048:
			break
	return _('%(size).1f %(unit)s') % {'size': size, 'unit': unit}

def ro_rmtree(root):
	"""Like shutil.rmtree, except that we also delete read-only items.
	@param root: the root of the subtree to remove
	@type root: str
	@since: 0.28"""
	import shutil
	import platform
	if (os.getcwd() + os.path.sep).startswith(root + os.path.sep):
		import warnings
		warnings.warn("Removing tree ({tree}) containing the current directory ({cwd}) - this will not work on Windows".format(cwd = os.getcwd(), tree = root), stacklevel = 2)

	if os.path.isfile(root):
		os.chmod(root, 0o700)
		os.remove(root)
	else:
		if platform.system() == 'Windows':
			for main, dirs, files in os.walk(root):
				for i in files + dirs:
					os.chmod(os.path.join(main, i), 0o700)
			os.chmod(root, 0o700)
		else:
			for main, dirs, files in os.walk(root):
				os.chmod(main, 0o700)
		shutil.rmtree(root)

def raise_with_traceback(ex, tb):
	"""Raise an exception in a way that works on Python 2 and Python 3
	@type ex: BaseException"""
	if hasattr(ex, 'with_traceback'):
		raise ex					# Python 3
	exec("raise ex, None, tb", {'ex': ex, 'tb': tb})	# Python 2
	assert 0

def portable_rename(src, dst):
	"""Rename 'src' to 'dst', which must be on the same filesystem.
	On POSIX systems, this operation is atomic.
	On Windows, do the best we can by deleting dst and then renaming.
	@type src: str
	@type dst: str
	@since: 1.9"""
	if os.name == "nt" and os.path.exists(dst):
		os.unlink(dst)
	os.rename(src, dst)

if sys.version_info[0] > 2:
	# Python 3
	unicode = str
	intern = sys.intern
	raw_input = input

else:
	# Python 2
	unicode = unicode		# (otherwise it can't be imported)
	intern = intern
	raw_input = raw_input
