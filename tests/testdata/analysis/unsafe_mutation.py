# ruff: noqa
"""Fixture for UnsafeMutation detection."""
import ctypes


def write_ptr_subscript(ptr: ctypes.c_char_p) -> None:
    """Subscript write on ptr — UnsafeMutation."""
    ptr[0] = 0xFF


def write_buf_subscript(buf: ctypes.c_char_p) -> None:
    """Subscript write on buf — UnsafeMutation."""
    buf[0] = 0x00


def write_p_name_subscript(p_data: ctypes.c_char_p) -> None:
    """Subscript write on p_ name — UnsafeMutation."""
    p_data[0] = 0x42


def write_contents(mem: ctypes.Structure) -> None:
    """Attribute .contents write — UnsafeMutation."""
    mem.contents = ctypes.c_int(42)


def safe_list_write(items: list) -> None:
    """List subscript write — NOT UnsafeMutation."""
    items[0] = 42
