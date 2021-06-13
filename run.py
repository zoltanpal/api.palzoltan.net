from flask import Flask
from flask_cors import CORS

from config import config
from api.time_travellers.time_travellers import time_travellers
from api.climate_change.climate_change import climate_change
from api.movie_connections.movie_connections import movie_connections


def create_app():
	app = Flask(__name__)
	app.config.from_object('config')
	app.config['CORS_HEADERS'] = 'Content-Type'
	app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
	app.config["DEBUG"] = config['API']['DEBUG']
	
	CORS(app)
	return app


def run(app, host, port):
	app.run(host=host, port=port, threaded=True)


def register_blueprint(app, api_bp, endpoint):
	app.register_blueprint(api_bp, url_prefix=f'/v{config["API"]["API_VERSION"]}/{endpoint}')


if __name__ == "__main__":
	app = create_app()

	register_blueprint(app, time_travellers, 'time_travellers')
	register_blueprint(app, climate_change, 'climate_change')
	register_blueprint(app, movie_connections, 'movie_connections')
	run(app, config['API']['HOST'], int(config['API']['PORT']))
