# ruff: noqa
def complex_func(x, y, z, flag, mode):
    if x > 0:
        if y > 0:
            result = x + y
        elif z > 0:
            result = x + z
        else:
            result = x
    elif flag:
        for i in range(x):
            if i % 2 == 0:
                result = i
            else:
                result = -i
    else:
        while z > 0:
            z -= 1
            if z == 5:
                break
        result = z
    return result
