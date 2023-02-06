import ctypes
import ctypes.util
import os

libc = ctypes.CDLL(ctypes.util.find_library('c'), use_errno=True)
libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)

# C binding to create an overlay mount
def overlay_mount(target, options):
  ret = libc.mount(None, target.encode(), "overlay".encode(), 0, options.encode())
  if ret < 0:
    errno = ctypes.get_errno()
    raise OSError(errno, f"Error mounting overlay on {target} with options '{options}': {os.strerror(errno)}")