import sqlite3

# Verbindung zur Datenbank herstellen
verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

# Tabelle für Geräte anlegen
cursor.execute("""
CREATE TABLE IF NOT EXISTS geraete (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interne_nummer TEXT,
    name TEXT,
    kategorie TEXT,
    fahrzeug TEXT,
    fachnummer TEXT,
    pruefdatum TEXT,
    ablaufdatum TEXT,
    anzahl INTEGER,
    bemerkung TEXT,
    hersteller TEXT,
    barcode TEXT
)
""")

verbindung.commit()
verbindung.close()

print("Datenbank und Tabelle wurden erstellt.")