import os

from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth

import config

config.load_dotenv()

auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth(scheme='Bearer')

tokens = {
	os.environ['ADMIN_TOKEN']: "admin"
}

@auth.verify_password
def verify(username, password):
	if not (username and password):
		return False
	return config.USERS.get(username) == password


@token_auth.verify_token
def verify_token(token):
	if token in tokens:
		return tokens[token]
