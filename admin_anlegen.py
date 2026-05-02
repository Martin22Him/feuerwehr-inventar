import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASIS_ORDNER = Path(__file__).resolve().parent
DATENBANK = BASIS_ORDNER / "inventar.db"

username = os.environ.get("ADMIN_USERNAME", "admin")
password = os.environ.get("ADMIN_PASSWORD")

if not password:
    raise ValueError("ADMIN_PASSWORD ist nicht gesetzt.")

password_hash = generate_password_hash(password)

verbindung = sqlite3.connect(DATENBANK)
cursor = verbindung.cursor()

cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
vorhanden = cursor.fetchone()

if vorhanden:
    print(f"Benutzer '{username}' existiert bereits.")
else:
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, "admin")
    )
    verbindung.commit()
    print(f"Admin-Benutzer '{username}' wurde angelegt.")

verbindung.close()