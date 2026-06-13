# ruff: noqa
def process(data):
    result = None
    try:
        result = data
    finally:
        result = str(data)  # finally assignment
    return result  # return is OUTSIDE finally
