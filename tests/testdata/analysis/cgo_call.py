# ruff: noqa
import ctypes

def f():
    ctypes.CDLL("lib.so")
