from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from .db import Base


class Player(Base):
    """Un joueur du tableau de scores → table "players"."""

    __tablename__ = "players"

    # Clé primaire : identifiant unique auto-incrémenté
    id = Column(Integer, primary_key=True)
    # Nom du joueur : texte de 50 caractères max, obligatoire et unique
    # (deux joueurs ne peuvent pas avoir le même nom)
    name = Column(String(50), unique=True, nullable=False)

    # Relation vers les scores : player.scores donne la liste des scores du joueur.
    # "back_populates" crée le lien dans les deux sens (voir Score.player).
    # Aucune colonne n'est créée pour ça : c'est juste un raccourci Python.
    scores = relationship("Score", back_populates="player")


class Score(Base):
    """Un score enregistré pour un joueur → table "scores"."""

    __tablename__ = "scores"

    id = Column(Integer, primary_key=True)
    # Clé étrangère : relie chaque score à un joueur de la table "players".
    # Si le joueur n'existe pas, la base refuse l'insertion (intégrité référentielle).
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    # Nombre de points : obligatoire
    points = Column(Integer, nullable=False)
    # Date d'enregistrement : remplie AUTOMATIQUEMENT par Postgres (func.now())
    # au moment de l'insertion, avec fuseau horaire
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relation inverse : score.player donne le joueur associé au score
    player = relationship("Player", back_populates="scores")
