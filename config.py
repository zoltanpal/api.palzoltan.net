"""
project configuration
"""

import copy
import os

from dotenv import load_dotenv

from libs.db.db_config import DBConfig

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LIBS_DIR = os.path.join(ROOT_DIR, "libs")
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

try:
    dotenv_path = os.path.join(ROOT_DIR, ".env")
    load_dotenv(dotenv_path)
except FileNotFoundError:
    print(".env file not found")

try:
    AWS_CORS_ALLOWED_LIST = os.environ["AWS_CORS_ALLOWED_LIST"].split(",")
except KeyError:
    AWS_CORS_ALLOWED_LIST = []

API_NAME = "api.palzoltan.net"
API_DEBUG = True
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", default="DEBUG")

AUTH_ALLOWED_DOMAINS = os.getenv("AUTH_ALLOWED_DOMAINS", default="").split(",")
AUTH_ALLOWED_USERS = os.getenv("AUTH_ALLOWED_USERS", default="").split(",")

# IMDB-API
IMDB_API_URL = os.getenv("IMDB_BASE_URL")
IMDB_API_KEY = os.getenv("IMDB_API_KEY")

USGS_API_HOST = os.getenv("USGS_API_HOST")
WEBUI_USER = os.getenv("WEBUI_USER").split(":")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    
CREDENTIALS = {
    WEBUI_USER[0]: WEBUI_USER[1]
}

psql_config = DBConfig(
    dialect="postgresql+psycopg2",
    username=os.environ["PSQL_USER"],
    password=os.environ["PSQL_PASSWORD"],
    dbname="postgres",
    host=os.environ["PSQL_HOST"],
    port=int(os.getenv("PSQL_PORT", default=5432)),
)

time_travelers_db_config = copy.copy(psql_config)
time_travelers_db_config.dbname = "time_travellers"

pow_db_config = copy.copy(psql_config)
pow_db_config.dbname = "power_of_words"

# city_names_mysql_db_config = copy.copy(psql_config)
# city_names_mysql_db_config.dbname = "city_names"
