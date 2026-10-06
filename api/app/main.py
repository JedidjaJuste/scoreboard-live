import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# On importe les modèles ET les schémas : les modèles pour écrire en base,
# les schémas pour valider ce qui entre et formater ce qui sort.
# "cache" = notre module Redis, "ws" = la logique WebSocket.
from . import cache, models, schemas, ws  # noqa: F401
from .db import Base, engine, get_db

# Le calcul du classement vit dans son propre module : une seule source
# de vérité partagée entre REST, WebSockets et GraphQL (principe DRY).
from .graphql_schema import router as graphql_router
from .leaderboard import compute_leaderboard, get_fresh_leaderboard

# Crée les tables "players" et "scores" au démarrage si elles n'existent pas.
# Pratique pour un lab ; en production on utiliserait des migrations (Alembic).
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Code exécuté au démarrage et à l'arrêt de l'application.

    Au démarrage : on lance redis_listener() en tâche de fond — elle tourne
    en parallèle des requêtes, à l'écoute du canal Redis "scores".
    À l'arrêt : on l'annule proprement.
    (C'est le remplaçant moderne de @app.on_event("startup").)
    """
    task = asyncio.create_task(ws.redis_listener(get_fresh_leaderboard))
    yield
    task.cancel()


app = FastAPI(title="Scoreboard Live", lifespan=lifespan)

# Monte l'API GraphQL sur /graphql, avec GraphiQL (l'explorateur interactif)
# accessible directement dans le navigateur.
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
def health():
    """Sonde de santé : répond toujours OK si l'API tourne."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Scoreboard Live — étape 5 : WebSockets en direct 🔌"}


@app.get("/live")
def live_page():
    """Page HTML du classement en direct (démonstration WebSocket)."""
    # Chemin relatif au WORKDIR du conteneur (/code)
    return FileResponse("app/static/live.html")


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    """Vérifie que la connexion à Postgres fonctionne et liste les tables."""
    db.execute(text("SELECT 1"))
    return {"db": "ok", "tables": sorted(Base.metadata.tables)}


@app.post("/players", response_model=schemas.PlayerOut, status_code=201)
def create_player(payload: schemas.PlayerCreate, db: Session = Depends(get_db)):
    """Crée un joueur.

    - payload est déjà validé par Pydantic (PlayerCreate) avant d'arriver ici.
    - 409 Conflict si le nom existe déjà (la colonne est unique en base).
    - 201 Created + le joueur créé en réponse.
    """
    existing = db.query(models.Player).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce nom est déjà pris")
    player = models.Player(name=payload.name)
    db.add(player)  # marque l'objet à insérer...
    db.commit()  # ...exécute réellement l'INSERT
    db.refresh(player)  # recharge l'objet pour récupérer l'id généré
    return player


@app.post("/scores", response_model=schemas.ScoreOut, status_code=201)
def create_score(payload: schemas.ScoreCreate, db: Session = Depends(get_db)):
    """Enregistre un score pour un joueur.

    - 404 Not Found si le player_id ne correspond à aucun joueur.
    - La date (created_at) est remplie automatiquement par Postgres.
    - Après l'insertion : on invalide le cache Redis ET on publie
      l'événement → la tâche WebSocket préviendra les navigateurs.
    """
    player = db.get(models.Player, payload.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Joueur introuvable")
    score = models.Score(player_id=payload.player_id, points=payload.points)
    db.add(score)
    db.commit()
    db.refresh(score)
    # Les données ont changé : le classement en cache est périmé.
    cache.invalidate_leaderboard()  # force un recalcul au prochain GET
    # On publie l'événement : l'étape 5 (WebSockets) s'y abonnera
    # pour prévenir les navigateurs en direct.
    cache.publish_score_event({"player_id": score.player_id, "points": score.points})
    return score


@app.get("/players", response_model=list[schemas.PlayerOut])
def list_players(db: Session = Depends(get_db)):
    """Liste tous les joueurs, par ordre de création."""
    return db.query(models.Player).order_by(models.Player.id).all()


@app.get("/players/{player_id}", response_model=schemas.PlayerDetail)
def get_player(player_id: int, db: Session = Depends(get_db)):
    """Un joueur et tous ses scores.

    - player_id vient directement de l'URL (/players/3 → player_id=3).
    - Grâce à la relation Player.scores, SQLAlchemy charge les scores
      automatiquement : pas besoin de deuxième requête écrite à la main.
    - 404 si l'id n'existe pas.
    """
    player = db.get(models.Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Joueur introuvable")
    return player


@app.get("/leaderboard", response_model=list[schemas.LeaderboardEntry])
def leaderboard(
    # Paramètre d'URL optionnel : /leaderboard?limit=5 (défaut 10, max 100).
    # FastAPI le valide automatiquement (ge=1, le=100).
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Classement avec cache Redis (stratégie "cache-aside").

    1. On cherche d'abord dans Redis : si présent et non expiré (cache hit),
       on le sert en quelques millisecondes sans toucher Postgres.
    2. Sinon (cache miss), on calcule depuis Postgres, on stocke le résultat
       en cache pour 30 secondes, puis on le renvoie.
    """
    cached = cache.get_cached_leaderboard(limit)
    if cached is not None:
        return cached
    entries = compute_leaderboard(db, limit)
    cache.set_cached_leaderboard(limit, entries)
    return entries


@app.websocket("/ws/leaderboard")
async def websocket_leaderboard(websocket: WebSocket):
    """Canal temps réel vers les navigateurs.

    1. Le navigateur ouvre UNE connexion (handshake HTTP → upgrade WebSocket).
    2. On lui envoie le classement actuel immédiatement.
    3. La connexion reste ouverte : à chaque nouveau score, redis_listener()
       diffusera le classement à jour à tous les clients connectés.
    4. Quand l'onglet se ferme, receive_text() lève WebSocketDisconnect
       et on retire proprement le client du registre.
    """
    await ws.manager.connect(websocket)
    try:
        # SQLAlchemy est synchrone : on l'exécute dans un thread pour
        # ne pas bloquer l'event loop qui sert les autres clients.
        entries = await asyncio.to_thread(get_fresh_leaderboard)
        await websocket.send_json({"type": "leaderboard", "entries": entries})
        # On garde la connexion ouverte. On ne s'intéresse pas aux messages
        # du client (canal descendant) : receive_text() sert juste à
        # détecter la déconnexion.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws.manager.disconnect(websocket)
