# ruff: noqa
def outer():
    x = 0
    def inner():
        nonlocal x
        x = x + 1  # ClosureCaptureMutation on the inner function
    return inner
