# ruff: noqa
def f_text(p):
    p.write_text("x")


def f_bytes(p):
    p.write_bytes(b"x")
