from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import pandas as pd
from pathlib import Path

app = Flask(__name__)
app.secret_key = "feuerwehr-inventar-geheim"

BASIS_ORDNER = Path(__file__).resolve().parent
DATENBANK = BASIS_ORDNER / "inventar.db"


def lade_geraete_aus_db():
    verbindung = sqlite3.connect(DATENBANK)
    df = pd.read_sql_query("SELECT * FROM geraete", verbindung)
    verbindung.close()
    return df

def lade_pruefstellen():
    verbindung = sqlite3.connect(DATENBANK)
    cursor = verbindung.cursor()

    cursor.execute("SELECT name FROM pruefstellen ORDER BY name ASC")
    daten = cursor.fetchall()

    verbindung.close()

    return [eintrag[0] for eintrag in daten]

def lade_fahrzeugdaten(schluessel):
    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    cursor = verbindung.cursor()

    cursor.execute("SELECT * FROM fahrzeuge WHERE schluessel = ?", (schluessel,))
    fahrzeugdaten = cursor.fetchone()

    verbindung.close()
    return fahrzeugdaten

@app.route("/")
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
def kleidung():
    return "<h1>Kleidung folgt später</h1>"

@app.route("/geraet/neu", methods=["GET", "POST"])
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

        verbindung = sqlite3.connect(DATENBANK)
        cursor = verbindung.cursor()

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

    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
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

        cursor.execute("""
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

    cursor.execute("SELECT * FROM geraete WHERE id = ?", (id,))
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
def geraet_detail(id):
    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    cursor = verbindung.cursor()

    cursor.execute("SELECT * FROM geraete WHERE id = ?", (id,))
    geraet = cursor.fetchone()

    if geraet is None:
        verbindung.close()
        return f"Gerät mit ID {id} nicht gefunden."

    cursor.execute("""
        SELECT * FROM pruefhistorie
        WHERE geraet_id = ?
        ORDER BY pruefdatum DESC, id DESC
    """, (id,))
    historie = cursor.fetchall()

    verbindung.close()

    return render_template(
        "geraet_detail.html",
        geraet=geraet,
        historie=historie
    )
@app.route("/pruefauftrag")
def pruefauftrag():
    verbindung = sqlite3.connect(DATENBANK)
    df = pd.read_sql_query(
        "SELECT * FROM geraete WHERE pruefstatus = 'in Prüfung'",
        verbindung
    )
    verbindung.close()

    daten = df.to_dict(orient="records")

    return render_template("pruefauftrag.html", daten=daten)

from datetime import datetime

@app.route("/geraet/<int:id>/in_pruefung")
def geraet_in_pruefung(id):
    verbindung = sqlite3.connect(DATENBANK)
    cursor = verbindung.cursor()

    heute = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        UPDATE geraete
        SET pruefstatus = 'in Prüfung',
            pruefauftrag_datum = ?
        WHERE id = ?
    """, (heute, id))

    verbindung.commit()
    verbindung.close()

    return redirect(url_for("prueftermine"))

@app.route("/geraet/<int:id>/pruefung_abschliessen", methods=["GET", "POST"])
def geraet_pruefung_abschliessen(id):
    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    cursor = verbindung.cursor()

    cursor.execute("SELECT * FROM geraete WHERE id = ?", (id,))
    geraet = cursor.fetchone()

    if geraet is None:
        verbindung.close()
        return f"Gerät mit ID {id} nicht gefunden."

    if request.method == "POST":
        pruefdatum = request.form.get("pruefdatum", "")
        ablaufdatum = request.form.get("ablaufdatum", "")
        pruefstelle = request.form.get("pruefstelle", "")
        bemerkung = request.form.get("bemerkung", "")

        # Historie speichern
        cursor.execute("""
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

        # Gerät aktualisieren
        cursor.execute("""
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

        return redirect(url_for("pruefauftrag"))

    verbindung.close()

    pruefstellen = lade_pruefstellen()

    return render_template(
        "pruefung_abschliessen.html",
        geraet=geraet,
        pruefstellen=pruefstellen
    )
@app.route("/barcode_suche")
def barcode_suche():
    barcode = request.args.get("barcode", "").strip()

    gefundenes_geraet = None

    if barcode:
        verbindung = sqlite3.connect(DATENBANK)
        verbindung.row_factory = sqlite3.Row
        cursor = verbindung.cursor()

        cursor.execute("SELECT * FROM geraete WHERE barcode = ?", (barcode,))
        gefundenes_geraet = cursor.fetchone()

        verbindung.close()

    return render_template("barcode_suche.html", barcode=barcode, geraet=gefundenes_geraet)

@app.route("/barcode_sammeln", methods=["GET", "POST"])
def barcode_sammeln():
    if "barcode_liste" not in session:
        session["barcode_liste"] = []

    fehlermeldung = ""
    gefundenes_geraet = None

    if request.method == "POST":
        barcode = request.form.get("barcode", "").strip()

        if barcode:
            verbindung = sqlite3.connect(DATENBANK)
            verbindung.row_factory = sqlite3.Row
            cursor = verbindung.cursor()

            cursor.execute("SELECT * FROM geraete WHERE barcode = ?", (barcode,))
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
def barcode_sammeln_loeschen(id):
    if "barcode_liste" in session:
        session["barcode_liste"] = [
            eintrag for eintrag in session["barcode_liste"]
            if eintrag["id"] != id
        ]
        session.modified = True

    return redirect(url_for("barcode_sammeln"))


@app.route("/barcode_sammeln/alle_in_pruefung", methods=["POST"])
def barcode_sammeln_alle_in_pruefung():
    if "barcode_liste" not in session or not session["barcode_liste"]:
        return redirect(url_for("barcode_sammeln"))

    pruefstelle = request.form.get("pruefstelle", "").strip()

    verbindung = sqlite3.connect(DATENBANK)
    cursor = verbindung.cursor()

    heute = datetime.now().strftime("%Y-%m-%d")

    for eintrag in session["barcode_liste"]:
        cursor.execute("""
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
def barcode_sammeln_leeren():
    session["barcode_liste"] = []
    session.modified = True
    return redirect(url_for("barcode_sammeln"))

@app.route("/pruefstellen", methods=["GET", "POST"])
def pruefstellen_verwalten():
    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    cursor = verbindung.cursor()

    fehlermeldung = ""

    if request.method == "POST":
        neue_pruefstelle = request.form.get("name", "").strip()

        if neue_pruefstelle:
            try:
                cursor.execute("INSERT INTO pruefstellen (name) VALUES (?)", (neue_pruefstelle,))
                verbindung.commit()
            except sqlite3.IntegrityError:
                fehlermeldung = "Diese Prüfstelle existiert bereits."

    cursor.execute("SELECT * FROM pruefstellen ORDER BY name ASC")
    pruefstellen = cursor.fetchall()

    verbindung.close()

    return render_template(
        "pruefstellen.html",
        pruefstellen=pruefstellen,
        fehlermeldung=fehlermeldung
    )

@app.route("/fahrzeug/<schluessel>/bearbeiten", methods=["GET", "POST"])
def fahrzeug_bearbeiten(schluessel):
    verbindung = sqlite3.connect(DATENBANK)
    verbindung.row_factory = sqlite3.Row
    cursor = verbindung.cursor()

    cursor.execute("SELECT * FROM fahrzeuge WHERE schluessel = ?", (schluessel,))
    fahrzeugdaten = cursor.fetchone()

    if fahrzeugdaten is None:
        verbindung.close()
        return f"Fahrzeug mit Schlüssel '{schluessel}' nicht gefunden."

    if request.method == "POST":
        tuev_termin = request.form.get("tuev_termin", "")
        sp_termin = request.form.get("sp_termin", "")
        kennzeichen = request.form.get("kennzeichen", "")
        schlauchwechsel = request.form.get("schlauchwechsel", "")

        cursor.execute("""
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
