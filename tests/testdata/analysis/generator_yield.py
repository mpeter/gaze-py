"""Fixture: GeneratorYield — sync generator functions."""


def gen_numbers(n):
    for i in range(n):
        yield i


def delegate(src):
    yield from src
