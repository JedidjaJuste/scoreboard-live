"""Schémas Pydantic : les "contrats" de l'API.

Deux rôles distincts :
- Les schémas *Create (ex. PlayerCreate) valident ce que le CLIENT ENVOIE.
  Si le JSON ne respecte pas les règles (nom trop long, points négatifs...),
  FastAPI répond 422 automatiquement, sans qu'on écrive le moindre test.
- Les schémas *Out (ex. PlayerOut) décrivent ce que l'API RENVOIE.
  FastAPI filtre la réponse pour ne laisser passer QUE ces champs.

"model_config = {"from_attributes": True}" permet de construire le schéma
directement depuis un objet SQLAlchemy (ex. PlayerOut.model_validate(player)).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PlayerCreate(BaseModel):
    # Ce que le client doit envoyer pour créer un joueur : juste un nom,
    # entre 1 et 50 caractères. L'id sera généré par la base.
    name: str = Field(min_length=1, max_length=50)


class PlayerOut(BaseModel):
    # Ce que l'API renvoie après création : id + nom (jamais le mot de passe
    # s'il y en avait un — c'est ici qu'on choisit ce qui est exposé).
    id: int
    name: str

    model_config = {"from_attributes": True}


class ScoreCreate(BaseModel):
    # Pour enregistrer un score : l'id du joueur + les points.
    # ge=0 (greater or equal) interdit les scores négatifs.
    player_id: int
    points: int = Field(ge=0)


class ScoreOut(BaseModel):
    # Ce que l'API renvoie : le score complet, avec sa date de création.
    id: int
    player_id: int
    points: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    # Une ligne du classement : pas une table, juste une forme de réponse
    # construite par la requête d'agrégation (JOIN + GROUP BY + SUM).
    player_id: int
    name: str
    total_points: int
    games: int


class PlayerDetail(PlayerOut):
    # Un joueur AVEC ses scores : on hérite de PlayerOut (id + name déjà là)
    # et on ajoute la liste des scores. Le "= []" donne une liste vide
    # par défaut pour un joueur qui n'a encore jamais joué.
    scores: list[ScoreOut] = []
