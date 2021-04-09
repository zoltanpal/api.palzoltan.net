# common_functions.py
import datetime

def transform_mongodb_response(raw_data, object_ids = ['_id']):
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
    return date.replace(month=date.month+1, day=1) - datetime.timedelta(days=1)