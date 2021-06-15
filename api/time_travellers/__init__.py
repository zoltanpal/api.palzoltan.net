from marshmallow import Schema, fields

class PersonSchema(Schema):
    """
    Parameters:
     - name (str)
     - short_name (str)
     - actor_name (str)
     - memo (str)
     - time_created (time)
    """

    name = fields.Str(required=True)
    short_name = fields.Str(required=True)
    actor_name = fields.Str(required=True)
    memo = fields.Str()
    created = fields.DateTime()

person_schema = PersonSchema()


class DateSchema(Schema):
    pass

class TripSchema(Schema):
    pass