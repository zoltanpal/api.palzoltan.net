from typing import Any, Dict, Iterable, Optional, Sequence, TypeVar

from sqlalchemy import and_
from sqlalchemy.orm import DeclarativeMeta, Session

from app.utils.reponses import BAD_REQUEST, METHOD_NOT_ALLOWED, NOT_FOUND

T = TypeVar("T", bound=DeclarativeMeta)


class APIFactory:
    """Produces basic DB access methods for API endpoints.
    Returns ORM objects or raises HTTPException via ApiError.
    """

    def __init__(self, model: DeclarativeMeta, db: Session):
        self.model = model
        self.db = db

    def get_all(self, order: Optional[Any] = None):
        q = self.db.query(self.model)
        if order is not None:
            q = q.order_by(order)
        # .all() returns [] if nothing found (never None)
        return q.all()

    def get_by_id(self, id: int):
        # SQLAlchemy legacy: Query.get is deprecated in SA 2.0 style,
        # but keeping your pattern; alternative shown below.
        obj = self.db.query(self.model).get(id)
        if obj is None:
            raise NOT_FOUND.to_http_exception()
        return obj

    def get_by_fields_first(self, filters: Sequence[Any]):
        obj = self.db.query(self.model).filter(and_(*filters)).first()
        if obj is None:
            raise NOT_FOUND.to_http_exception()
        return obj

    def get_by_fields(self, filters: Sequence[Any]):
        # .all() returns list, possibly empty
        return self.db.query(self.model).filter(and_(*filters)).all()

    def require_field(self, data: Dict[str, Any], field: str) -> None:
        """Validate presence of a field, raise 405/400 style error."""
        if field not in data:
            # choose whichever semantics you prefer:
            # - BAD_REQUEST (400) is usually more correct than METHOD_NOT_ALLOWED (405)
            # but keeping your original "405" intent if you want:
            raise METHOD_NOT_ALLOWED.to_http_exception()
            # or:
            # raise BAD_REQUEST.to_http_exception()
