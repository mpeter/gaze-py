# ruff: noqa
def save_record(cursor, sql, params):
    cursor.execute(sql, params)
