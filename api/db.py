import config
from pymongo import MongoClient

mongodb_client = MongoClient(config.MONGODB_URI)
db = mongodb_client.time_travellers
