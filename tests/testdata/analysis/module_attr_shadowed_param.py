# ruff: noqa
import os


def not_a_module_mutation(os):
    os.getcwd = lambda: "/fake"
