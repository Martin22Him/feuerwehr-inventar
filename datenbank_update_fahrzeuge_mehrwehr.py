import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt.")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("""
        ALTER TABLE fahrzeuge
        ADD COLUMN IF NOT EXISTS id SERIAL
    """))

    conn.execute(text("""
        ALTER TABLE fahrzeuge
        ADD COLUMN IF NOT EXISTS name TEXT
    """))

    conn.execute(text("""
        ALTER TABLE fahrzeuge
        ADD COLUMN IF NOT EXISTS typ TEXT
    """))

    conn.execute(text("""
        ALTER TABLE fahrzeuge
        ADD COLUMN IF NOT EXISTS aktiv INTEGER NOT NULL DEFAULT 1
    """))

    conn.execute(text("""
        UPDATE fahrzeuge
        SET name = schluessel
        WHERE name IS NULL OR name = ''
    """))

    conn.execute(text("""
        UPDATE fahrzeuge
        SET typ = 'fahrzeug'
        WHERE typ IS NULL OR typ = ''
    """))

print("Fahrzeugtabelle wurde erweitert.")