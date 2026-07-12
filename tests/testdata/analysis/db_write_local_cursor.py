# ruff: noqa
import sqlite3


def save_many(db_path, rows):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executemany("INSERT INTO t VALUES (?)", rows)
