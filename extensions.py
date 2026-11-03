from flask_sqlalchemy import SQLAlchemy


class DatabaseSingleton:
    """Patrón de diseño Singleton para garantizar una única instancia del ORM."""

    _instance = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._db = SQLAlchemy()
        return cls._instance

    @property
    def db(self) -> SQLAlchemy:
        return self._db

    def init_app(self, app) -> None:
        self._db.init_app(app)


db_manager = DatabaseSingleton()
db = db_manager.db
