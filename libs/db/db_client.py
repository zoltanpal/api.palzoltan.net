from contextlib import contextmanager

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from libs.db.db_config import DBConfig


class SQLDBClient:
    """
    Database client for managing SQLAlchemy sessions with connection pooling.
    """

    def __init__(
            self, db_config: DBConfig, pool_size: int = 10, max_overflow: int = 5,
            auto_commit: bool = False, auto_flush: bool = False, expire_on_commit: bool = False
    ) -> None:
        """
        Initialize the database client.

        :param db_config: Database configuration object.
        :param pool_size: The number of connections to keep in the pool.
        :param max_overflow: The maximum number of connections that can be created beyond the pool size.
        :param auto_commit: Whether sessions should automatically commit changes.
        :param auto_flush: Whether sessions should automatically flush pending changes.
        :param expire_on_commit: Whether objects should expire after a commit.
        """
        if not db_config:
            raise ValueError("Missing database configuration.")

        self.auto_commit = auto_commit
        self.auto_flush = auto_flush
        self.expire_on_commit = expire_on_commit

        # Construct the database connection string
        self.connection_string: str = (
            f"{db_config.dialect}://{db_config.username}:{db_config.password}"
            f"@{db_config.host}:{db_config.port}/{db_config.dbname}"
        )

        self.engine: Engine = self._create_engine(pool_size, max_overflow)
        self.session_local: sessionmaker = self._create_session_factory()

    def _create_engine(self, pool_size: int, max_overflow: int) -> Engine:
        """
        Create and return the SQLAlchemy engine with connection pooling.

        :param pool_size: The number of connections to keep in the pool.
        :param max_overflow: The maximum number of connections that can be created beyond the pool size.
        :return: SQLAlchemy Engine instance.
        """
        return create_engine(
            self.connection_string,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )

    def _create_session_factory(self) -> sessionmaker:
        """
        Create and return the SQLAlchemy session factory.

        :return: SQLAlchemy sessionmaker instance.
        """
        return sessionmaker(
            bind=self.engine,
            autocommit=self.auto_commit,
            autoflush=self.auto_flush,
            expire_on_commit=self.expire_on_commit,
        )

    @contextmanager
    def get_db_session(self) -> Session:
        """
        Provide a transactional scope around a series of operations.

        :return: A database session object.
        """
        session: Session = self.session_local()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()  # Rollback in case of an error
            raise e
        finally:
            session.close()  # Ensure session is closed properly

    def get_session(self) -> Session:
        """
        Get a new database session.

        :return: A new session instance.
        """
        return self.session_local()
