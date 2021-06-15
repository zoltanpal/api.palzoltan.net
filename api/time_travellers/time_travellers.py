# time_travellers.py

from bson.objectid import ObjectId
from flask import Blueprint, jsonify, abort, request
from flask_restful import reqparse

from api import auth, token_auth
from api.db import mongodb_client
from libs.common_functions import transform_mongodb_response
import json
from . import person_schema


time_travellers = Blueprint('time_travellers', __name__)

db = mongodb_client.time_travellers


@time_travellers.route('/', methods=['GET'])
def home():
    return 'Welcome at Time Travellers API!'


@time_travellers.route('/persons', methods=['GET'])
@token_auth.login_required
def persons():
    """
    Get all the documents in persons collection

    :return: persons json
    """
    cursor = db.persons.find()
    raw_data = [doc for doc in cursor]
    data = transform_mongodb_response(raw_data)

    return jsonify(data)


@time_travellers.route('/persons/list', methods=['GET'])
@token_auth.login_required
def persons_list():
    """
    List of persons
    :return: ID:PersonName list
    """
    cursor = db.persons.find({}, {'_id': 1, 'name': 1, 'other_name': 1})
    raw_data = [doc for doc in cursor]

    data = {}
    for e in raw_data:
        if ('other_name' in e.keys() and e['other_name'] != ''):
            data[str(e['_id'])] = f'{e["name"]} ({e["other_name"]})'
        else:
            data[str(e['_id'])] = e['name']

    return jsonify(data)


@time_travellers.route('/person/<person_id>', methods=['GET'])
@token_auth.login_required
def get_person(person_id):
    """
    Return person object by ID
    
    :param person_id: Person ObjectId
    :return:
    """
    if (ObjectId.is_valid(person_id)):
        raw_data = db.persons.find_one({"_id": ObjectId(person_id)})
        raw_data['_id'] = str(raw_data['_id'])

        return jsonify(raw_data)

    else:
        return jsonify({"status": 405, "message": "The ID is not valid!"}), 405


@time_travellers.route('/person/<person_id>/trips', methods=['GET'])
@token_auth.login_required
def get_person_trips(person_id):
    """
    Get person's trips
    
    :param person_id: Person ObjectId
    :return:
    """
    if (ObjectId.is_valid(person_id)):
        data = {}

        person = db.persons.find_one({"_id": ObjectId(person_id)})

        if person:
            person['_id'] = str(person['_id'])
            data['person'] = person

            cursor = db.trips.aggregate([
                {"$lookup": {
                    "from": "persons",
                    "localField": "person",
                            "foreignField": "_id",
                            "as": "Person"
                }},
                {"$unwind": "$Person"},
                {"$lookup": {
                    "from": "dates",
                    "localField": "date",
                            "foreignField": "_id",
                            "as": "Date"
                }},
                {"$unwind": "$Date"},
                {"$project": {
                    "_id": 0,
                    "movie": 1,
                    "movie_imdb_url": 1,
                    "order": 1,
                    "Date": "$Date.date",
                            "DateId": "$Date._id",
                            "PersonId": "$Person._id",
                            "TripId": "$_id",
                }},
                {"$match": {"PersonId": ObjectId(person_id)}},
                {"$sort": {"order": 1}}
            ])
            trips = [doc for doc in cursor]
            data['trips'] = transform_mongodb_response(trips, ['TripId', 'DateId', 'PersonId'])

            return jsonify(data)
        else:
            return jsonify({"status": 405, "message": "No Person with this ID: '{}'!".format(str(person_id))}), 405

    else:
        return jsonify({"status": 405, "message": "The ID is not valid!"}), 405


@time_travellers.route('/person', methods=['POST'])
@token_auth.login_required
def person_add():
    """
    
    :return:
    """

    data = json.loads(request.data)
    errors = person_schema.validate(data)
    if errors:
        return jsonify({
            'status_code': 400,
            'message': 'Missing request arguments',
            'error_msg': errors
        })

    
    if not data:
        return jsonify("Missing data"), 400

    #data['created'] = ''

    try:
        db.persons.insert_one(data)
        return jsonify("INSERTED"), 200
    except BaseException as ex:
        abort(400)



@time_travellers.route('/person/<person_id>', methods=['PUT'])
@token_auth.login_required
def person_edit(person_id):
    """
    
    :param person_id:
    :return:
    """

    data = json.loads(request.data)
    errors = person_schema.validate(data)
    if errors:
        return jsonify({
            'status_code': 400,
            'message': 'Missing request arguments',
            'error_msg': errors
        })


    db.persons.update_one({'_id': ObjectId(person_id)}, {"$set": data})
    return jsonify("UPDATED"), 200


@time_travellers.route('/person/<person_id>', methods=['DELETE'])
@token_auth.login_required
def person_delete(person_id):
    """
    
    :param person_id:
    :return:
    """
    try:
        db.persons.delete_one({'_id': ObjectId(person_id)})
        return jsonify("DELETED"), 200
    except BaseException as ex:
        abort(400)


# DATES
dates_args = reqparse.RequestParser()
dates_args.add_argument("date", type=str, required=True)


@time_travellers.route('/dates', methods=['GET'])
@token_auth.login_required
def dates():
    """
    
    :return:
    """
    cursor = db.dates.find()
    raw_data = [doc for doc in cursor]
    data = transform_mongodb_response(raw_data)

    return jsonify(data)


@time_travellers.route('/dates/list', methods=['GET'])
@token_auth.login_required
def dates_list():
    """
    
    :return:
    """
    cursor = db.dates.find({}, {'_id': 1, 'date': 1}).sort([('date', 1)])
    raw_data = [doc for doc in cursor]

    data = {}
    for e in raw_data:
        data[str(e['_id'])] = e['date']

    return jsonify(data)


@time_travellers.route('/date/<date_id>', methods=['GET'])
@token_auth.login_required
def get_date(date_id):
    """
    
    :param date_id:
    :return:
    """
    if ObjectId.is_valid(date_id):
        date = db.dates.find_one({"_id": ObjectId(date_id)})
        date['_id'] = str(date['_id'])

        return jsonify(date)

    else:
        return jsonify({"status": 405, "message": "The ID is not valid!"}), 405


@time_travellers.route('/date/add', methods=['POST'])
@token_auth.login_required
def date_add():
    """
    
    :return:
    """
    data = dates_args.parse_args()
    if not data:
        abort(400)

    try:
        db.dates.insert_one(data)
        return jsonify("INSERTED"), 200
    except BaseException as ex:
        abort(400)


@time_travellers.route('/date/edit/<date_id>', methods=['PUT'])
@token_auth.login_required
def date_edit(date_id):
    """
    
    :param date_id:
    :return:
    """
    data = dates_args.parse_args()
    if not data:
        abort(400)

    db.dates.update_one({'_id': ObjectId(date_id)}, {"$set": data})
    return jsonify("UPDATED"), 200


@time_travellers.route('/date/<date_id>', methods=['DELETE'])
@token_auth.login_required
def date_delete(date_id):
    """
    
    :param date_id:
    :return:
    """
    try:
        db.dates.delete_one({'_id': ObjectId(date_id)})
        return jsonify("DELETED"), 200
    except BaseException as ex:
        abort(400)


# TRIPS
trips_args = reqparse.RequestParser()
trips_args.add_argument("person", type=ObjectId, required=True)
trips_args.add_argument("date", type=ObjectId, required=True)
trips_args.add_argument("movie", type=str, required=True)
trips_args.add_argument("movie_year", type=str)
trips_args.add_argument("order", type=int, required=True)


@time_travellers.route('/trips', methods=['GET'])
@token_auth.login_required
def trips():
    """
    
    :return:
    """
    params = request.args.to_dict()
    where = {}
    if 'order' in params.keys() and params['order'] == 'gt0':
        where = {"order": {"$gt": 0}}

    cursor = db.trips.aggregate([
        {"$lookup": {
            "from": "persons",
            "localField": "person",
            "foreignField": "_id",
            "as": "Person"
        }},
        {"$unwind": "$Person"},
        {"$lookup": {
            "from": "dates",
            "localField": "date",
            "foreignField": "_id",
            "as": "Date"
        }},
        {"$unwind": "$Date"},
        {"$project": {
            "_id": 1,
            "movie": 1,
            "movie_imdb_url": 1,
            "order": 1,
            "PersonName": "$Person.name",
            "PersonOtherName": "$Person.other_name",
            "PersonId": "$Person._id",
            "Date": "$Date.date",
            "DateId": "$Date._id"
        }},
        {"$match": where},
        {"$sort": {"order": 1}}
        
    ])

    raw_data = [doc for doc in cursor]

    data = transform_mongodb_response(raw_data, ["_id", "DateId", "PersonId"])

    return jsonify(data)


@time_travellers.route('/trip/<trip_id>', methods=['GET'])
@token_auth.login_required
def get_trip(trip_id):
    """
    
    :param trip_id:
    :return:
    """
    if (ObjectId.is_valid(trip_id)):
        trip = db.trips.find_one({"_id": ObjectId(trip_id)})
        trip['_id'] = str(trip['_id'])

        return jsonify(trip)

    else:
        return jsonify({"status": 405, "message": "The ID is not valid!"}), 405


@time_travellers.route('/trip/add', methods=['POST'])
@token_auth.login_required
def trip_add():
    """
    
    :return:
    """
    data = trips_args.parse_args()
    if not data:
        abort(400)

    try:
        db.trips.insert_one(data)
        return jsonify("INSERTED"), 200
    except BaseException as ex:
        abort(400)


@time_travellers.route('/trip/edit/<trip_id>', methods=['PUT'])
@token_auth.login_required
def trip_edit(trip_id):
    """
    
    :param trip_id:
    :return:
    """
    data = trips_args.parse_args()
    if not data:
        abort(400)

    db.trips.update_one({'_id': ObjectId(trip_id)}, {"$set": data})
    return jsonify("UPDATED"), 200


@time_travellers.route('/trip/delete/<trip_id>', methods=['DELETE'])
@token_auth.login_required
def trip_delete(trip_id):
    """
    
    :param trip_id:
    :return:
    """
    try:
        db.trips.delete_one({'_id': ObjectId(trip_id)})
        return jsonify("DELETED"), 200
    except BaseException as ex:
        abort(400)


@time_travellers.route('/movies', methods=['GET'])
@token_auth.login_required
def movies():
    """
    Get unique list of movies object
    :return:
    """
    cursor = db.trips.find({}, {"_id": 0, "movie": 1, "movie_year": 1, "movie_imdb_url": 1}).sort([('movie', 1)])
    raw_data = [doc for doc in cursor]
    raw_data = transform_mongodb_response(raw_data)
    movies = list({value['movie']: value for value in raw_data}.values())

    return jsonify(movies)


@time_travellers.route('/movies/list', methods=['GET'])
@token_auth.login_required
def movies_list():
    """
    Get unique list of movies
    :return:
    """

    cursor = db.trips.find({}, {"_id": 0, "movie": 1, "movie_year": 1}).sort([('movie', 1)])
    movies = list({value['movie']: value for value in cursor}.values())
    list_movies = ["%s (%s)" % (doc['movie'], doc['movie_year']) for doc in movies]

    return jsonify(list_movies)
