# movie_connections.py

import urllib.request as urllib
from urllib.parse import quote

from flask import Blueprint, jsonify, request

import config
from api import token_auth
from api.db import mongodb_client
from libs.common_functions import check_parameters
import json

movie_connections = Blueprint('movie_connections', __name__)

DB = mongodb_client.local


@movie_connections.route('/', methods=['GET'])
def home():
    return 'Welcome at Movie Connections API!'


def get_data_from_url(url):
    try:
        req = urllib.Request(url)
        response = urllib.urlopen(req)
        content = response.read()
        return content.decode()
    except:
        return False


@movie_connections.route('/person/search', methods=['GET'])
@token_auth.login_required
@check_parameters(['q'])
def person_search():
    params = request.args.to_dict()
    q = quote(params['q'])

    url = '{}search/person?api_key={}&query={}&sort_by=popularity.desc'.format(config.IMDB_BASE_URL,
                                                                               config.IMDB_API_KEY, q)
    resp = get_data_from_url(url)

    if resp:
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@movie_connections.route('/person/<person_id>/movies', methods=['GET'])
@token_auth.login_required
def person_movies(person_id):
    url = '{}person/{}/movie_credits?api_key={}&language={}'.format(config.IMDB_BASE_URL, person_id,
                                                                    config.IMDB_API_KEY,
                                                                    'hun')
    resp = get_data_from_url(url)

    if resp:
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@movie_connections.route('/person/<person_id>/external_ids', methods=['GET'])
@token_auth.login_required
def person_external_ids(person_id):
    url = '{}person/{}/external_ids?api_key={}&language={}'.format(config.IMDB_BASE_URL, person_id, config.IMDB_API_KEY,
                                                                   'hun')
    resp = get_data_from_url(url)

    if resp:
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@movie_connections.route('/movie/<movie_id>/external_ids', methods=['GET'])
@token_auth.login_required
def movie_external_ids(movie_id):
    url = '{}movie/{}/external_ids?api_key={}&language={}'.format(config.IMDB_BASE_URL, movie_id, config.IMDB_API_KEY,
                                                                  'hun')
    resp = get_data_from_url(url)

    if resp:
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405



'''
@movie_connections.route('/person/common_movies', methods=['GET'])
@token_auth.login_required
@check_parameters(['persons'])
def person_common_movies():
    params = request.args.to_dict()
    persons = params['persons']
    url = '{}discover/movie?api_key={}&with_people={}'.format(config.IMDB_BASE_URL, config.IMDB_API_KEY,
                                                              persons)

    resp = get_data_from_url(url)
    raw_data = json.loads(resp)
    return jsonify(raw_data)
'''


@movie_connections.route('/person/common_movies', methods=['GET'])
@token_auth.login_required
@check_parameters(['persons'])
def person_common_movies():
    params = request.args.to_dict()
    persons = params['persons'].split(',')
    movies = {}
    persons_movies = {}
    for person_id in persons:
        url = '{}person/{}/movie_credits?api_key={}&language={}'.format(config.IMDB_BASE_URL, person_id,
                                                                        config.IMDB_API_KEY,
                                                                        'hun')

        resp = get_data_from_url(url)
        raw_data = json.loads(resp)

        for item in raw_data['cast']:
            movie = {
                'person_id': int(person_id),
                'movie_id': int(item['id']),
                'character': item['character'],
                'title': item['title'],
                'original_title': item['original_title'],
                'popularity': item['popularity'],
                'overview': item['overview'],
                'poster_path': item['poster_path'],
                'release_date': item['release_date']
            }
            movies.setdefault(person_id, []).append(movie)
            persons_movies.setdefault(person_id, []).append(int(item['id']))

        for item in raw_data['crew']:
            
            movie = {
                'person_id': int(person_id),
                'movie_id': int(item['id']),
                'job': item['job'],
                'title': item['title'],
                'original_title': item['original_title'],
                'popularity': item['popularity'],
                'overview': item['overview'],
                'poster_path': item['poster_path'],
                'release_date': item['release_date']
            }
            movies.setdefault(person_id, []).append(movie)
            persons_movies.setdefault(person_id, []).append(int(item['id']))




    return jsonify(movies)
