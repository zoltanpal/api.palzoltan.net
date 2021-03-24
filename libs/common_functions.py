# common_functions.py


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