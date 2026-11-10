from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

sqlite_file_name = "graphql_database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
from pathlib import Path

DB_FILE_PATH = Path(__file__).resolve().parent / "graphql_database.db"
sqlite_url = f"sqlite:///{DB_FILE_PATH}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
