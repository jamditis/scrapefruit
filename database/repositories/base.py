"""Base repository class with common CRUD operations.

This module provides a generic base repository that handles common
database operations, reducing code duplication across repositories.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Type, Any, Dict
from datetime import datetime

from sqlalchemy.orm import Query

from database.connection import session_scope

# Type variable for model classes
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.

    Provides standard create, read, update, delete operations
    that can be inherited by specific repositories.

    Usage:
        class UserRepository(BaseRepository[User]):
            model_class = User

            def find_by_email(self, email: str) -> Optional[User]:
                return self.find_one_by(email=email)

    Type Parameters:
        T: The SQLAlchemy model class this repository manages
    """

    # Subclasses must define this
    model_class: Type[T]

    # Override this if primary key isn't 'id'
    primary_key: str = "id"

    def get(self, entity_id: Any) -> Optional[T]:
        """
        Get an entity by its primary key.

        Args:
            entity_id: The primary key value

        Returns:
            The entity or None if not found
        """
        with session_scope() as session:
            entity = session.query(self.model_class).filter(
                getattr(self.model_class, self.primary_key) == entity_id
            ).first()
            if entity:
                session.expunge(entity)
            return entity

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = True,
    ) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Column name to order by (default: primary key)
            descending: Sort descending if True

        Returns:
            List of entities
        """
        with session_scope() as session:
            query = session.query(self.model_class)

            # Apply ordering
            order_column = getattr(
                self.model_class,
                order_by or self.primary_key
            )
            if descending:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column)

            # Apply pagination
            entities = query.offset(offset).limit(limit).all()
            for entity in entities:
                session.expunge(entity)
            return entities

    def find_one_by(self, **filters) -> Optional[T]:
        """
        Find a single entity matching the given filters.

        Args:
            **filters: Column-value pairs to filter by

        Returns:
            The first matching entity or None
        """
        with session_scope() as session:
            query = session.query(self.model_class)
            for column, value in filters.items():
                query = query.filter(getattr(self.model_class, column) == value)
            entity = query.first()
            if entity:
                session.expunge(entity)
            return entity

    def find_all_by(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        descending: bool = True,
        **filters,
    ) -> List[T]:
        """
        Find all entities matching the given filters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Column name to order by
            descending: Sort descending if True
            **filters: Column-value pairs to filter by

        Returns:
            List of matching entities
        """
        with session_scope() as session:
            query = session.query(self.model_class)

            # Apply filters
            for column, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model_class, column) == value)

            # Apply ordering
            if order_by:
                order_column = getattr(self.model_class, order_by)
                if descending:
                    query = query.order_by(order_column.desc())
                else:
                    query = query.order_by(order_column)

            # Apply pagination
            entities = query.offset(offset).limit(limit).all()
            for entity in entities:
                session.expunge(entity)
            return entities

    def count(self, **filters) -> int:
        """
        Count entities matching the given filters.

        Args:
            **filters: Column-value pairs to filter by

        Returns:
            Number of matching entities
        """
        with session_scope() as session:
            query = session.query(self.model_class)
            for column, value in filters.items():
                if value is not None:
                    query = query.filter(getattr(self.model_class, column) == value)
            return query.count()

    def exists(self, entity_id: Any) -> bool:
        """
        Check if an entity exists.

        Args:
            entity_id: The primary key value

        Returns:
            True if entity exists
        """
        return self.get(entity_id) is not None

    def create(self, **kwargs) -> T:
        """
        Create a new entity.

        Args:
            **kwargs: Column-value pairs for the new entity

        Returns:
            The created entity
        """
        with session_scope() as session:
            entity = self.model_class(**kwargs)
            session.add(entity)
            session.flush()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def update(self, entity_id: Any, **kwargs) -> Optional[T]:
        """
        Update an entity by its primary key.

        Args:
            entity_id: The primary key value
            **kwargs: Column-value pairs to update

        Returns:
            The updated entity or None if not found
        """
        with session_scope() as session:
            entity = session.query(self.model_class).filter(
                getattr(self.model_class, self.primary_key) == entity_id
            ).first()
            if not entity:
                return None

            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            session.flush()
            session.refresh(entity)
            session.expunge(entity)
            return entity

    def delete(self, entity_id: Any) -> bool:
        """
        Delete an entity by its primary key.

        Args:
            entity_id: The primary key value

        Returns:
            True if entity was deleted, False if not found
        """
        with session_scope() as session:
            entity = session.query(self.model_class).filter(
                getattr(self.model_class, self.primary_key) == entity_id
            ).first()
            if entity:
                session.delete(entity)
                return True
            return False

    def bulk_create(self, entities_data: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple entities in a single transaction.

        Args:
            entities_data: List of dictionaries with entity data

        Returns:
            List of created entities
        """
        with session_scope() as session:
            entities = [self.model_class(**data) for data in entities_data]
            session.add_all(entities)
            session.flush()
            for entity in entities:
                session.refresh(entity)
                session.expunge(entity)
            return entities

    def bulk_delete(self, entity_ids: List[Any]) -> int:
        """
        Delete multiple entities by their primary keys.

        Args:
            entity_ids: List of primary key values

        Returns:
            Number of entities deleted
        """
        with session_scope() as session:
            pk_column = getattr(self.model_class, self.primary_key)
            deleted = session.query(self.model_class).filter(
                pk_column.in_(entity_ids)
            ).delete(synchronize_session=False)
            return deleted
