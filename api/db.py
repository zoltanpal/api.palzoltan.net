"""
MongoDB Client connection
"""
from pymongo import MongoClient

import config

mongodb_client = MongoClient(config.MONGODB_URI)