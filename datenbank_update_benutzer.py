import sqlite3
from pathlib import Path

BASIS_ORDNER = Path(__file__).resolve().parent
DATENBANK = BASIS_ORDNER / "inventar.db"

verbindung = sqlite3.connect(DATENBANK)
cursor = verbindung.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

verbindung.commit()
verbindung.close()

print("Tabelle 'users' wurde angelegt.")