# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LIBS_DIR = os.path.join(BASE_DIR, 'libs')

MONGODB_URI = os.environ["MONGODB_HOST"]

DEBUG = True
HOST = '127.0.0.1'
PORT = 8000
API_VERSION = 1


IMDB_BASE_URL = "https://api.themoviedb.org/3/"

try:
	SECRET_KEY = os.environ['SECRET_KEY']
except KeyError as ex:
	SECRET_KEY = None

try:
	IMDB_API_KEY = os.environ['IMDB_API_KEY']
except KeyError as ex:
	IMDB_API_KEY = None

USERS = {
	'admin': os.environ['ADMIN']
}
