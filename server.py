import os, math
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder="public")

TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
AF_BASE = "https://v3.football.api-sports.io"
AF_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()


def tsdb(path, params):
    r = requests.get(f"{TSDB_BASE}/{path}", params=params, timeout=12)
    r.raise_for_status()
    return r.json()


def af(path, params=None):
    if not AF_KEY:
        return None, "API_FOOTBALL_KEY non configurée"
    headers = {"x-apisports-key": AF_KEY}
    try:
        r = requests.get(f"{AF_BASE}/{path}", params=params or {}, headers=headers, timeout=15)
        if r.status_code == 401:
            return None, "Clé API-Football refusée (401)"
        if r.status_code == 403:
            return None, "Accès API-Football refusé (403)"
        if r.status_code == 429:
            return None, "Limite API-Football atteinte (429)"
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            return data, "; ".join(str(v) for v in data["errors"].values())
        return data, None
    except requests.RequestException as e:
        return None, f"API-Football indisponible: {e.__class__.__name__}"


def find_af_team(name):
    data, err = af("teams", {"search": name})
    if not data:
        return None, err
    teams = data.get("response") or []
    if not teams:
        return None, "Équipe introuvable dans API-Football"
    wanted = name.casefold()
    exact = next((x for x in teams if (x.get("team") or {}).get("name", "").casefold() == wanted), None)
    return exact or teams[0], None


def find_fixture(home_team_id, away_team_id):
    # First look ahead 30 days from now. If unavailable, use a wider team search.
    today = datetime.now(ZoneInfo("UTC")).date().isoformat()
    data, err = af("fixtures", {"team": home_team_id, "from": today, "to": today})
    fixtures = (data or {}).get("response") or []
    if not fixtures:
        data, err = af("fixtures", {"team": home_team_id, "next": 20})
        fixtures = (data or {}).get("response") or []
    for f in fixtures:
        teams = f.get("teams") or {}
        hid = (teams.get("home") or {}).get("id")
        aid = (teams.get("away") or {}).get("id")
        if int(hid or -1) == int(home_team_id) and int(aid or -1) == int(away_team_id):
            return f, err
    return None, err


def parse_af_fixture(f):
    fixture = f.get("fixture") or {}
    league = f.get("league") or {}
    venue = fixture.get("venue") or {}
    dt_raw = fixture.get("date")
    date_ci = "Date à confirmer"
    if dt_raw:
        try:
            dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
            date_ci = dt.astimezone(ZoneInfo("Africa/Abidjan")).strftime("%d/%m/%Y à %H:%M")
        except Exception:
            pass
    return {
        "dateCI": date_ci,
        "competition": league.get("name") or "Compétition non renseignée",
        "country": league.get("country") or "Pays non renseigné",
        "round": league.get("round") or "Journée non renseignée",
        "venue": venue.get("name") or "Stade non renseigné",
        "city": venue.get("city") or "Ville non renseignée",
        "eventId": fixture.get("id"),
        "status": (fixture.get("status") or {}).get("long") or "Statut inconnu",
    }


def safe_num(v):
    try:
        return float(v)
    except Exception:
        return None


def extract_stats(fixture_id, team_id):
    data, err = af("fixtures/statistics", {"fixture": fixture_id})
    if not data:
        return {}, err
    rows = data.get("response") or []
    row = next((x for x in rows if (x.get("team") or {}).get("id") == team_id), None)
    if not row:
        return {}, err
    out = {}
    for item in row.get("statistics") or []:
        out[item.get("type", "")] = item.get("value")
    return out, err


def extract_form(team_id):
    data, err = af("fixtures", {"team": team_id, "last": 5})
    fixtures = (data or {}).get("response") or []
    results = []
    for f in fixtures:
        teams = f.get("teams") or {}
        goals = f.get("goals") or {}
        hid = (teams.get("home") or {}).get("id")
        aid = (teams.get("away") or {}).get("id")
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue
        if team_id == hid:
            results.append("V" if hg > ag else "N" if hg == ag else "D")
        elif team_id == aid:
            results.append("V" if ag > hg else "N" if hg == ag else "D")
    return results, err


def build_prediction(home_form, away_form, fixture):
    # Transparent baseline only; no fabricated certainty.
    h = sum(x == "V" for x in home_form)
    a = sum(x == "V" for x in away_form)
    total = max(1, len(home_form) + len(away_form))
    home_edge = 0.50 + 0.18 * ((h / max(1, len(home_form))) - (a / max(1, len(away_form))))
    home_edge = max(0.20, min(0.80, home_edge))
    away_edge = 0.50 - (home_edge - 0.50)
    draw = max(0.10, 1 - home_edge - away_edge)
    # Normalize with a small draw prior.
    home_p = max(0.05, min(0.85, home_edge * 0.90))
    away_p = max(0.05, min(0.85, away_edge * 0.90))
    draw_p = max(0.10, 1 - home_p - away_p)
    s = home_p + draw_p + away_p
    probs = {"1": round(home_p/s*100,1), "X": round(draw_p/s*100,1), "2": round(away_p/s*100,1)}
    winner = max(probs, key=probs.get)
    score = "1-0" if winner == "1" else "0-1" if winner == "2" else "1-1"
    return {
        "winner": winner,
        "score": score,
        "probabilities": probs,
        "confidence": round(max(probs.values()), 1),
        "note": "Estimation indicative basée sur les données disponibles; aucune probabilité ne garantit un résultat."
    }


@app.get("/")
def index():
    return send_from_directory("public", "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "apiFootballConfigured": bool(AF_KEY)})


@app.post("/api/analyze")
def analyze():
    body = request.get_json(silent=True) or {}
    home = str(body.get("home", "")).strip()
    away = str(body.get("away", "")).strip()
    if not home or not away:
        return jsonify({"error": "Équipes manquantes"}), 400
    if not AF_KEY:
        return jsonify({"error": "API_FOOTBALL_KEY non configurée sur le serveur"}), 500

    ht, he = find_af_team(home)
    at, ae = find_af_team(away)
    if not ht or not at:
        return jsonify({"error": he or ae or "Équipe introuvable"}), 404

    hteam = ht.get("team") or {}
    ateam = at.get("team") or {}
    fixture, fe = find_fixture(hteam.get("id"), ateam.get("id"))

    result = {
        "match": {"home": hteam.get("name", home), "away": ateam.get("name", away)},
        "sources": ["API-Football"],
        "sourceStatus": {"API-Football": "OK"},
        "prediction": {"winner": "Non déterminé", "score": "Non déterminé", "confidence": 0,
                        "note": "Pas assez de données pour produire un verdict."},
    }

    if not fixture:
        result["sourceStatus"]["Calendrier"] = "Aucun affrontement correspondant trouvé"
        result["match"]["dateCI"] = "Aucun affrontement futur confirmé par API-Football"
        if fe:
            result["sourceStatus"]["API-Football"] = fe
        return jsonify(result)

    result["match"].update(parse_af_fixture(fixture))
    fid = (fixture.get("fixture") or {}).get("id")
    hs, hse = extract_stats(fid, hteam.get("id"))
    ass, ase = extract_stats(fid, ateam.get("id"))
    hf, hfe = extract_form(hteam.get("id"))
    afm, afe = extract_form(ateam.get("id"))
    result["statistics"] = {"home": hs, "away": ass}
    result["form"] = {"home": hf, "away": afm}
    result["sourceStatus"]["Statistiques"] = "OK" if hs or ass else (hse or ase or "Non disponible")
    result["sourceStatus"]["Forme"] = "OK" if hf or afm else (hfe or afe or "Non disponible")
    result["prediction"] = build_prediction(hf, afm, fixture)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
