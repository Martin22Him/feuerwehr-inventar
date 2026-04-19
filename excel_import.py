import sqlite3
import pandas as pd

DATEINAME = "Inventarliste-Tanker-vereinfacht.xlsx"

# Excel-Datei laden
df = pd.read_excel(DATEINAME)

# Fehlende Werte durch leere Strings ersetzen
df = df.fillna("")

# Verbindung zur Datenbank herstellen
verbindung = sqlite3.connect("inventar.db")
cursor = verbindung.cursor()

# Optional: alte Daten löschen, damit nicht doppelt importiert wird
cursor.execute("DELETE FROM geraete")

# Daten importieren
for _, zeile in df.iterrows():
    cursor.execute("""
        INSERT INTO geraete (
            interne_nummer,
            name,
            kategorie,
            fahrzeug,
            fachnummer,
            pruefdatum,
            ablaufdatum,
            anzahl,
            bemerkung,
            hersteller,
            barcode
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(zeile.get("Interne Nummer", "")),
        str(zeile.get("Name", "")),
        str(zeile.get("Kategorie", "")),
        str(zeile.get("Fahrzeug", "")),
        str(zeile.get("Fachnummer", "")),
        str(zeile.get("Prüfdatum", "")),
        str(zeile.get("Ablaufdatum", "")),
        int(zeile.get("Anzahl", 0)) if str(zeile.get("Anzahl", "")).strip() != "" else 0,
        str(zeile.get("Bemerkung", "")),
        str(zeile.get("Hersteller", "")),
        str(zeile.get("Barcode", ""))
    ))

verbindung.commit()
verbindung.close()

print("Excel-Daten wurden in die Datenbank importiert.")