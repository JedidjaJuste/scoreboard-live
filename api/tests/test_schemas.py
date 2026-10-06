"""Tests de validation Pydantic : l'API refuse les données invalides.

Ces tests ne touchent à aucune base : ils vérifient juste que les
"contrats" (schémas) rejettent ce qu'ils doivent rejeter. Rapide et fiable.
"""

import pytest
from pydantic import ValidationError

from app.schemas import PlayerCreate, ScoreCreate


def test_player_name_too_long_rejected():
    """Un nom de plus de 50 caractères doit être refusé (pas de 500 en base)."""
    with pytest.raises(ValidationError):
        PlayerCreate(name="x" * 51)


def test_player_name_empty_rejected():
    """Un nom vide doit être refusé."""
    with pytest.raises(ValidationError):
        PlayerCreate(name="")


def test_negative_score_rejected():
    """Un score négatif doit être refusé (ge=0 dans le schéma)."""
    with pytest.raises(ValidationError):
        ScoreCreate(player_id=1, points=-10)


def test_valid_payloads_accepted():
    """Des données valides passent sans erreur."""
    player = PlayerCreate(name="Jedidja")
    score = ScoreCreate(player_id=1, points=50)
    assert player.name == "Jedidja"
    assert score.points == 50
