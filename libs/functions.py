def to_dict(obj):
    """Converts an SQLAlchemy ORM object to a dictionary."""
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
