# ruff: noqa
import sqlite3


def save_row(db_path, row):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO t VALUES (?)", row)
    con.commit()
