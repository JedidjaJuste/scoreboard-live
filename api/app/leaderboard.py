"""Logique du classement, partagée entre REST, WebSockets et GraphQL.

Extraite dans son propre module : UNE SEULE requête SQL, trois façons
de la servir. Si la règle de calcul change demain, on la modifie ici
et tout le monde en profite — c'est le principe DRY (Don't Repeat Yourself).
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .db import SessionLocal


def compute_leaderboard(db: Session, limit: int = 10) -> list[dict]:
    """Calcule le classement depuis Postgres.

    La requête "coûteuse" (JOIN + GROUP BY + SUM) : on veut éviter
    de la relancer à chaque appel → d'où le cache Redis autour (REST).
    """
    rows = (
        db.query(
            models.Player.id.label("player_id"),
            models.Player.name,
            # SUM(points) par joueur...
            func.sum(models.Score.points).label("total_points"),
            # ...et nombre de parties jouées
            func.count(models.Score.id).label("games"),
        )
        # JOIN : on ne garde que les joueurs qui ont au moins un score
        .join(models.Score, models.Score.player_id == models.Player.id)
        # GROUP BY : une ligne de résultat par joueur
        .group_by(models.Player.id, models.Player.name)
        # ORDER BY : les plus gros totaux en premier
        .order_by(func.sum(models.Score.points).desc())
        .limit(limit)
        .all()
    )
    # Liste de dictionnaires : chaque consommateur (REST, WS, GraphQL)
    # la met en forme à sa façon.
    return [
        {
            "player_id": r.player_id,
            "name": r.name,
            "total_points": r.total_points,
            "games": r.games,
        }
        for r in rows
    ]


def get_fresh_leaderboard(limit: int = 10) -> list[dict]:
    """Recalcule le classement hors contexte de requête HTTP.

    Utilisé par la tâche WebSocket et GraphQL : il n'y a pas de
    Depends(get_db) en dehors d'une requête, donc on ouvre
    une session dédiée.
    """
    db = SessionLocal()
    try:
        return compute_leaderboard(db, limit)
    finally:
        db.close()
