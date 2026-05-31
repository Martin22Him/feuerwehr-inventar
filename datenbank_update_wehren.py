import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt.")

engine = create_engine(DATABASE_URL)

STANDARD_WEHR_NAME = "Feuerwehr Jesewitz"
STANDARD_WEHR_KUERZEL = "jesewitz"

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS wehren (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            kuerzel TEXT NOT NULL UNIQUE,
            aktiv INTEGER NOT NULL DEFAULT 1,
            erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        INSERT INTO wehren (name, kuerzel, aktiv)
        VALUES (:name, :kuerzel, 1)
        ON CONFLICT (kuerzel) DO NOTHING
    """), {
        "name": STANDARD_WEHR_NAME,
        "kuerzel": STANDARD_WEHR_KUERZEL
    })

    standard_wehr_id = conn.execute(text("""
        SELECT id FROM wehren WHERE kuerzel = :kuerzel
    """), {
        "kuerzel": STANDARD_WEHR_KUERZEL
    }).scalar()

    conn.execute(text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS wehr_id INTEGER
    """))

    conn.execute(text("""
        ALTER TABLE geraete
        ADD COLUMN IF NOT EXISTS wehr_id INTEGER
    """))

    conn.execute(text("""
        ALTER TABLE fahrzeuge
        ADD COLUMN IF NOT EXISTS wehr_id INTEGER
    """))

    conn.execute(text("""
        UPDATE users
        SET wehr_id = :wehr_id
        WHERE wehr_id IS NULL
    """), {
        "wehr_id": standard_wehr_id
    })

    conn.execute(text("""
        UPDATE geraete
        SET wehr_id = :wehr_id
        WHERE wehr_id IS NULL
    """), {
        "wehr_id": standard_wehr_id
    })

    conn.execute(text("""
        UPDATE fahrzeuge
        SET wehr_id = :wehr_id
        WHERE wehr_id IS NULL
    """), {
        "wehr_id": standard_wehr_id
    })

print("Wehr-Struktur wurde angelegt und bestehende Daten wurden Feuerwehr Jesewitz zugeordnet.")