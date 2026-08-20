# ORACLE FOOTBALL RÉEL — V1000 MULTI-SOURCES

## Ce que fait cette version

L'utilisateur saisit seulement 1 à 3 affiches. Le serveur recherche automatiquement les équipes et l'événement dans TheSportsDB et convertit l'heure en heure de Côte d'Ivoire.

## Pourquoi il faut un serveur pour la version "comme ChatGPT"

Un simple fichier HTML ouvert avec `content://` ne possède pas les outils de recherche web de ChatGPT. Il ne peut pas, de manière fiable et sécurisée, interroger des dizaines de sites, conserver des clés API privées, comparer les cotes de bookmakers et lancer un modèle d'analyse.

La bonne architecture est donc :

Téléphone → interface web → serveur → sources sportives/API → moteur d'analyse → résultat.

## Sources prévues pour la version complète

- TheSportsDB : calendrier, événements, équipes, stades.
- API-Football / API-Sports : fixtures, standings, forme, H2H, blessures, statistiques, prédictions et cotes bookmakers.
- OpenAI Responses API + web search : recherche documentaire multi-sources et synthèse raisonnée.

API-Football est particulièrement adapté car sa documentation indique qu'il fournit fixtures, standings, événements, statistiques, prédictions et odds, avec des limites de couverture selon la compétition.
La version complète doit utiliser les clés API côté serveur uniquement.

## Important

Ne pas mettre les clés API dans `public/index.html`.

Variables d'environnement recommandées :
- API_FOOTBALL_KEY
- OPENAI_API_KEY

La clé TheSportsDB gratuite `123` est utilisée ici uniquement pour l'identification/calendrier de démonstration.

## Lancer localement

Python 3.10+ recommandé.

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python server.py

Puis ouvrir :
    http://127.0.0.1:8080

## Pour une installation sur téléphone

Le bouton "Installer l'application" nécessite un hébergement HTTPS et un manifeste/service worker PWA. Le serveur doit donc être déployé sur un hébergeur compatible HTTPS.
