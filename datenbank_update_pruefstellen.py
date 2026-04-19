import sqlite3

verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

# Tabelle erstellen
cursor.execute("""
CREATE TABLE IF NOT EXISTS pruefstellen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
""")

# Standard-Prüfstellen einfügen
standard_pruefstellen = [
    "Gerätewart FF-Jesewitz",
    "FF-Eilenburg",
    "FTZ-Trebsen",
    "Externe Prüfstelle"
]

for stelle in standard_pruefstellen:
    try:
        cursor.execute("INSERT INTO pruefstellen (name) VALUES (?)", (stelle,))
    except sqlite3.IntegrityError:
        # existiert bereits
        pass

verbindung.commit()
verbindung.close()

print("Tabelle 'pruefstellen' wurde erstellt und Standardwerte wurden eingefügt.")