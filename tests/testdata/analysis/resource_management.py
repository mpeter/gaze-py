"""Fixture: ResourceManagement — generic context-manager acquisition."""


def read_config(p):
    with open(p) as f:
        return f.read()


class Svc:
    async def fetch(self, client):
        async with client.session() as s:
            return s
