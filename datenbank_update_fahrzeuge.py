import sqlite3

verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS fahrzeuge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schluessel TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tuev_termin TEXT,
    sp_termin TEXT,
    kennzeichen TEXT,
    schlauchwechsel TEXT
)
""")

standard_fahrzeuge = [
    ("tlf", "Tanklöschfahrzeug"),
    ("lf", "Löschgruppenfahrzeug"),
    ("schlauchanhaenger", "Schlauchanhänger"),
    ("ts", "Tragkraftspritzenanhänger"),
    ("boot", "Boot-Anhänger")
]

for schluessel, name in standard_fahrzeuge:
    try:
        cursor.execute(
            "INSERT INTO fahrzeuge (schluessel, name) VALUES (?, ?)",
            (schluessel, name)
        )
    except sqlite3.IntegrityError:
        pass

verbindung.commit()
verbindung.close()

print("Tabelle 'fahrzeuge' wurde erstellt und Standardfahrzeuge wurden eingefügt.")
