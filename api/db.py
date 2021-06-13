"""
MongoDB Client connection
"""
from pymongo import MongoClient

from config import config

mongodb_client = MongoClient(config['HOSTS']['MONGODB_HOST'])