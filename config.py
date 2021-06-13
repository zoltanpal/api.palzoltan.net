# config.py
import os
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LIBS_DIR = os.path.join(BASE_DIR, 'libs')

MONGODB_URI = config['HOSTS']['MONGODB_HOST']

IMDB_BASE_URL = "https://api.themoviedb.org/3/"

try:
	SECRET_KEY = config['KEYS']['SECRET_KEY']
except KeyError as ex:
	SECRET_KEY = None

try:
	IMDB_API_KEY = config['KEYS']['IMDB_API_KEY']
except KeyError as ex:
	IMDB_API_KEY = None

USERS = {
	'admin': config['KEYS']['ADMIN']
}
