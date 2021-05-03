# -*- coding: utf-8 -*-

import datetime
import functools

from flask import Blueprint, jsonify, request
from flask_restful import reqparse

from api import token_auth
from api.db import mongodb_client
from libs.common_functions import validate_date, last_day_of_month


DB = mongodb_client.climate_change
DISTRIBUTIONS = ['daily', 'monthly', 'annual']

climate_change = Blueprint('climate_change', __name__)

request_args = reqparse.RequestParser()

@climate_change.route('/', methods=['GET'])
def home():
    return 'Welcome at Climate Change API!'


def check_parameters(expected_args):
    """
    Check request paramters
    :param expected_args: list of expected arguments
    :return: True or error
    """

    def decorator_validate_json(func):
        @functools.wraps(func)
        def wrapper_validate_json(*args, **kwargs):
            params = request.args.to_dict()
            for expected_arg in expected_args:
                if expected_arg not in params:
                    error_msg = f'Missing parameter: {expected_arg}'
                    return jsonify({"status": "Error", "message": error_msg}), 400
                else:
                    if params[expected_arg] == '':
                        error_msg = f'{expected_arg} parameter should not be empty'
                        return jsonify({"status": "Error", "message": error_msg}), 400

                    if expected_arg == 'distribution' and params[expected_arg] not in DISTRIBUTIONS:
                        error_msg = 'Invalid distribution parameter value: {}. The parameter value should be one of the following: {}'.format(
                            params[expected_arg], ','.join(DISTRIBUTIONS))
                        return jsonify({"status": "Error", "message": error_msg}), 400

                    if expected_arg in ['start_date', 'end_date']:
                        if validate_date(params[expected_arg]) == False:
                            error_msg = f'Incorrect {expected_arg} date format, should be YYYY-MM-DD'
                            return jsonify({"status": "Error", "message": error_msg}), 400

            return func(*args, **kwargs)

        return wrapper_validate_json

    return decorator_validate_json


@climate_change.route('/weather_history', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date', 'distribution'])
def weather_history():
    """

    :return: json object
    """
    PARAMS = request.args.to_dict()

    if PARAMS['distribution'] == 'daily':
        cursor = DB.weather_history.find(
            {'date': {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}, {'_id': 0})

    else:
        group_by = {"year": {"$substr": ["$date", 0, 4]}}

        if PARAMS['distribution'] == 'monthly':
            group_by = {
                "year": {"$substr": ["$date", 0, 4]},
                "month": {"$substr": ["$date", 5, 2]}
            }
        cursor = DB.weather_history.aggregate(
            [{"$match": {"date": {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}}, {
                "$group": {"_id": group_by, "tempAvg": {"$avg": "$daily_medium"},
                           "tempMaxAvg": {"$avg": "$daily_max"}, "tempMinAvg": {"$avg": "$daily_min"},
                           "sunshineMax": {"$max": "$sunshine"},
                           "sunMaxGroup": {"$push": {'date': '$date', 'sunshineMax': '$sunshine', }},
                           "sunshineAvg": {"$avg": "$sunshine"}, "sunshineSum": {"$sum": "$sunshine"},
                           "precipitationMax": {"$max": "$precipitation"},
                           "preMaxGroup": {"$push": {'date': '$date', 'precipitationMax': '$precipitation', }},
                           "precipitationAvg": {"$avg": "$precipitation"},
                           "precipitationSum": {"$sum": "$precipitation"}, }}, {
                 "$project": {'_id': 1, 'tempAvg': 1, 'tempMaxAvg': 1, 'tempMinAvg': 1, 'sunshineMax': {
                     '$setDifference': [{'$map': {'input': '$sunMaxGroup', 'as': 'date', 'in': {
                         '$cond': [{'$eq': ['$sunshineMax', '$$date.sunshineMax']}, '$$date', False]}, }, },
                                        [False]]}, 'sunshineAvg': 1, 'sunshineSum': 1, 'precipitationMax': {
                     '$setDifference': [{'$map': {'input': '$preMaxGroup', 'as': 'date', 'in': {
                         '$cond': [{'$eq': ['$precipitationMax', '$$date.precipitationMax']}, '$$date',
                                   False]}, }, }, [False]]}, 'precipitationAvg': 1, 'precipitationSum': 1}},
             {"$sort": {"_id.year": 1, "_id.month": 1}}])

    if cursor:
        resp = [doc for doc in cursor]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/compare_years', methods=['GET'])
@token_auth.login_required
@check_parameters(['years', 'distribution'])
def compare_years():
    """

    :return:
    """
    PARAMS = request.args.to_dict()
    PARAMS['years'] = PARAMS['years'].split(',')

    where_years = []
    for year in PARAMS['years']:
        obj = {
            'date': {"$gte": year + '-01-01', "$lte": year + '-12-31'}
        }
        where_years.append(obj)

    if PARAMS['distribution'] == 'daily':
        cursor = DB.weather_history.aggregate([{"$match": {'$or': where_years}}, {"$project": {"_id": 0}}])
    else:
        cursor = DB.weather_history.aggregate([{"$match": {'$or': where_years}}, {
            "$group": {"_id": {"year": {"$substr": ["$date", 0, 4]}, "month": {"$substr": ["$date", 5, 2]}},
                       "tempMax": {"$max": "$daily_max"}, "tempMin": {"$min": "$daily_min"},
                       "tempAvg": {"$avg": "$daily_medium"}, "sunshineMax": {"$max": "$sunshine"},
                       "sunshineAvg": {"$avg": "$sunshine"}, "sunshineSum": {"$sum": "$sunshine"},
                       "precipitationMax": {"$max": "$precipitation"},
                       "precipitationAvg": {"$avg": "$precipitation"},
                       "precipitationSum": {"$sum": "$precipitation"}, }},
                                               {"$sort": {"_id.year": 1, "_id.month": 1}}])

    if cursor:
        resp = [doc for doc in cursor]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/precipitation_distribution', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date'])
def precipitation_distribution():
    """
    Get precipition data
    PARAMS:
    - years: string->comma separated list
    - distribution: string
    """
    PARAMS = request.args.to_dict()

    main_data = DB.weather_history.aggregate([
        {"$match": {"date": {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}},
        {"$group": {
            "_id": {
                "precipitation_type": "$precipitation_type",
                "year": {"$substr": ["$date", 0, 4]}
            },
            "precipitation": {"$sum": "$precipitation"},
            "months": {
                "$push": {
                    "month": {"$substr": ["$date", 5, 2]},
                    "mm": "$precipitation"
                }
            },
        }},
        {"$project": {
            "_id": 1,
            "precipitation": 1,
            "months": 1
        }},
        {"$sort": {"_id.precipitation_type": 1}}
    ])

    drilldown = DB.weather_history.aggregate([
        {"$match": {"date": {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}},
        {"$group": {
            "_id": {
                "precipitation_type": "$precipitation_type",
                "year": {"$substr": ["$date", 0, 4]},
                "month": {"$substr": ["$date", 5, 2]},
            },
            "precipitation": {"$sum": "$precipitation"},
            "days": {
                "$push": {
                    "day": {"$substr": ["$date", 8, 2]},
                    # "precipitation_type":"$precipitation_type",
                    "mm": "$precipitation"
                }
            }
        }},
        {"$project": {
            "_id": 1,
            "precipitation": 1,
            "days": 1
        }},
        {"$sort": {
            "_id.precipitation_type": 1,
            "_id.month": 1
        }}
    ])

    if main_data and drilldown:
        resp = {'data': [doc for doc in main_data], 'drilldown': [doc for doc in drilldown]}
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/precipitaion_sunshine_sum', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date', 'distribution'])
def precipitaion_sunshine_sum():
    """
    Sum data of precipitation and Sunshine
    PARAMS:
    - start_date: string
    - end_date: string
    - distribution: string
    """
    PARAMS = request.args.to_dict()
    if PARAMS['distribution'] == 'daily':
        group_by = {
            "year": {"$substr": ["$date", 0, 4]},
            "month": {"$substr": ["$date", 5, 2]},
            "day": {"$substr": ["$date", 8, 2]}
        }
    elif PARAMS['distribution'] == 'monthly':
        group_by = {
            "year": {"$substr": ["$date", 0, 4]},
            "month": {"$substr": ["$date", 5, 2]}
        }
    else:
        group_by = {
            "year": {"$substr": ["$date", 0, 4]}
        }

    result = DB.weather_history.aggregate(
        [{"$match": {"date": {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}}, {
            "$group": {"_id": group_by, "sunshineSum": {"$sum": "$sunshine"},
                       'precipitation_types': {"$addToSet": '$precipitation_type'},
                       "precipitations": {"$push": {"type": '$precipitation_type', "mm": "$precipitation"}},
                       "precipitationSum": {"$sum": "$precipitation"}, }}, {
             "$project": {'_id': 1, 'sunshineSum': 1, 'precipitationSum': 1,
                          'precipitations': {"$setDifference": ["$precipitations", [None]]}}},
         {"$sort": {"_id.year": 1, "_id.month": 1}}])
    if result:
        resp = [doc for doc in result]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


def get_extremes(params):
    return DB.weather_history.find({'date': {"$gte": params['start_date'], "$lte": params['end_date']},
                                    params['field']: {params['field_sign']: params['field_value']}},
                                   {'_id': 0, 'date': 1, params['field']: 1})


@climate_change.route('/extremes_frequency', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date', 'reports'])
def extremes_frequency():
    PARAMS = request.args.to_dict()

    response = {}
    for r in PARAMS['reports'].split(','):
        if r == 'cold_days':
            PARAMS['field'] = 'daily_min'
            PARAMS['field_sign'] = '$lte'
            PARAMS['field_value'] = 0.00
            response[r] = [doc for doc in get_extremes(PARAMS)]
        elif r == 'freezing_days':
            PARAMS['field'] = 'daily_min'
            PARAMS['field_sign'] = '$lte'
            PARAMS['field_value'] = -10.00
            response[r] = [doc for doc in get_extremes(PARAMS)]
        elif r == 'hot_nights':
            PARAMS['field'] = 'daily_min'
            PARAMS['field_sign'] = '$gte'
            PARAMS['field_value'] = 20.00
            response[r] = [doc for doc in get_extremes(PARAMS)]
        elif r == 'warm_days':
            PARAMS['field'] = 'daily_max'
            PARAMS['field_sign'] = '$gte'
            PARAMS['field_value'] = 30.00
            response[r] = [doc for doc in get_extremes(PARAMS)]
        elif r == 'hot_days':
            PARAMS['field'] = 'daily_max'
            PARAMS['field_sign'] = '$gte'
            PARAMS['field_value'] = 35.00
            response[r] = [doc for doc in get_extremes(PARAMS)]
        elif r == 'extreme_cold_days':
            PARAMS['field'] = 'daily_min'
            PARAMS['field_sign'] = '$lte'
            PARAMS['field_value'] = -15.00
            response[r] = [doc for doc in get_extremes(PARAMS)]

    if response:
        return jsonify(response)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/custom_report', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date', 'riport_type', 'value', 'sign', 'minmaxavg'])
def custom_report():
    PARAMS = request.args.to_dict()

    if PARAMS['riport_type'] == 'temp':
        field = 'daily_{}'.format(PARAMS['minmaxavg'])
    elif PARAMS['riport_type'] == 'sun':
        field = 'sunshine'
    else:
        field = 'precipitation'

    field_sign = '${}'.format(PARAMS['sign'])
    field_value = float(PARAMS['value'])

    result = DB.weather_history.find(
        {'date': {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']},
         field: {field_sign: field_value}},
        {'_id': 0, 'date': 1, 'daily_max': 1, 'daily_min': 1, 'daily_medium': 1, 'precipitation': 1, 'sunshine': 1})
    if result:
        resp = [doc for doc in result]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/min_max_differences', methods=['GET'])
@token_auth.login_required
@check_parameters(['start_date', 'end_date', 'type'])
def min_max_differences():
    PARAMS = request.args.to_dict()

    if PARAMS['type'] == 'high_diffs':
        match = {"$gte": 20}
    else:
        match = {"$lte": 2}

    # {"$sort": {"diff": -1 }},
    cursor = DB.weather_history.aggregate([
        {'$match': {'date': {"$gte": PARAMS['start_date'], "$lte": PARAMS['end_date']}}},
        {'$project': {'_id': 0, 'date': 1, 'daily_max': 1, 'daily_medium': 1, 'daily_min': 1,
                      'diff': {'$subtract': ["$daily_max", "$daily_min"]}}},
        {"$match": {"diff": match}}
    ])

    if cursor:
        resp = [doc for doc in cursor]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405


@climate_change.route('/temperature_variation', methods=['GET'])
@token_auth.login_required
@check_parameters(['year', 'month', 'distribution'])
def temperature_variation():
    PARAMS = request.args.to_dict()

    if PARAMS['distribution'] == 'monthly':
        year = PARAMS['year']
        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'
    else:
        year = PARAMS['year']
        month = PARAMS['month']
        if len(int(month)) == 1:
            month = f'0{month}'
        start_date = f'{year}-{month}-01'
        end_date_day = last_day_of_month(datetime.date(int(year), int(month), 1))
        end_date = f'{end_date_day}'

    columns = {'_id': 0, 'date': 1, 'daily_medium': 1, 'daily_max': 1, 'daily_min': 1}

    if PARAMS['distribution'] == 'daily':
        cursor = DB.weather_history.find(
            {'date': {"$gte": start_date, "$lte": end_date}}, columns)

    else:
        group_by = {
            "year": {"$substr": ["$date", 0, 4]},
            "month": {"$substr": ["$date", 5, 2]}
        }
        cursor = DB.weather_history.aggregate(
            [{"$match": {"date": {"$gte": start_date, "$lte": end_date}}},
             {"$group": {
                 "_id": group_by, "tempAvg": {"$avg": "$daily_medium"},
                 "tempMaxAvg": {"$avg": "$daily_max"}, "tempMinAvg": {"$avg": "$daily_min"}
             }}, {"$project": {'_id': 1, 'tempAvg': 1, 'tempMaxAvg': 1, 'tempMinAvg': 1}},
             {"$sort": {"_id.year": 1, "_id.month": 1}}
             ])

    if cursor:
        resp = [doc for doc in cursor]
        return jsonify(resp)
    else:
        return jsonify({"status": 405, "message": "Query error"}), 405
