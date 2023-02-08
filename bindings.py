import ctypes
import ctypes.util
import os

libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)
libc.umount.argtypes = (ctypes.c_char_p, ctypes.c_int)
libc.unshare.argtypes = [ctypes.c_int]

# C binding to create an overlay mount
def overlay_mount(target: str, options: str):
  ret = libc.mount(None, target.encode(), "overlay".encode(), 0, options.encode())
  if ret < 0:
    errno = ctypes.get_errno()
    raise OSError(errno, f"Error mounting overlay on {target} with options '{options}': {os.strerror(errno)}")

def proc_mount():
  ret = libc.mount("proc".encode(), "/proc".encode(), "proc".encode(), 0, "".encode())
  if ret < 0:
    errno = ctypes.get_errno()
    raise OSError(errno, f"Error mounting proc")

# C binding for umount
def umount(fs: str):
  ret = libc.umount(fs.encode(), 0)
  if ret < 0:
    errno = ctypes.get_errno()
    raise OSError(errno, f"Error unmounting {fs}")

# C binding for unshare
def unshare(flags: int):
  ret = libc.unshare(flags)
  if ret < 0:
    errno = ctypes.get_errno()
    raise OSError(errno, f"Error unsharing with flags {flags}")