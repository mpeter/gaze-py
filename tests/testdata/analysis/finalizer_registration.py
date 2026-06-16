# ruff: noqa
import weakref

def f(obj, cb):
    weakref.finalize(obj, cb)
