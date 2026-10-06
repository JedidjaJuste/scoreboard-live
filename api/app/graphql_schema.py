"""Schéma GraphQL (Strawberry) : interroger les stats librement.

Différence fondamentale avec REST : ici c'est le CLIENT qui choisit
les champs qu'il veut, dans une seule requête :
- juste les noms ?            { players { name } }
- avec les scores en plus ?    { players { name scores { points } } }
Pas de nouvel endpoint à créer : le schéma expose tout, le client trie.

Strawberry transforme des classes Python décorées en schéma GraphQL :
@strawberry.type  → un type GraphQL
@strawberry.field → un champ / une requête (un "resolver")
Le schéma généré sert aussi de documentation interactive (GraphiQL).
"""

from datetime import datetime

import strawberry
from sqlalchemy.orm import selectinload
from strawberry.fastapi import GraphQLRouter

from . import models
from .db import SessionLocal
from .leaderboard import get_fresh_leaderboard


@strawberry.type
class ScoreType:
    """Un score, tel qu'exposé en GraphQL."""

    id: int
    points: int
    # strawberry sérialise datetime tout seul (scalaire DateTime)
    created_at: datetime


@strawberry.type
class PlayerType:
    """Un joueur. Le champ "scores" n'est chargé que si le client
    le demande — c'est ça qui élimine le sur-fetching."""

    id: int
    name: str
    scores: list[ScoreType]


@strawberry.type
class LeaderboardEntryType:
    """Une ligne du classement."""

    player_id: int
    name: str
    total_points: int
    games: int


@strawberry.type
class Query:
    """Tous les points d'entrée du graphe. Chaque méthode est un "resolver" :
    une fonction Python exécutée quand le client demande ce champ."""

    @strawberry.field
    def players(self) -> list[PlayerType]:
        """Tous les joueurs, avec leurs scores pré-chargés."""
        db = SessionLocal()
        try:
            # selectinload : charge les scores en UNE requête supplémentaire,
            # au lieu d'une requête par joueur (le piège classique "N+1").
            players = (
                db.query(models.Player)
                .options(selectinload(models.Player.scores))
                .order_by(models.Player.id)
                .all()
            )
            return [
                PlayerType(
                    id=p.id,
                    name=p.name,
                    scores=[
                        ScoreType(id=s.id, points=s.points, created_at=s.created_at)
                        for s in p.scores
                    ],
                )
                for p in players
            ]
        finally:
            db.close()

    @strawberry.field
    def player(self, player_id: int) -> PlayerType | None:
        """Un joueur par son id. None → GraphQL renvoie null (pas d'erreur).

        Note : l'argument s'écrit player_id en Python mais playerId
        en GraphQL — strawberry convertit en camelCase automatiquement.
        """
        db = SessionLocal()
        try:
            p = (
                db.query(models.Player)
                .options(selectinload(models.Player.scores))
                .filter_by(id=player_id)
                .first()
            )
            if not p:
                return None
            return PlayerType(
                id=p.id,
                name=p.name,
                scores=[
                    ScoreType(id=s.id, points=s.points, created_at=s.created_at)
                    for s in p.scores
                ],
            )
        finally:
            db.close()

    @strawberry.field
    def leaderboard(self, limit: int = 10) -> list[LeaderboardEntryType]:
        """Le classement — réutilise la même fonction que REST et WebSockets.
        Une seule source de vérité, trois façons de la servir."""
        return [LeaderboardEntryType(**e) for e in get_fresh_leaderboard(limit)]


# Le schéma complet, introspecté par strawberry pour générer la doc.
schema = strawberry.Schema(query=Query)

# Le router FastAPI : expose le schéma sur /graphql, avec l'explorateur
# interactif GraphiQL directement dans le navigateur.
router = GraphQLRouter(schema)
