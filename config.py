import os

from dotenv import load_dotenv
from palzlib_db.db_config import DBConfig


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    dotenv_path = os.path.join(ROOT_DIR, ".env")
    load_dotenv(dotenv_path)
except FileNotFoundError:
    print(".env file not found")


# IMDB-API
IMDB_API_URL = os.getenv("IMDB_BASE_URL", default="")
IMDB_API_KEY = os.getenv("IMDB_API_KEY", default="")

USGS_API_HOST = os.getenv("USGS_API_HOST", default="")
WEBUI_USER = os.getenv("WEBUI_USER", default="").split(":")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", default="")

AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", default="")

# Database Configuration
def get_db_config(db_name: str) -> DBConfig:
    return DBConfig(
        dialect=os.getenv("DIALECT", "postgresql+psycopg2"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "mysecretpw"),
        dbname=db_name,
    )


psql_config = get_db_config(os.getenv("DB_NAME", "postgres"))
time_travelers_db_config = get_db_config("time_travellers")
pow_db_config = get_db_config("power_of_words_v2")
pow_live_db_config = get_db_config("power_of_words_live")
