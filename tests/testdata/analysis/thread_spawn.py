# ruff: noqa
import threading
def spawn_worker(fn):
    t = threading.Thread(target=fn)
    t.start()
