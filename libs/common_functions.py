# common_functions.py
import datetime
import functools

from flask import jsonify, request


def transform_mongodb_response(raw_data, object_ids=['_id']):
    data = []
    for d in raw_data:
        d.update((k, str(v)) for k, v in d.items() if k in object_ids)
        data.append(d)

    return raw_data


def freeze(d):
    if isinstance(d, dict):
        return frozenset((key, freeze(value)) for key, value in d.items())
    elif isinstance(d, list):
        return tuple(freeze(value) for value in d)
    return d


def validate_date(date_text):
    try:
        datetime.datetime.strptime(date_text, '%Y-%m-%d')
    except ValueError:
        return False


def last_day_of_month(date):
    if date.month == 12:
        return date.replace(day=31)
    return date.replace(month=date.month + 1, day=1) - datetime.timedelta(days=1)


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

                    if expected_arg in ['start_date', 'end_date']:
                        if validate_date(params[expected_arg]) == False:
                            error_msg = f'Incorrect {expected_arg} date format, should be YYYY-MM-DD'
                            return jsonify({"status": "Error", "message": error_msg}), 400

            return func(*args, **kwargs)

        return wrapper_validate_json

    return decorator_validate_json
