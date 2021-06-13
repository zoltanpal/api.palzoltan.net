import os
from config import USERS as users
from config import config
from flask_httpauth import HTTPBasicAuth, HTTPTokenAuth


auth = HTTPBasicAuth()
token_auth = HTTPTokenAuth(scheme='Bearer')

tokens = {
	config['KEYS']['ADMIN_TOKEN']: "admin"
}

@auth.verify_password
def verify(username, password):
	if not (username and password):
		return False
	return users['username'] == password


@token_auth.verify_token
def verify_token(token):
	if token in tokens:
		return tokens[token]
