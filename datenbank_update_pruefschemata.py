import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt.")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pruefschemata (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            kategorie TEXT NOT NULL,
            beschreibung TEXT,
            aktiv INTEGER NOT NULL DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pruefpunkte (
            id SERIAL PRIMARY KEY,
            schema_id INTEGER NOT NULL REFERENCES pruefschemata(id) ON DELETE CASCADE,
            sortierung INTEGER NOT NULL DEFAULT 0,
            pruefpunkt TEXT NOT NULL,
            hinweis TEXT,
            pflichtfeld INTEGER NOT NULL DEFAULT 1
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pruefprotokolle (
            id SERIAL PRIMARY KEY,
            geraet_id INTEGER NOT NULL,
            schema_id INTEGER,
            pruefdatum TEXT,
            ablaufdatum TEXT,
            pruefstelle TEXT,
            ergebnis TEXT,
            bemerkung TEXT,
            pdf_url TEXT,
            pdf_dateiname TEXT,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pruefpunkt_ergebnisse (
            id SERIAL PRIMARY KEY,
            protokoll_id INTEGER NOT NULL REFERENCES pruefprotokolle(id) ON DELETE CASCADE,
            pruefpunkt_id INTEGER,
            pruefpunkt_text TEXT NOT NULL,
            status TEXT NOT NULL,
            bemerkung TEXT
        )
    """))

print("Prüfschema-Tabellen wurden angelegt.")