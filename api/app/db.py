import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# URL de connexion à Postgres.
# "postgresql+psycopg://" = on utilise le pilote psycopg v3
# (SQLAlchemy chercherait psycopg2 par défaut, qu'on n'a pas installé).
# Dans Docker, le nom d'hôte "db" correspond au service postgres du docker-compose.
# En local (hors Docker), on retombe sur localhost.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://scoreboard:scoreboard@localhost:5432/scoreboard",
)

# L'engine = la connexion à la base de données.
# Il est créé UNE SEULE FOIS au démarrage et gère un pool de connexions
# (plusieurs requêtes peuvent l'utiliser en même temps sans se marcher dessus).
engine = create_engine(DATABASE_URL)

# SessionLocal = une "fabrique" de sessions.
# Une session = une conversation temporaire avec la base :
# on y ajoute/modifie des objets, puis on fait commit() pour valider
# ou rollback() pour tout annuler.
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Classe mère de tous nos modèles.

    Chaque classe qui hérite de Base devient une TABLE en base de données
    (grâce à l'attribut __tablename__). C'est le principe de l'ORM :
    on manipule des objets Python, SQLAlchemy génère le SQL.
    """
    pass


def get_db():
    """Dépendance FastAPI : fournit une session de base de données
    à chaque endpoint qui en a besoin.

    Le "yield" fait de cette fonction un générateur : FastAPI exécute
    le code AVANT le yield pour préparer la session, puis le code APRÈS
    (dans le finally) une fois la requête terminée — la session est donc
    toujours fermée proprement, même en cas d'erreur.
    Usage dans un endpoint : db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
