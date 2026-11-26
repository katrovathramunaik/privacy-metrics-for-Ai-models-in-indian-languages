import sqlite3
conn = sqlite3.connect('results/runs.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM runs').fetchall()
for row in rows:
    print(dict(row))
conn.close()