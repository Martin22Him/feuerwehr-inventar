import sqlite3

verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

# Spalte pruefstatus hinzufügen
try:
    cursor.execute("ALTER TABLE geraete ADD COLUMN pruefstatus TEXT DEFAULT 'frei'")
    print("Spalte 'pruefstatus' wurde hinzugefügt.")
except sqlite3.OperationalError:
    print("Spalte 'pruefstatus' existiert bereits.")

# Spalte pruefstelle hinzufügen
try:
    cursor.execute("ALTER TABLE geraete ADD COLUMN pruefstelle TEXT")
    print("Spalte 'pruefstelle' wurde hinzugefügt.")
except sqlite3.OperationalError:
    print("Spalte 'pruefstelle' existiert bereits.")

# Spalte pruefauftrag_datum hinzufügen
try:
    cursor.execute("ALTER TABLE geraete ADD COLUMN pruefauftrag_datum TEXT")
    print("Spalte 'pruefauftrag_datum' wurde hinzugefügt.")
except sqlite3.OperationalError:
    print("Spalte 'pruefauftrag_datum' existiert bereits.")

verbindung.commit()
verbindung.close()

print("Datenbank wurde für Prüfstatus erweitert.")