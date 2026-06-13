# ruff: noqa
def save(path, content):
    with open(path, 'w') as f:
        f.write(content)
