"""
Script that automatically generates mapped classes and relationships from a database schema
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.automap import (
    automap_base,
    generate_relationship,
    interfaces,
    name_for_collection_relationship,
)

from libs.db.db_client import SQLDBClient


class SQLDBMapping:
    def __init__(self, db_client: SQLDBClient, mapping_tables: list = None):
        self.metadata = MetaData()
        self.sorted_tables: list = []
        self.db_client: SQLDBClient = db_client
        self.mapping_tables: list = mapping_tables
        self.db_classes = None

        self.mapping()

    def mapping(self):
        if self.db_client is None:
            return False

        if self.mapping_tables is not None:
            self.metadata.reflect(self.db_client.engine, only=self.mapping_tables, views=True)
        else:
            self.metadata.reflect(self.db_client.engine, views=True)

        AutoBase = automap_base(metadata=self.metadata)
        AutoBase.prepare(
            name_for_collection_relationship=self._name_for_collection_relationship,
            generate_relationship=self._generate_relationship,
        )

        self.sorted_tables = [table.name for table in self.metadata.sorted_tables]
        self.db_classes = AutoBase.classes

    def __getattr__(self, item: str):
        try:
            self.db_classes[item]
        except KeyError:
            raise KeyError(f"'{item}' table not found or not mapped.")

    def __getitem__(self, item: str):
        try:
            self.db_classes[item]
        except KeyError:
            raise KeyError(f"'{item}' table not found or not mapped.")

    def get(self, item: str):
        try:
            return getattr(self.db_classes, item)
        except AttributeError:
            raise AttributeError(f"'{item}' table not found or mapped.")

    @property
    def mapped_table_names(self):
        if self.db_classes:
            return [x.__table__ for x in list(self.db_classes.db_classes)]
        else:
            return []

    @staticmethod
    def _generate_relationship(
            base, direction, return_fn, attr_name, local_cls, referred_cls, **kw
    ):
        """Generates relationship() and backref() for the automapped tables
        @param base: the AutomapBase class doing the prepare.
        @param direction: the “direction” of the relationship: ONETOMANY, MANYTOONE, MANYTOMANY.
        @param return_fn: the function that is used by default to create the relationship
        @param attr_name: the attribute name to which this relationship is being assigned
        @param local_cls: relationship or backref
        @param referred_cls: the relationship or backref refers to
        @param kw: additional keyword arguments
        @return:
        """

        if direction is interfaces.ONETOMANY:
            kw["cascade"] = "all, delete"
            kw["passive_deletes"] = False

        return generate_relationship(
            base, direction, return_fn, attr_name, local_cls, referred_cls, **kw
        )

    @staticmethod
    def _name_for_collection_relationship(base, local_cls, referred_cls, constraint):
        """Return the attribute name that should be used to refer from one class to another, for a collection reference.
        @param base: The AutomapBase class doing the prepare.
        @param local_cls: the class to be mapped on the local side
        @param referred_cls: the class to be mapped on the referring side
        @param constraint: ForeignKeyConstraint that is being inspected to produce this relationship
        @return:
        """

        if constraint.name:
            return constraint.name.lower()

        return name_for_collection_relationship(
            base, local_cls, referred_cls, constraint
        )
