import os
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

import pandas as pd
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf import FlaskForm, CSRFProtect
from werkzeug.security import check_password_hash
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

import requests

app = Flask(__name__)

# WICHTIG: SECRET_KEY nicht mehr fest im Code speichern.
# Lokal vor dem Start setzen, z. B. in PowerShell:
# $env:SECRET_KEY="ein-langer-geheimer-zufaelliger-wert"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise ValueError("SECRET_KEY ist nicht gesetzt. Bitte vor dem Start als Umgebungsvariable setzen.")

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
csrf = CSRFProtect(app)
# Lokal auf False lassen. Für Render später SESSION_COOKIE_SECURE=true setzen.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"

BASIS_ORDNER = Path(__file__).resolve().parent
DATENBANK = BASIS_ORDNER / "inventar.db"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USING_POSTGRES = bool(DATABASE_URL)


def hole_db_verbindung():
    """
    Lokal ohne DATABASE_URL: SQLite-Datei inventar.db.
    Online mit DATABASE_URL: PostgreSQL, z. B. Neon/Supabase.
    """
    if USING_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    return verbindung


def db_execute(cursor, sql, params=()):
    """
    Einheitliche SQL-Ausführung für SQLite und PostgreSQL.
    Der bestehende Code nutzt ? als Platzhalter.
    Für PostgreSQL werden diese automatisch zu %s umgewandelt.
    """
    if params is None:
        params = ()

    if USING_POSTGRES:
        sql = sql.replace("?", "%s")

    return cursor.execute(sql, params)


def row_get(row, key, index=0):
    """Wert aus sqlite3.Row, Tupel oder psycopg dict_row lesen."""
    if row is None:
        return None

    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return row[index]


def lese_dataframe(sql, params=()):
    """SQL-Abfrage als DataFrame, kompatibel mit SQLite und PostgreSQL."""
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()
    db_execute(cursor, sql, params)

    daten = cursor.fetchall()
    spalten = [beschreibung[0] for beschreibung in cursor.description] if cursor.description else []

    verbindung.close()

    if not daten:
        return pd.DataFrame(columns=spalten)

    if USING_POSTGRES:
        return pd.DataFrame(daten)

    return pd.DataFrame([dict(zeile) for zeile in daten])


login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Bitte melde dich zuerst an."
login_manager.login_message_category = "warning"
login_manager.init_app(app)


class User(UserMixin):
    def __init__(self, id, username, password_hash, role, is_active):
        self.id = str(id)
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.active_flag = bool(is_active)

    @property
    def is_active(self):
        return self.active_flag


def lade_user_nach_id(user_id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()
    db_execute(cursor, 
        "SELECT id, username, password_hash, role, is_active FROM users WHERE id = ?",
        (user_id,)
    )
    daten = cursor.fetchone()
    verbindung.close()

    if not daten:
        return None

    return User(
        daten["id"],
        daten["username"],
        daten["password_hash"],
        daten["role"],
        daten["is_active"],
    )


def lade_user_nach_username(username):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()
    db_execute(cursor, 
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?",
        (username,)
    )
    daten = cursor.fetchone()
    verbindung.close()

    if not daten:
        return None

    return User(
        daten["id"],
        daten["username"],
        daten["password_hash"],
        daten["role"],
        daten["is_active"],
    )

def initialisiere_datenbank():
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    if USING_POSTGRES:
        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS geraete (
                id SERIAL PRIMARY KEY,
                interne_nummer TEXT,
                name TEXT,
                kategorie TEXT,
                fahrzeug TEXT,
                fachnummer TEXT,
                pruefdatum TEXT,
                ablaufdatum TEXT,
                anzahl INTEGER,
                bemerkung TEXT,
                hersteller TEXT,
                barcode TEXT,
                pruefstatus TEXT DEFAULT 'frei',
                pruefauftrag_datum TEXT,
                pruefstelle TEXT
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS pruefstellen (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS fahrzeuge (
                schluessel TEXT PRIMARY KEY,
                tuev_termin TEXT,
                sp_termin TEXT,
                kennzeichen TEXT,
                schlauchwechsel TEXT
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS pruefhistorie (
                id SERIAL PRIMARY KEY,
                geraet_id INTEGER,
                pruefdatum TEXT,
                ablaufdatum TEXT,
                pruefstelle TEXT,
                bemerkung TEXT
            )
        """)
    else:
        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS geraete (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interne_nummer TEXT,
                name TEXT,
                kategorie TEXT,
                fahrzeug TEXT,
                fachnummer TEXT,
                pruefdatum TEXT,
                ablaufdatum TEXT,
                anzahl INTEGER,
                bemerkung TEXT,
                hersteller TEXT,
                barcode TEXT,
                pruefstatus TEXT DEFAULT 'frei',
                pruefauftrag_datum TEXT,
                pruefstelle TEXT
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS pruefstellen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS fahrzeuge (
                schluessel TEXT PRIMARY KEY,
                tuev_termin TEXT,
                sp_termin TEXT,
                kennzeichen TEXT,
                schlauchwechsel TEXT
            )
        """)

        db_execute(cursor, """
            CREATE TABLE IF NOT EXISTS pruefhistorie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geraet_id INTEGER,
                pruefdatum TEXT,
                ablaufdatum TEXT,
                pruefstelle TEXT,
                bemerkung TEXT
            )
        """)

    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if admin_username and admin_password:
        db_execute(cursor, "SELECT id FROM users WHERE username = ?", (admin_username,))
        admin_vorhanden = cursor.fetchone()

        if not admin_vorhanden:
            from werkzeug.security import generate_password_hash

            db_execute(
                cursor,
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (admin_username, generate_password_hash(admin_password), "admin")
            )

    verbindung.commit()
    verbindung.close()


initialisiere_datenbank()

@login_manager.user_loader
def load_user(user_id):
    return lade_user_nach_id(user_id)


def rollen_required(*rollen):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()

            if current_user.role not in rollen:
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    return rollen_required("admin")(f)


def geraetewart_required(f):
    return rollen_required("admin", "geraetewart")(f)


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Anmelden")

class BenutzerForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired()])
    password = PasswordField("Passwort")
    role = StringField("Rolle", validators=[DataRequired()])
    submit = SubmitField("Speichern")

def lade_geraete_aus_db():
    return lese_dataframe("SELECT * FROM geraete")

def lade_pruefstellen():
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT name FROM pruefstellen ORDER BY name ASC")
    daten = cursor.fetchall()

    verbindung.close()

    return [row_get(eintrag, "name", 0) for eintrag in daten]

def lade_fahrzeugdaten(schluessel):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT * FROM fahrzeuge WHERE schluessel = ?", (schluessel,))
    fahrzeugdaten = cursor.fetchone()

    verbindung.close()
    return fahrzeugdaten

def erstelle_pruefprotokoll_pdf(protokoll_id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT 
            p.*,
            g.name AS geraet_name,
            g.interne_nummer,
            g.barcode,
            g.fahrzeug,
            g.fachnummer,
            g.kategorie,
            s.name AS schema_name
        FROM pruefprotokolle p
        JOIN geraete g ON p.geraet_id = g.id
        LEFT JOIN pruefschemata s ON p.schema_id = s.id
        WHERE p.id = ?
    """, (protokoll_id,))
    protokoll = cursor.fetchone()

    db_execute(cursor, """
        SELECT *
        FROM pruefpunkt_ergebnisse
        WHERE protokoll_id = ?
        ORDER BY id ASC
    """, (protokoll_id,))
    pruefpunkte = cursor.fetchall()

    verbindung.close()

    ordner = BASIS_ORDNER / "static" / "pruefprotokolle"
    ordner.mkdir(parents=True, exist_ok=True)

    dateiname = f"pruefprotokoll_{protokoll_id}_{protokoll['interne_nummer']}.pdf"
    dateipfad = ordner / dateiname

    doc = SimpleDocTemplate(str(dateipfad), pagesize=A4)
    styles = getSampleStyleSheet()
    elemente = []

    elemente.append(Paragraph("<b>Freiwillige Feuerwehr Jesewitz</b>", styles["Title"]))
    elemente.append(Spacer(1, 6))
    elemente.append(Paragraph("<b>Prüfprotokoll gemäß DGUV 305-002, Fassung 2021.12</b>", styles["Heading2"]))
    elemente.append(Spacer(1, 12))


    kopf_daten = [
        ["Protokoll-Nr.", str(protokoll_id)],
        ["Gerät", protokoll["geraet_name"]],
        ["Interne Nummer", protokoll["interne_nummer"]],
        ["Barcode", protokoll["barcode"]],
        ["Kategorie", protokoll["kategorie"]],
        ["Fahrzeug", protokoll["fahrzeug"]],
        ["Fachnummer", protokoll["fachnummer"]],
        ["Prüfschema", protokoll["schema_name"]],
        ["Prüfdatum", protokoll["pruefdatum"]],
        ["Nächste Prüfung", protokoll["ablaufdatum"]],
        ["Prüfstelle", protokoll["pruefstelle"]],
        ["Ergebnis", protokoll["ergebnis"]],
    ]

    tabelle_kopf = Table(kopf_daten, colWidths=[130, 350])
    tabelle_kopf.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elemente.append(tabelle_kopf)
    elemente.append(Spacer(1, 18))

    elemente.append(Paragraph("Prüfpunkte", styles["Heading2"]))

    pruefpunkt_daten = [["Prüfpunkt", "Status", "Bemerkung"]]

    for punkt in pruefpunkte:
        pruefpunkt_daten.append([
            Paragraph(str(punkt["pruefpunkt_text"] or ""), styles["BodyText"]),
            str(punkt["status"] or ""),
            Paragraph(str(punkt["bemerkung"] or ""), styles["BodyText"]),
        ])

    tabelle_punkte = Table(pruefpunkt_daten, colWidths=[260, 100, 120])
    tabelle_punkte.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elemente.append(tabelle_punkte)
    elemente.append(Spacer(1, 18))

    elemente.append(Paragraph("Bemerkung", styles["Heading2"]))
    elemente.append(Paragraph(str(protokoll["bemerkung"] or "-"), styles["BodyText"]))
    elemente.append(Spacer(1, 30))

    unterschrift = Table([
        ["Prüfer / Prüfstelle", "Unterschrift"],
        ["", ""]
    ], colWidths=[240, 240], rowHeights=[24, 45])
    unterschrift.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    elemente.append(unterschrift)

    doc.build(elemente)

    storage_pfad = f"protokolle/{protokoll_id}/{dateiname}"
    cloud_url = lade_pdf_zu_supabase_hoch(dateipfad, storage_pfad)

    if cloud_url:
        pdf_url = cloud_url

        try:
            dateipfad.unlink()
        except Exception:
            pass
    else:
         pdf_url = url_for("static", filename=f"pruefprotokolle/{dateiname}")

    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()
    db_execute(cursor, """
         UPDATE pruefprotokolle
         SET pdf_url = ?,
             pdf_dateiname = ?
         WHERE id = ?
    """, (pdf_url, dateiname, protokoll_id))
    verbindung.commit()
    verbindung.close()

    return pdf_url

def lade_pdf_zu_supabase_hoch(dateipfad, storage_pfad):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    bucket_name = os.environ.get("SUPABASE_BUCKET", "pruefprotokolle")

    if not supabase_url or not supabase_key:
        return None

    upload_url = f"{supabase_url}/storage/v1/object/{bucket_name}/{storage_pfad}"

    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }

    with open(dateipfad, "rb") as datei:
        response = requests.post(upload_url, headers=headers, data=datei)

    if response.status_code not in (200, 201):
        print("Supabase Upload Fehler:", response.status_code, response.text)
        return None

    signed_url_api = f"{supabase_url}/storage/v1/object/sign/{bucket_name}/{storage_pfad}"

    signed_response = requests.post(
        signed_url_api,
        headers={
            "Authorization": f"Bearer {supabase_key}",
            "apikey": supabase_key,
            "Content-Type": "application/json",
        },
        json={"expiresIn": 60 * 60 * 24 * 365}
    )

    if signed_response.status_code != 200:
        print("Supabase Signed URL Fehler:", signed_response.status_code, signed_response.text)
        return None

    daten = signed_response.json()
    signed_url = daten.get("signedURL") or daten.get("signedUrl") or daten.get("signed_url")

    if signed_url and signed_url.startswith("/"):
        signed_url = supabase_url + "/storage/v1" + signed_url

    return signed_url

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("startseite"))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = lade_user_nach_username(username)

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Erfolgreich angemeldet.", "success")
            return redirect(url_for("startseite"))

        flash("Benutzername oder Passwort ist falsch.", "danger")

    return render_template("login.html", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Du wurdest abgemeldet.", "info")
    return redirect(url_for("login"))

@app.route("/benutzer")
@login_required
@admin_required
def benutzer_liste():
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT id, username, role, is_active, created_at
        FROM users
        ORDER BY username ASC
    """)

    benutzer = cursor.fetchall()
    verbindung.close()

    return render_template("benutzer.html", benutzer=benutzer)


@app.route("/benutzer/neu", methods=["GET", "POST"])
@login_required
@admin_required
def benutzer_neu():
    form = BenutzerForm()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "benutzer").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if username and password and role in ["admin", "geraetewart", "benutzer"]:
            from werkzeug.security import generate_password_hash

            verbindung = hole_db_verbindung()
            cursor = verbindung.cursor()

            try:
                db_execute(cursor, """
                    INSERT INTO users (username, password_hash, role, is_active)
                    VALUES (?, ?, ?, ?)
                """, (
                    username,
                    generate_password_hash(password),
                    role,
                    is_active
                ))

                verbindung.commit()
                flash("Benutzer wurde angelegt.", "success")
                return redirect(url_for("benutzer_liste"))

            except Exception:
                verbindung.rollback()
                flash("Benutzer konnte nicht angelegt werden. Existiert der Name bereits?", "danger")

            finally:
                verbindung.close()
        else:
            flash("Bitte Benutzername, Passwort und gültige Rolle angeben.", "danger")

    return render_template("benutzer_neu.html", form=form)


@app.route("/benutzer/<int:id>/bearbeiten", methods=["GET", "POST"])
@login_required
@admin_required
def benutzer_bearbeiten(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        role = request.form.get("role", "benutzer").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if role not in ["admin", "geraetewart", "benutzer"]:
            verbindung.close()
            flash("Ungültige Rolle.", "danger")
            return redirect(url_for("benutzer_bearbeiten", id=id))

        db_execute(cursor, """
            UPDATE users
            SET username = ?,
                role = ?,
                is_active = ?
            WHERE id = ?
        """, (
            username,
            role,
            is_active,
            id
        ))

        verbindung.commit()
        verbindung.close()

        flash("Benutzer wurde aktualisiert.", "success")
        return redirect(url_for("benutzer_liste"))

    db_execute(cursor, """
        SELECT id, username, role, is_active, created_at
        FROM users
        WHERE id = ?
    """, (id,))

    benutzer = cursor.fetchone()
    verbindung.close()

    if not benutzer:
        return "Benutzer nicht gefunden."

    return render_template("benutzer_bearbeiten.html", benutzer=benutzer)


@app.route("/benutzer/<int:id>/passwort", methods=["GET", "POST"])
@login_required
@admin_required
def benutzer_passwort(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT id, username FROM users WHERE id = ?", (id,))
    benutzer = cursor.fetchone()

    if not benutzer:
        verbindung.close()
        return "Benutzer nicht gefunden."

    if request.method == "POST":
        neues_passwort = request.form.get("password", "").strip()

        if neues_passwort:
            from werkzeug.security import generate_password_hash

            db_execute(cursor, """
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            """, (
                generate_password_hash(neues_passwort),
                id
            ))

            verbindung.commit()
            verbindung.close()

            flash("Passwort wurde neu gesetzt.", "success")
            return redirect(url_for("benutzer_liste"))

        flash("Bitte ein neues Passwort eingeben.", "danger")

    verbindung.close()

    return render_template("benutzer_passwort.html", benutzer=benutzer)

@app.route("/pruefschemata")
@login_required
@geraetewart_required
def pruefschemata_liste():
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT id, name, kategorie, beschreibung, aktiv, erstellt_am
        FROM pruefschemata
        ORDER BY kategorie ASC, name ASC
    """)
    schemata = cursor.fetchall()
    verbindung.close()

    return render_template("pruefschemata.html", schemata=schemata)


@app.route("/pruefschemata/neu", methods=["GET", "POST"])
@login_required
@geraetewart_required
def pruefschema_neu():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        kategorie = request.form.get("kategorie", "").strip()
        beschreibung = request.form.get("beschreibung", "").strip()
        aktiv = 1 if request.form.get("aktiv") == "1" else 0

        if not name or not kategorie:
            flash("Name und Kategorie sind Pflichtfelder.", "danger")
            return redirect(url_for("pruefschema_neu"))

        verbindung = hole_db_verbindung()
        cursor = verbindung.cursor()

        db_execute(cursor, """
            INSERT INTO pruefschemata (name, kategorie, beschreibung, aktiv)
            VALUES (?, ?, ?, ?)
        """, (name, kategorie, beschreibung, aktiv))

        verbindung.commit()
        verbindung.close()

        flash("Prüfschema wurde angelegt.", "success")
        return redirect(url_for("pruefschemata_liste"))

    df = lade_geraete_aus_db()
    kategorien = sorted([k for k in df["kategorie"].dropna().unique() if str(k).strip() != ""])

    return render_template("pruefschema_neu.html", kategorien=kategorien)


@app.route("/pruefschemata/<int:id>")
@login_required
@geraetewart_required
def pruefschema_detail(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT id, name, kategorie, beschreibung, aktiv, erstellt_am
        FROM pruefschemata
        WHERE id = ?
    """, (id,))
    schema = cursor.fetchone()

    if not schema:
        verbindung.close()
        return "Prüfschema nicht gefunden."

    db_execute(cursor, """
        SELECT id, schema_id, sortierung, pruefpunkt, hinweis, pflichtfeld
        FROM pruefpunkte
        WHERE schema_id = ?
        ORDER BY sortierung ASC, id ASC
    """, (id,))
    pruefpunkte = cursor.fetchall()

    verbindung.close()

    return render_template(
        "pruefschema_detail.html",
        schema=schema,
        pruefpunkte=pruefpunkte
    )


@app.route("/pruefschemata/<int:id>/bearbeiten", methods=["GET", "POST"])
@login_required
@geraetewart_required
def pruefschema_bearbeiten(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        kategorie = request.form.get("kategorie", "").strip()
        beschreibung = request.form.get("beschreibung", "").strip()
        aktiv = 1 if request.form.get("aktiv") == "1" else 0

        db_execute(cursor, """
            UPDATE pruefschemata
            SET name = ?,
                kategorie = ?,
                beschreibung = ?,
                aktiv = ?
            WHERE id = ?
        """, (name, kategorie, beschreibung, aktiv, id))

        verbindung.commit()
        verbindung.close()

        flash("Prüfschema wurde aktualisiert.", "success")
        return redirect(url_for("pruefschema_detail", id=id))

    db_execute(cursor, """
        SELECT id, name, kategorie, beschreibung, aktiv
        FROM pruefschemata
        WHERE id = ?
    """, (id,))
    schema = cursor.fetchone()
    verbindung.close()

    if not schema:
        return "Prüfschema nicht gefunden."

    df = lade_geraete_aus_db()
    kategorien = sorted([k for k in df["kategorie"].dropna().unique() if str(k).strip() != ""])

    return render_template("pruefschema_bearbeiten.html", schema=schema, kategorien=kategorien)


@app.route("/pruefschemata/<int:schema_id>/pruefpunkt/neu", methods=["GET", "POST"])
@login_required
@geraetewart_required
def pruefpunkt_neu(schema_id):
    if request.method == "POST":
        sortierung = request.form.get("sortierung", "0")
        pruefpunkt = request.form.get("pruefpunkt", "").strip()
        hinweis = request.form.get("hinweis", "").strip()
        pflichtfeld = 1 if request.form.get("pflichtfeld") == "1" else 0

        try:
            sortierung = int(sortierung)
        except ValueError:
            sortierung = 0

        if not pruefpunkt:
            flash("Prüfpunkt ist ein Pflichtfeld.", "danger")
            return redirect(url_for("pruefpunkt_neu", schema_id=schema_id))

        verbindung = hole_db_verbindung()
        cursor = verbindung.cursor()

        db_execute(cursor, """
            INSERT INTO pruefpunkte (schema_id, sortierung, pruefpunkt, hinweis, pflichtfeld)
            VALUES (?, ?, ?, ?, ?)
        """, (schema_id, sortierung, pruefpunkt, hinweis, pflichtfeld))

        verbindung.commit()
        verbindung.close()

        flash("Prüfpunkt wurde angelegt.", "success")
        return redirect(url_for("pruefschema_detail", id=schema_id))

    return render_template("pruefpunkt_neu.html", schema_id=schema_id)


@app.route("/pruefpunkt/<int:id>/bearbeiten", methods=["GET", "POST"])
@login_required
@geraetewart_required
def pruefpunkt_bearbeiten(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    if request.method == "POST":
        sortierung = request.form.get("sortierung", "0")
        pruefpunkt = request.form.get("pruefpunkt", "").strip()
        hinweis = request.form.get("hinweis", "").strip()
        pflichtfeld = 1 if request.form.get("pflichtfeld") == "1" else 0

        try:
            sortierung = int(sortierung)
        except ValueError:
            sortierung = 0

        db_execute(cursor, """
            UPDATE pruefpunkte
            SET sortierung = ?,
                pruefpunkt = ?,
                hinweis = ?,
                pflichtfeld = ?
            WHERE id = ?
        """, (sortierung, pruefpunkt, hinweis, pflichtfeld, id))

        verbindung.commit()

        db_execute(cursor, "SELECT schema_id FROM pruefpunkte WHERE id = ?", (id,))
        punkt = cursor.fetchone()
        verbindung.close()

        return redirect(url_for("pruefschema_detail", id=punkt["schema_id"]))

    db_execute(cursor, """
        SELECT id, schema_id, sortierung, pruefpunkt, hinweis, pflichtfeld
        FROM pruefpunkte
        WHERE id = ?
    """, (id,))
    punkt = cursor.fetchone()
    verbindung.close()

    if not punkt:
        return "Prüfpunkt nicht gefunden."

    return render_template("pruefpunkt_bearbeiten.html", punkt=punkt)

@app.route("/")
@login_required
def startseite():
    df = lade_geraete_aus_db()

    # Ablaufdatum in Datumsformat umwandeln
    df["ablaufdatum_sort"] = pd.to_datetime(df["ablaufdatum"], errors="coerce")

    # Nur Geräte mit gültigem Ablaufdatum betrachten
    pruef_df = df[df["ablaufdatum_sort"].notna()].copy()

    heute = pd.Timestamp.today().normalize()
    in_30_tagen = heute + pd.Timedelta(days=30)

    rot_df = pruef_df[pruef_df["ablaufdatum_sort"] < heute]
    gelb_df = pruef_df[
        (pruef_df["ablaufdatum_sort"] >= heute) &
        (pruef_df["ablaufdatum_sort"] <= in_30_tagen)
    ]
    gruen_df = pruef_df[pruef_df["ablaufdatum_sort"] > in_30_tagen]

    blau_df = df[df["pruefstatus"] == "in Prüfung"]

    naechste_pruefungen = pruef_df.sort_values("ablaufdatum_sort").head(5).to_dict(orient="records")

    return render_template(
        "start.html",
        anzahl_rot=len(rot_df),
        anzahl_gelb=len(gelb_df),
        anzahl_gruen=len(gruen_df),
        anzahl_blau=len(blau_df),
        naechste_pruefungen=naechste_pruefungen
    )

@app.route("/geraete")
@login_required
def geraete():
    df = lade_geraete_aus_db()

    fahrzeug = request.args.get("fahrzeug", "")
    kategorie = request.args.get("kategorie", "")
    suche = request.args.get("suche", "")

    alle_fahrzeuge = sorted(df["fahrzeug"].dropna().unique())
    alle_kategorien = sorted(df["kategorie"].dropna().unique())

    if fahrzeug:
        df = df[df["fahrzeug"] == fahrzeug]

    if kategorie:
        df = df[df["kategorie"] == kategorie]

    if suche:
        suchtext = suche.lower()
        df = df[
            df["interne_nummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["name"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["kategorie"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["fahrzeug"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["fachnummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["bemerkung"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["hersteller"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["barcode"].astype(str).str.lower().str.contains(suchtext, na=False)
        ]

    daten = df.to_dict(orient="records")

    return render_template(
        "geraete.html",
        daten=daten,
        fahrzeug=fahrzeug,
        kategorie=kategorie,
        suche=suche,
        fahrzeuge=alle_fahrzeuge,
        kategorien=alle_kategorien
    )


@app.route("/prueftermine")
@login_required
def prueftermine():
    df = lade_geraete_aus_db()

    fahrzeug = request.args.get("fahrzeug", "")
    kategorie = request.args.get("kategorie", "")
    suche = request.args.get("suche", "")

    alle_fahrzeuge = sorted(df["fahrzeug"].dropna().unique())
    alle_kategorien = sorted(df["kategorie"].dropna().unique())

    if fahrzeug:
        df = df[df["fahrzeug"] == fahrzeug]

    if kategorie:
        df = df[df["kategorie"] == kategorie]

    if suche:
        suchtext = suche.lower()
        df = df[
            df["interne_nummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["name"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["kategorie"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["fahrzeug"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["fachnummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["bemerkung"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["hersteller"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["barcode"].astype(str).str.lower().str.contains(suchtext, na=False)
        ]

    df["ablaufdatum_sort"] = pd.to_datetime(df["ablaufdatum"], errors="coerce")
    df = df[df["ablaufdatum_sort"].notna()]
    df = df.sort_values("ablaufdatum_sort")
    
    heute = pd.Timestamp.today().normalize()
    in_30_tagen = heute + pd.Timedelta(days=30)

    def bestimme_status(row):
        if row["pruefstatus"] == "in Prüfung":
            return "blau"
        if row["ablaufdatum_sort"] < heute:
            return "rot"
        if row["ablaufdatum_sort"] <= in_30_tagen:
            return "gelb"
        return "normal"

    df["statusfarbe"] = df.apply(bestimme_status, axis=1)

    daten = df.to_dict(orient="records")

    return render_template(
        "prueftermine.html",
        daten=daten,
        fahrzeug=fahrzeug,
        kategorie=kategorie,
        suche=suche,
        fahrzeuge=alle_fahrzeuge,
        kategorien=alle_kategorien
    )


@app.route("/fahrzeug/<name>")
@login_required
def fahrzeug(name):
    df = lade_geraete_aus_db()

    mapping = {
        "tlf": ("TLF", "Tanklöschfahrzeug", "fahrzeug"),
        "lf": ("LF", "Löschgruppenfahrzeug", "fahrzeug"),
        "schlauchanhaenger": ("SA", "Schlauchanhänger", "schlauch"),
        "ts": ("TSA", "Tragkraftspritzenanhänger", "none"),
        "boot": ("BoA", "Boot-Anhänger", "none"),
    }

    if name not in mapping:
        return f"Unbekanntes Fahrzeug: {name}"

    fahrzeug_name, titel, typ = mapping[name]

    df = df[df["fahrzeug"] == fahrzeug_name]
    daten = df.to_dict(orient="records")

    fahrzeugdaten = lade_fahrzeugdaten(name)

    return render_template(
        "fahrzeug.html",
        daten=daten,
        titel=titel,
        typ=typ,
        schluessel=name,
        fahrzeugdaten=fahrzeugdaten
    )


@app.route("/kleidung")
@login_required
def kleidung():
    return "<h1>Kleidung folgt später</h1>"

@app.route("/geraet/neu", methods=["GET", "POST"])
@login_required
@geraetewart_required
def geraet_neu():
    fahrzeuge = [
        "TLF",
        "LF",
        "Lager",
        "Schlauchanhänger",
        "TS-Anhänger",
        "Boot-Anhänger"
    ]

    df = lade_geraete_aus_db()
    kategorien = sorted([k for k in df["kategorie"].dropna().unique() if str(k).strip() != ""])

    fachnummern = {
        "TLF": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "Dach", "Mannschaftsraum", "Gruppenführerplatz"],
        "LF": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "Dach", "Mannschaftsraum", "Gruppenführerplatz"],
        "Schlauchanhänger": ["Front", "Heck", "Dach"],
        "TS-Anhänger": ["Front", "Heck", "Dach"],
        "Boot-Anhänger": ["Front", "Heck", "Dach"],
        "Lager": ["Regal"]
    }

    if request.method == "POST":
        interne_nummer = request.form.get("interne_nummer", "")
        name = request.form.get("name", "")
        kategorie = request.form.get("kategorie", "")
        fahrzeug = request.form.get("fahrzeug", "")
        fachnummer = request.form.get("fachnummer", "")
        pruefdatum = request.form.get("pruefdatum", "")
        ablaufdatum = request.form.get("ablaufdatum", "")
        anzahl = request.form.get("anzahl", "1")
        bemerkung = request.form.get("bemerkung", "")
        hersteller = request.form.get("hersteller", "")
        barcode = request.form.get("barcode", "")

        try:
            anzahl = int(anzahl)
        except ValueError:
            anzahl = 1

        verbindung = hole_db_verbindung()
        cursor = verbindung.cursor()

        db_execute(cursor, """
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
        ))

        verbindung.commit()
        verbindung.close()

        return redirect(url_for("geraete"))

    return render_template(
        "geraet_neu.html",
        fahrzeuge=fahrzeuge,
        kategorien=kategorien,
        fachnummern=fachnummern
    )

@app.route("/geraet/<int:id>/bearbeiten", methods=["GET", "POST"])
@login_required
@geraetewart_required
def geraet_bearbeiten(id):
    fahrzeuge = [
        "TLF",
        "LF",
        "Lager",
        "Schlauchanhänger",
        "TS-Anhänger",
        "Boot-Anhänger"
    ]

    df = lade_geraete_aus_db()
    kategorien = sorted([k for k in df["kategorie"].dropna().unique() if str(k).strip() != ""])

    fachnummern = {
        "TLF": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "Dach", "Mannschaftsraum", "Gruppenführerplatz"],
        "LF": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "Dach", "Mannschaftsraum", "Gruppenführerplatz"],
        "Schlauchanhänger": ["Front", "Heck", "Dach"],
        "TS-Anhänger": ["Front", "Heck", "Dach"],
        "Boot-Anhänger": ["Front", "Heck", "Dach"],
        "Lager": ["Regal"]
    }

    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    if request.method == "POST":
        interne_nummer = request.form.get("interne_nummer", "")
        name = request.form.get("name", "")
        kategorie = request.form.get("kategorie", "")
        fahrzeug = request.form.get("fahrzeug", "")
        fachnummer = request.form.get("fachnummer", "")
        pruefdatum = request.form.get("pruefdatum", "")
        ablaufdatum = request.form.get("ablaufdatum", "")
        anzahl = request.form.get("anzahl", "1")
        bemerkung = request.form.get("bemerkung", "")
        hersteller = request.form.get("hersteller", "")
        barcode = request.form.get("barcode", "")

        try:
            anzahl = int(anzahl)
        except ValueError:
            anzahl = 1

        db_execute(cursor, """
            UPDATE geraete
            SET interne_nummer = ?,
                name = ?,
                kategorie = ?,
                fahrzeug = ?,
                fachnummer = ?,
                pruefdatum = ?,
                ablaufdatum = ?,
                anzahl = ?,
                bemerkung = ?,
                hersteller = ?,
                barcode = ?
            WHERE id = ?
        """, (
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
            barcode,
            id
        ))

        verbindung.commit()
        verbindung.close()

        return redirect(url_for("geraete"))

    db_execute(cursor, "SELECT * FROM geraete WHERE id = ?", (id,))
    geraet = cursor.fetchone()
    verbindung.close()

    if geraet is None:
        return f"Gerät mit ID {id} nicht gefunden."

    return render_template(
        "geraet_bearbeiten.html",
        geraet=geraet,
        fahrzeuge=fahrzeuge,
        kategorien=kategorien,
        fachnummern=fachnummern
    )

@app.route("/geraet/<int:id>")
@login_required
def geraet_detail(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT * FROM geraete WHERE id = ?", (id,))
    geraet = cursor.fetchone()

    if geraet is None:
        verbindung.close()
        return f"Gerät mit ID {id} nicht gefunden."

    db_execute(cursor, """
        SELECT *
        FROM pruefhistorie
        WHERE geraet_id = ?
        ORDER BY pruefdatum DESC, id DESC
    """, (id,))
    historie = cursor.fetchall()

    db_execute(cursor, """
        SELECT 
            p.id,
            p.pruefdatum,
            p.ablaufdatum,
            p.pruefstelle,
            p.ergebnis,
            p.bemerkung,
            p.pdf_url,
            p.pdf_dateiname,
            s.name AS schema_name
        FROM pruefprotokolle p
        LEFT JOIN pruefschemata s ON p.schema_id = s.id
        WHERE p.geraet_id = ?
        ORDER BY p.pruefdatum DESC, p.id DESC
    """, (id,))
    protokolle = cursor.fetchall()

    verbindung.close()

    return render_template(
        "geraet_detail.html",
        geraet=geraet,
        historie=historie,
        protokolle=protokolle
    )

@app.route("/pruefauftrag")
@login_required
def pruefauftrag():
    df = lese_dataframe("SELECT * FROM geraete WHERE pruefstatus = 'in Prüfung'")

    daten = df.to_dict(orient="records")

    return render_template("pruefauftrag.html", daten=daten)


@app.route("/geraet/<int:id>/in_pruefung")
@login_required
@geraetewart_required
def geraet_in_pruefung(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    heute = datetime.now().strftime("%Y-%m-%d")

    db_execute(cursor, """
        UPDATE geraete
        SET pruefstatus = 'in Prüfung',
            pruefauftrag_datum = ?
        WHERE id = ?
    """, (heute, id))

    verbindung.commit()
    verbindung.close()

    return redirect(url_for("prueftermine"))

@app.route("/geraet/<int:id>/pruefung_abschliessen", methods=["GET", "POST"])
@login_required
@geraetewart_required
def geraet_pruefung_abschliessen(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT * FROM geraete WHERE id = ?", (id,))
    geraet = cursor.fetchone()

    if geraet is None:
        verbindung.close()
        return f"Gerät mit ID {id} nicht gefunden."

    db_execute(cursor, """
        SELECT *
        FROM pruefschemata
        WHERE kategorie = ?
          AND aktiv = 1
        ORDER BY name ASC
    """, (geraet["kategorie"],))
    schemata = cursor.fetchall()

    ausgewaehltes_schema_id = request.values.get("schema_id")

    if not ausgewaehltes_schema_id and len(schemata) == 1:
        ausgewaehltes_schema_id = str(schemata[0]["id"])

    schema = None
    pruefpunkte = []

    if ausgewaehltes_schema_id:
        db_execute(cursor, """
            SELECT *
            FROM pruefschemata
            WHERE id = ?
              AND aktiv = 1
        """, (ausgewaehltes_schema_id,))
        schema = cursor.fetchone()

        if schema:
            db_execute(cursor, """
                SELECT *
                FROM pruefpunkte
                WHERE schema_id = ?
                ORDER BY sortierung ASC, id ASC
            """, (schema["id"],))
            pruefpunkte = cursor.fetchall()

    if request.method == "POST":
        pruefdatum = request.form.get("pruefdatum", "")
        ablaufdatum = request.form.get("ablaufdatum", "")
        pruefstelle = request.form.get("pruefstelle", "")
        bemerkung = request.form.get("bemerkung", "")
        ergebnis = request.form.get("ergebnis", "bestanden")
        schema_id = request.form.get("schema_id") or None

        if schemata and not schema_id:
            verbindung.close()
            flash("Bitte ein Prüfschema auswählen.", "danger")
            return redirect(url_for("geraet_pruefung_abschliessen", id=id))

        db_execute(cursor, """
            INSERT INTO pruefprotokolle (
                geraet_id,
                schema_id,
                pruefdatum,
                ablaufdatum,
                pruefstelle,
                ergebnis,
                bemerkung
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            id,
            schema_id,
            pruefdatum,
            ablaufdatum,
            pruefstelle,
            ergebnis,
            bemerkung
        ))

        if USING_POSTGRES:
            db_execute(cursor, "SELECT LASTVAL() AS id")
            protokoll_id = cursor.fetchone()["id"]
        else:
            protokoll_id = cursor.lastrowid

        for punkt in pruefpunkte:
            punkt_id = punkt["id"]
            status = request.form.get(f"punkt_status_{punkt_id}", "nicht_geprueft")
            punkt_bemerkung = request.form.get(f"punkt_bemerkung_{punkt_id}", "")

            db_execute(cursor, """
                INSERT INTO pruefpunkt_ergebnisse (
                    protokoll_id,
                    pruefpunkt_id,
                    pruefpunkt_text,
                    status,
                    bemerkung
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                protokoll_id,
                punkt_id,
                punkt["pruefpunkt"],
                status,
                punkt_bemerkung
            ))

        db_execute(cursor, """
            INSERT INTO pruefhistorie (
                geraet_id,
                pruefdatum,
                ablaufdatum,
                pruefstelle,
                bemerkung
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            id,
            pruefdatum,
            ablaufdatum,
            pruefstelle,
            bemerkung
        ))

        db_execute(cursor, """
            UPDATE geraete
            SET pruefstatus = 'frei',
                pruefdatum = ?,
                ablaufdatum = ?,
                pruefstelle = ?
            WHERE id = ?
        """, (
            pruefdatum,
            ablaufdatum,
            pruefstelle,
            id
        ))

        verbindung.commit()
        verbindung.close()

        erstelle_pruefprotokoll_pdf(protokoll_id)

        flash("Prüfung wurde abgeschlossen und das Prüfprotokoll wurde gespeichert.", "success")
        return redirect(url_for("geraet_detail", id=id))

    verbindung.close()

    pruefstellen = lade_pruefstellen()

    return render_template(
        "pruefung_abschliessen.html",
        geraet=geraet,
        pruefstellen=pruefstellen,
        schemata=schemata,
        schema=schema,
        pruefpunkte=pruefpunkte,
        ausgewaehltes_schema_id=ausgewaehltes_schema_id
    )

@app.route("/pruefprotokoll/<int:id>")
@login_required
def pruefprotokoll_detail(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT 
            p.*,
            g.name AS geraet_name,
            g.interne_nummer,
            g.barcode,
            g.fahrzeug,
            g.fachnummer,
            g.kategorie,
            s.name AS schema_name
        FROM pruefprotokolle p
        JOIN geraete g ON p.geraet_id = g.id
        LEFT JOIN pruefschemata s ON p.schema_id = s.id
        WHERE p.id = ?
    """, (id,))
    protokoll = cursor.fetchone()

    if not protokoll:
        verbindung.close()
        return "Prüfprotokoll nicht gefunden."

    db_execute(cursor, """
        SELECT *
        FROM pruefpunkt_ergebnisse
        WHERE protokoll_id = ?
        ORDER BY id ASC
    """, (id,))
    pruefpunkte = cursor.fetchall()

    verbindung.close()

    return render_template(
        "pruefprotokoll_detail.html",
        protokoll=protokoll,
        pruefpunkte=pruefpunkte
    )

@app.route("/pruefprotokoll/<int:id>/pdf")
@login_required
def pruefprotokoll_pdf_oeffnen(id):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, """
        SELECT pdf_dateiname
        FROM pruefprotokolle
        WHERE id = ?
    """, (id,))
    protokoll = cursor.fetchone()

    verbindung.close()

    if not protokoll or not protokoll["pdf_dateiname"]:
        return "Kein PDF vorhanden."

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    bucket_name = os.environ.get("SUPABASE_BUCKET", "pruefprotokolle")

    if not supabase_url or not supabase_key:
        return "Supabase ist nicht eingerichtet."

    storage_pfad = f"protokolle/{id}/{protokoll['pdf_dateiname']}"

    signed_url_api = f"{supabase_url}/storage/v1/object/sign/{bucket_name}/{storage_pfad}"

    response = requests.post(
        signed_url_api,
        headers={
            "Authorization": f"Bearer {supabase_key}",
            "apikey": supabase_key,
            "Content-Type": "application/json",
        },
        json={"expiresIn": 60 * 10}
    )

    if response.status_code != 200:
        return f"PDF konnte nicht geöffnet werden: {response.text}"

    daten = response.json()
    signed_url = daten.get("signedURL") or daten.get("signedUrl") or daten.get("signed_url")

    if signed_url and signed_url.startswith("/"):
        signed_url = supabase_url + "/storage/v1" + signed_url

    return redirect(signed_url)

@app.route("/barcode_suche")
@login_required
def barcode_suche():
    barcode = request.args.get("barcode", "").strip()

    gefundenes_geraet = None

    if barcode:
        verbindung = hole_db_verbindung()
        cursor = verbindung.cursor()

        db_execute(cursor, "SELECT * FROM geraete WHERE barcode = ?", (barcode,))
        gefundenes_geraet = cursor.fetchone()

        verbindung.close()

    return render_template("barcode_suche.html", barcode=barcode, geraet=gefundenes_geraet)

@app.route("/barcode_sammeln", methods=["GET", "POST"])
@login_required
def barcode_sammeln():
    if "barcode_liste" not in session:
        session["barcode_liste"] = []

    fehlermeldung = ""
    gefundenes_geraet = None

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()

        if barcode:
            verbindung = hole_db_verbindung()
            cursor = verbindung.cursor()

            db_execute(cursor, "SELECT * FROM geraete WHERE barcode = ?", (barcode,))
            geraet = cursor.fetchone()

            verbindung.close()

            if geraet:
                gefundenes_geraet = dict(geraet)

                vorhandene_ids = [eintrag["id"] for eintrag in session["barcode_liste"]]

                if geraet["id"] not in vorhandene_ids:
                    session["barcode_liste"].append({
                        "id": geraet["id"],
                        "interne_nummer": geraet["interne_nummer"],
                        "name": geraet["name"],
                        "fahrzeug": geraet["fahrzeug"],
                        "fachnummer": geraet["fachnummer"],
                        "pruefstatus": geraet["pruefstatus"],
                        "barcode": geraet["barcode"]
                    })
                    session.modified = True
                else:
                    fehlermeldung = "Gerät ist bereits in der Sammelliste."
            else:
                fehlermeldung = "Kein Gerät zu diesem Barcode gefunden."

    pruefstellen = lade_pruefstellen()

    return render_template(
        "barcode_sammeln.html",
        daten=session["barcode_liste"],
        fehlermeldung=fehlermeldung,
        gefundenes_geraet=gefundenes_geraet,
        pruefstellen=pruefstellen
    )

@app.route("/barcode_sammeln/loeschen/<int:id>")
@login_required
def barcode_sammeln_loeschen(id):
    if "barcode_liste" in session:
        session["barcode_liste"] = [
            eintrag for eintrag in session["barcode_liste"]
            if eintrag["id"] != id
        ]
        session.modified = True

    return redirect(url_for("barcode_sammeln"))


@app.route("/barcode_sammeln/alle_in_pruefung", methods=["POST"])
@login_required
@geraetewart_required
def barcode_sammeln_alle_in_pruefung():
    if "barcode_liste" not in session or not session["barcode_liste"]:
        return redirect(url_for("barcode_sammeln"))

    pruefstelle = request.form.get("pruefstelle", "").strip()

    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    heute = datetime.now().strftime("%Y-%m-%d")

    for eintrag in session["barcode_liste"]:
        db_execute(cursor, """
            UPDATE geraete
            SET pruefstatus = 'in Prüfung',
                pruefauftrag_datum = ?,
                pruefstelle = ?
            WHERE id = ?
        """, (heute, pruefstelle, eintrag["id"]))

    verbindung.commit()
    verbindung.close()

    session["barcode_liste"] = []
    session.modified = True

    return redirect(url_for("pruefauftrag"))


@app.route("/barcode_sammeln/leeren")
@login_required
def barcode_sammeln_leeren():
    session["barcode_liste"] = []
    session.modified = True
    return redirect(url_for("barcode_sammeln"))

@app.route("/pruefstellen", methods=["GET", "POST"])
@login_required
@geraetewart_required
def pruefstellen_verwalten():
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    fehlermeldung = ""

    if request.method == "POST":
        neue_pruefstelle = request.form.get("name", "").strip()

        if neue_pruefstelle:
            try:
                db_execute(cursor, "INSERT INTO pruefstellen (name) VALUES (?)", (neue_pruefstelle,))
                verbindung.commit()
            except Exception:
                verbindung.rollback()
                fehlermeldung = "Diese Prüfstelle existiert bereits."

    db_execute(cursor, "SELECT * FROM pruefstellen ORDER BY name ASC")
    pruefstellen = cursor.fetchall()

    verbindung.close()

    return render_template(
        "pruefstellen.html",
        pruefstellen=pruefstellen,
        fehlermeldung=fehlermeldung
    )

@app.route("/fahrzeug/<schluessel>/bearbeiten", methods=["GET", "POST"])
@login_required
@geraetewart_required
def fahrzeug_bearbeiten(schluessel):
    verbindung = hole_db_verbindung()
    cursor = verbindung.cursor()

    db_execute(cursor, "SELECT * FROM fahrzeuge WHERE schluessel = ?", (schluessel,))
    fahrzeugdaten = cursor.fetchone()

    if fahrzeugdaten is None:
        verbindung.close()
        return f"Fahrzeug mit Schlüssel '{schluessel}' nicht gefunden."

    if request.method == "POST":
        tuev_termin = request.form.get("tuev_termin", "")
        sp_termin = request.form.get("sp_termin", "")
        kennzeichen = request.form.get("kennzeichen", "")
        schlauchwechsel = request.form.get("schlauchwechsel", "")

        db_execute(cursor, """
            UPDATE fahrzeuge
            SET tuev_termin = ?,
                sp_termin = ?,
                kennzeichen = ?,
                schlauchwechsel = ?
            WHERE schluessel = ?
        """, (
            tuev_termin,
            sp_termin,
            kennzeichen,
            schlauchwechsel,
            schluessel
        ))

        verbindung.commit()
        verbindung.close()

        return redirect(url_for("fahrzeug", name=schluessel))

    verbindung.close()

    return render_template(
        "fahrzeug_bearbeiten.html",
        fahrzeugdaten=fahrzeugdaten,
        schluessel=schluessel
    )

if __name__ == "__main__":
    app.run(debug=True)
