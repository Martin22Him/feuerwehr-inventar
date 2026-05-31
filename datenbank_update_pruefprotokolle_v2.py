import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL ist nicht gesetzt.")

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("""
        ALTER TABLE pruefprotokolle
        ADD COLUMN IF NOT EXISTS pruefer TEXT
    """))

    conn.execute(text("""
        ALTER TABLE pruefprotokolle
        ADD COLUMN IF NOT EXISTS wehr_id INTEGER
    """))

    conn.execute(text("""
        UPDATE pruefprotokolle p
        SET wehr_id = g.wehr_id
        FROM geraete g
        WHERE p.wehr_id IS NULL
          AND p.geraet_id = g.id
    """))

print("Prüfprotokolle wurden um pruefer und wehr_id erweitert.")