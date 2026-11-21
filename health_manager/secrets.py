"""DPAPI: persistent keys are bound to the current Windows user."""
import ctypes
from ctypes import wintypes
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def transform(data, decrypt=False):
    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dest = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dest))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(src), "AI Health Manager", None, None, None, 1, ctypes.byref(dest))
    if not ok:
        raise OSError("Windows 无法读取或保存密钥，请重新输入")
    try:
        return ctypes.string_at(dest.pbData, dest.cbData)
    finally:
        kernel.LocalFree(dest.pbData)


def save_key(path, key):
    path = Path(path)
    if not key:
        path.unlink(missing_ok=True)
        return
    encrypted = transform(key.encode())
    temp = path.with_suffix(".tmp")
    temp.write_bytes(encrypted)
    temp.replace(path)


def load_key(path):
    path = Path(path)
    if not path.exists():
        return ""
    return transform(path.read_bytes(), decrypt=True).decode()
