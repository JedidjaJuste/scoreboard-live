"""Tests du calcul du classement (la logique métier).

Stratégie : SQLite EN MÉMOIRE au lieu de Postgres.
- Avantage : aucun serveur à lancer, tests instantanés — idéal pour la CI.
- Limite assumée : on teste la LOGIQUE (tri, totaux, limites), pas le
  dialecte Postgres lui-même. La requête n'utilise que du SQL standard,
  donc le comportement est identique.

Structure classique d'un test : Arrange (préparer) → Act (exécuter) → Assert (vérifier).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.leaderboard import compute_leaderboard
from app.models import Player, Score


def make_session():
    """Crée une base SQLite vide en mémoire et renvoie une session."""
    # sqlite:///:memory: = base temporaire en RAM, détruite à la fin
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db):
    """Remplit la base avec des données connues : Alice (50+30) et Bob (100)."""
    alice = Player(name="Alice")
    bob = Player(name="Bob")
    db.add_all([alice, bob])
    db.commit()  # commit nécessaire pour que les id soient générés
    db.add_all(
        [
            Score(player_id=alice.id, points=50),
            Score(player_id=alice.id, points=30),
            Score(player_id=bob.id, points=100),
        ]
    )
    db.commit()


def test_leaderboard_orders_by_total_desc():
    """Le classement trie par total décroissant : Bob (100) devant Alice (80)."""
    db = make_session()
    seed(db)

    entries = compute_leaderboard(db)

    assert entries[0]["name"] == "Bob"
    assert entries[0]["total_points"] == 100
    assert entries[1]["name"] == "Alice"
    assert entries[1]["total_points"] == 80
    db.close()


def test_leaderboard_respects_limit():
    """Le paramètre limit restreint bien le nombre de lignes."""
    db = make_session()
    seed(db)

    entries = compute_leaderboard(db, limit=1)

    assert len(entries) == 1
    assert entries[0]["name"] == "Bob"  # le premier reste le meilleur
    db.close()


def test_leaderboard_counts_games():
    """Chaque ligne compte aussi le nombre de parties jouées."""
    db = make_session()
    seed(db)

    entries = compute_leaderboard(db)

    alice = next(e for e in entries if e["name"] == "Alice")
    assert alice["games"] == 2
    db.close()


def test_leaderboard_empty_without_scores():
    """Un joueur sans score n'apparaît pas (le JOIN l'exclut)."""
    db = make_session()
    db.add(Player(name="Fantome"))
    db.commit()

    entries = compute_leaderboard(db)

    assert entries == []
    db.close()
