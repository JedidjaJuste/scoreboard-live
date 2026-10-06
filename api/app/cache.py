"""Client Redis + helpers de cache.

Deux usages dans ce projet :
1. CACHE (stratégie "cache-aside") : le classement est stocké en JSON avec un TTL.
   Lecture ultra-rapide (~1 ms), sans solliciter Postgres.
2. PUB/SUB : à chaque nouveau score, on publie un message sur un canal.
   L'étape 5 (WebSockets) s'y abonnera pour pousser les mises à jour en direct.
"""

import json
import os

import redis

# decode_responses=True : Redis renvoie des str Python, pas des bytes.
# Le nom d'hôte "cache" = le service redis du docker-compose.
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
)

# Durée de vie du classement en cache : 30 secondes.
LEADERBOARD_TTL = 30

# Canal pub/sub : un message y est publié à chaque score enregistré.
SCORES_CHANNEL = "scores"


def _leaderboard_key(limit: int) -> str:
    # La clé inclut les paramètres : ?limit=5 et ?limit=10 sont
    # deux entrées de cache indépendantes.
    return f"leaderboard:{limit}"


def get_cached_leaderboard(limit: int):
    """Lit le classement en cache. None si absent ou expiré (cache miss)."""
    raw = redis_client.get(_leaderboard_key(limit))
    return json.loads(raw) if raw else None


def set_cached_leaderboard(limit: int, entries: list):
    """Stocke le classement en cache pour LEADERBOARD_TTL secondes.

    Redis ne stocke que des chaînes → on sérialise en JSON.
    ex= définit le TTL : expiration automatique, rien à nettoyer.
    """
    redis_client.set(_leaderboard_key(limit), json.dumps(entries), ex=LEADERBOARD_TTL)


def invalidate_leaderboard():
    """Supprime toutes les versions cachées du classement.

    Appelé après chaque nouveau score : le cache est périmé,
    le prochain GET /leaderboard recalculera depuis Postgres.
    """
    keys = redis_client.keys("leaderboard:*")
    if keys:
        redis_client.delete(*keys)


def publish_score_event(score_data: dict):
    """Publie un événement "nouveau score" sur le canal pub/sub.

    publish() est "fire and forget" : s'il n'y a aucun abonné au moment
    de l'envoi, le message est simplement perdu. Ce n'est pas une file
    d'attente persistante — juste un signal en direct.
    """
    redis_client.publish(SCORES_CHANNEL, json.dumps(score_data))
