# ruff: noqa
import os


def patch_getcwd():
    os.getcwd = lambda: "/fake"
