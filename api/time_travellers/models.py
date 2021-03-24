from api.db import mongodb_client as db


class Person(db.Document):
    """
    Person collection schema
    """
    __tablename__ = "persons"

    name = db.StringField(required=True, unique=True)
    other_name = db.StringField(required=False, unique=True)
    present = db.StringField(required=False, unique=True)
