# Scoreboard Live 🏆

Lab personnel : appliquer les 7 technos de la veille tech dans un seul projet —
un tableau de scores en temps réel.

## Lancer le projet

```bash
cd scoreboard-live
docker compose up --build
```

- API : http://localhost:8000 (doc auto : http://localhost:8000/docs)
- PostgreSQL : localhost:5432 (user / password / db : `scoreboard`)
- Redis : localhost:6379

Arrêter : `Ctrl+C`, puis `docker compose down` (ajoute `-v` pour tout effacer).

## Option B — sans installer Docker : GitHub Codespaces

Sur une machine où tu ne peux pas installer Docker (ex. poste du cégep, pas de droits
admin), utilise Codespaces : un VS Code complet dans le navigateur, avec Docker inclus
(60 h/mois gratuites). Le fichier `.devcontainer/` est déjà prêt : tout démarre tout seul.

1. Crée un dépôt sur github.com et pousse ce dossier dedans
   (ou téléverse les fichiers via l'interface web de GitHub)
2. Sur la page du dépôt : **Code → Codespaces → Create codespace on main**
3. Attends le démarrage : `docker-compose` se lance automatiquement (api + postgres + redis)
4. Ouvre l'onglet **Ports**, clique sur le port **8000** → ton API s'affiche

Dans le terminal du codespace, le code est dans `/code` et `docker compose ps`
montre les 3 conteneurs en marche.

## Roadmap

- [x] **Étape 1 — Docker** : `docker-compose.yml` (api + db + cache), tout démarre en une commande
- [x] **Étape 2 — PostgreSQL** : tables `players` et `scores`, connexion depuis FastAPI
- [x] **Étape 3 — REST** : `POST /players`, `POST /scores`, `GET /players`, `GET /players/{id}`, `GET /leaderboard`
- [x] **Étape 4 — Redis** : cache du leaderboard (TTL) + pub/sub pour les mises à jour
- [x] **Étape 5 — WebSockets** : `/ws/leaderboard` pousse le classement en direct au navigateur (+ page `/live`)
- [x] **Étape 6 — GraphQL** : `/graphql` (strawberry) pour interroger les stats librement
- [ ] **Étape 7 — CI/CD** : GitHub Actions — build + tests à chaque push

## Exercice en cours — Étape 7 🏁 (CI/CD)

Objectif : un pipeline GitHub Actions qui teste + build à chaque push.

**À faire :**
1. Crée `api/tests/` : `test_leaderboard.py` (logique métier sur SQLite en
   mémoire) + `test_schemas.py` (validation Pydantic) + `__init__.py` vide
   (sans lui, pytest ne trouve pas le paquet `app`)
2. Ajoute `pytest>=8.0` dans `api/requirements.txt`
3. Crée `.github/workflows/ci.yml` (2 jobs parallèles : tests + build Docker)

**Vérification en local** (rebuild nécessaire : pytest est une nouvelle dépendance) :
```bash
docker compose up --build
docker compose exec api python -m pytest tests/ -v
```
→ 8 tests verts ✅

**Mise en ligne** :
```bash
cd ~/Documents/scoreboard-live
git init && git add . && git commit -m "Scoreboard Live : les 7 technos 🐳"
git branch -M main
git remote add origin https://github.com/TON-USER/scoreboard-live.git
git push -u origin main
```
Puis sur GitHub : onglet **Actions** → le workflow `CI` tourne tout seul
à chaque push. Vert = ton code est sain. 🟢
