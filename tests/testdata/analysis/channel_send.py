# ruff: noqa
def send(q, item):
    q.put(item)
