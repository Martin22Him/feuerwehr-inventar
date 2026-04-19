import sqlite3

verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pruefhistorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    geraet_id INTEGER NOT NULL,
    pruefdatum TEXT,
    ablaufdatum TEXT,
    pruefstelle TEXT,
    bemerkung TEXT,
    erstellt_am TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (geraet_id) REFERENCES geraete(id)
)
""")

verbindung.commit()
verbindung.close()

print("Tabelle 'pruefhistorie' wurde erstellt.")