import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt.")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("""
        ALTER TABLE geraete
        ADD COLUMN IF NOT EXISTS fahrzeug_id INTEGER
    """))

    # Bestehende Geräte anhand alter Textwerte zuordnen.
    # Vergleich 1: geraete.fahrzeug = fahrzeuge.name
    conn.execute(text("""
        UPDATE geraete g
        SET fahrzeug_id = f.id
        FROM fahrzeuge f
        WHERE g.fahrzeug_id IS NULL
          AND g.wehr_id = f.wehr_id
          AND LOWER(TRIM(g.fahrzeug)) = LOWER(TRIM(f.name))
    """))

    # Vergleich 2: geraete.fahrzeug = fahrzeuge.schluessel
    conn.execute(text("""
        UPDATE geraete g
        SET fahrzeug_id = f.id
        FROM fahrzeuge f
        WHERE g.fahrzeug_id IS NULL
          AND g.wehr_id = f.wehr_id
          AND LOWER(TRIM(g.fahrzeug)) = LOWER(TRIM(f.schluessel))
    """))

    # Vergleich 3: geraete.fahrzeug = UPPER(fahrzeuge.schluessel)
    conn.execute(text("""
        UPDATE geraete g
        SET fahrzeug_id = f.id
        FROM fahrzeuge f
        WHERE g.fahrzeug_id IS NULL
          AND g.wehr_id = f.wehr_id
          AND LOWER(TRIM(g.fahrzeug)) = LOWER(TRIM(UPPER(f.schluessel)))
    """))

print("geraete.fahrzeug_id wurde ergänzt und bestehende Geräte wurden soweit möglich zugeordnet.")