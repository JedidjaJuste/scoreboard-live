"""WebSockets : pousse le classement en direct aux navigateurs.

Architecture :
- Chaque navigateur ouvre UNE WebSocket vers /ws/leaderboard.
- Le ConnectionManager garde la liste des connexions ouvertes.
- redis_listener() tourne en tâche de fond : à chaque message publié
  sur le canal Redis "scores" (étape 4), elle recalcule le classement
  et le diffuse à TOUS les navigateurs connectés.

Chaîne complète d'un score affiché en direct :
  POST /scores → Postgres + publish Redis → redis_listener → broadcast → navigateurs
"""

import asyncio
import json
import os

import redis.asyncio as aioredis
from fastapi import WebSocket

from . import cache

# Client Redis ASYNC : la tâche d'écoute tourne dans l'event loop asyncio,
# elle ne doit jamais bloquer → on n'utilise PAS le client synchrone ici.
# (redis.asyncio est inclus dans le paquet "redis" déjà installé.)
async_redis = aioredis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
)


class ConnectionManager:
    """Registre des navigateurs connectés en ce moment."""

    def __init__(self):
        # Un set : pas de doublons, ajout/suppression instantanés
        self.active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        # accept() = la "poignée de main" : le client demande l'upgrade
        # WebSocket, le serveur l'accepte → le canal est ouvert.
        await websocket.accept()
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket):
        # discard() : retire sans erreur si déjà absent
        self.active.discard(websocket)

    async def broadcast(self, message: dict):
        """Envoie un message JSON à tous les clients connectés.

        Un client peut être "mort" (onglet fermé brutalement) : au lieu
        de faire planter la diffusion pour tout le monde, on le retire
        simplement du registre.
        """
        dead = set()
        for connection in self.active:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        self.active -= dead


# Une seule instance partagée par toute l'application
manager = ConnectionManager()


async def redis_listener(get_leaderboard):
    """Tâche de fond : écoute Redis et prévient les navigateurs.

    - pubsub() + subscribe() : on s'abonne au canal "scores".
    - "async for ... listen()" : boucle d'écoute non-bloquante.
      listen() envoie aussi des messages de contrôle (confirmation
      d'abonnement...) : on ne traite que type == "message".
    - À chaque vrai message : on recalcule le classement DANS UN THREAD
      (asyncio.to_thread), car SQLAlchemy est synchrone et ne doit pas
      bloquer l'event loop, puis on le diffuse à tous les connectés.
    - get_leaderboard est passé en paramètre pour éviter un import
      circulaire (main.py importe déjà ce module).
    """
    pubsub = async_redis.pubsub()
    await pubsub.subscribe(cache.SCORES_CHANNEL)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        event = json.loads(message["data"])
        entries = await asyncio.to_thread(get_leaderboard)
        await manager.broadcast(
            {"type": "leaderboard", "entries": entries, "event": event}
        )
