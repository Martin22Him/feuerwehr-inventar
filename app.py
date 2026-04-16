from flask import Flask, render_template, request
import pandas as pd
from pathlib import Path

app = Flask(__name__)

BASIS_ORDNER = Path(__file__).resolve().parent
DATEINAME = BASIS_ORDNER / "Inventarliste-Tanker-vereinfacht.xlsx"

@app.route("/")
def startseite():
    return render_template("start.html")

@app.route("/geraete")
def geraete():
    df = pd.read_excel(DATEINAME)

    fahrzeug = request.args.get("fahrzeug", "")
    kategorie = request.args.get("kategorie", "")
    suche = request.args.get("suche", "")

    alle_fahrzeuge = sorted(df["Fahrzeug"].dropna().unique())
    alle_kategorien = sorted(df["Kategorie"].dropna().unique())

    if fahrzeug:
        df = df[df["Fahrzeug"] == fahrzeug]

    if kategorie:
        df = df[df["Kategorie"] == kategorie]

    if suche:
        suchtext = suche.lower()
        df = df[
            df["Interne Nummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["Name"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["Kategorie"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["Fahrzeug"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["Fachnummer"].astype(str).str.lower().str.contains(suchtext, na=False) |
            df["Bemerkung"].astype(str).str.lower().str.contains(suchtext, na=False)
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
    df = pd.read_excel(DATEINAME)

    fahrzeug = request.args.get("fahrzeug", "")
    kategorie = request.args.get("kategorie", "")

    if fahrzeug:
        df = df[df["Fahrzeug"] == fahrzeug]

    if kategorie:
        df = df[df["Kategorie"] == kategorie]

    df["Ablaufdatum_sort"] = pd.to_datetime(df["Ablaufdatum"], errors="coerce")
    df = df[df["Ablaufdatum_sort"].notna()]
    df = df.sort_values("Ablaufdatum_sort")

    daten = df.to_dict(orient="records")

    return render_template(
        "prueftermine.html",
        daten=daten,
        fahrzeug=fahrzeug,
        kategorie=kategorie
    )

@app.route("/fahrzeug/<name>")
def fahrzeug(name):
    df = pd.read_excel(DATEINAME)

    mapping = {
        "tlf": ("TLF", "Tanklöschfahrzeug", "fahrzeug"),
        "lf": ("LF", "Löschgruppenfahrzeug", "fahrzeug"),
        "schlauchanhaenger": ("Schlauchanhänger", "Schlauchanhänger", "schlauch"),
        "ts": ("TS-Anhänger", "Tragkraftspritzenanhänger", "none"),
        "boot": ("Boot-Anhänger", "Boot-Anhänger", "none"),
    }

    fahrzeug_name, titel, typ = mapping[name]

    df = df[df["Fahrzeug"] == fahrzeug_name]

    daten = df.to_dict(orient="records")

    return render_template(
        "fahrzeug.html",
        daten=daten,
        titel=titel,
        typ=typ
    )
if __name__ == "__main__":
    app.run(debug=True)