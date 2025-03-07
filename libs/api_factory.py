from http import HTTPStatus
from typing import Dict

from sqlalchemy import and_
from sqlalchemy.orm import DeclarativeMeta, Session
from starlette.responses import JSONResponse

from libs.responses import responses


class APIFactory:
    """The Factory produce API methods (GET, POST, PUT and DELETE endpoint) with basic implementation"""

    def __init__(self, model: DeclarativeMeta, db: Session):
        self.model = model
        self.db = db
        self.error = None

    def get_all(self, order=None):
        if order is not None:
            db_entity = self.db.query(self.model).order_by(order).all()
        else:
            db_entity = self.db.query(self.model).all()
        if db_entity is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        return db_entity

    def get_by_id(self, id: int):
        db_entity = self.db.query(self.model).get(id)
        if db_entity is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        return db_entity

    def get_by_fields_first(self, filter):
        db_entity = self.db.query(self.model).filter(and_(filter)).first()
        if db_entity is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        return db_entity

    def get_by_fields(self, filter):
        db_entity = self.db.query(self.model).filter(and_(filter)).all()
        if db_entity is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        return db_entity


    def check_field(self, data, field):
        if field not in data:
            responses[HTTPStatus.METHOD_NOT_ALLOWED][
                "error_message"
            ] = "Missing '{}' value from the post data.".format(field)
            self.error = JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )
    '''
    def insert(self, data: Dict):
        if len(data) == 0:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["details"] = "Missing input data"
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

        if self.error is not None:
            return self.error

        try:
            insert_obj = self.model(**data)
        except BaseException as err:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["error_message"] = str(err)
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

        ok, resp = db_insert(db=self.db, obj=insert_obj)
        if ok:
            responses[HTTPStatus.CREATED]["last_row_id"] = resp
            return JSONResponse(
                status_code=HTTPStatus.CREATED, content=responses[HTTPStatus.CREATED]
            )
        else:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["error_message"] = str(resp)

            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

    def update(self, id: int, data: Dict):
        if len(data) == 0:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["details"] = "Missing input data"
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

        if self.error is not None:
            return self.error

        db_object = self.db.query(self.model).get(id)
        if db_object is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        # TODO: maybe need a smarter solution to be able to catch the Exceptions
        try:
            self.model(**data)
        except BaseException as err:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["error_message"] = str(err)
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

        for column, value in data.items():
            setattr(db_object, column, value)

        ok, resp = db_update(self.db, db_object)

        if ok:
            return JSONResponse(
                status_code=HTTPStatus.OK, content=responses[HTTPStatus.OK]
            )
        else:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["error_message"] = str(resp)
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )

    def delete(self, id: int):
        delete_obj = self.db.query(self.model).get(id)
        if delete_obj is None:
            return JSONResponse(
                status_code=HTTPStatus.NOT_FOUND,
                content=responses[HTTPStatus.NOT_FOUND],
            )

        ok, resp = db_delete(db=self.db, obj=delete_obj)
        if ok:
            return JSONResponse(
                status_code=HTTPStatus.OK, content=responses[HTTPStatus.OK]
            )
        else:
            responses[HTTPStatus.METHOD_NOT_ALLOWED]["error_message"] = str(resp)
            return JSONResponse(
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                content=responses[HTTPStatus.METHOD_NOT_ALLOWED],
            )
    '''