from __future__ import annotations

import io
import types
from typing import Any, TypeVar
from uuid import uuid4

import base64c as base64  # type: ignore
import numpy as np
import orjson  # type: ignore
import torch
from numpy.typing import NDArray
from pydantic import BaseModel, Field, ValidationError, computed_field
from rocksdict import DBCompressionType, Options, Rdict  # type: ignore

from ..utils import get_logger

PREFIX = "/tmp/"

T = TypeVar("T")

logger = get_logger(f"[{__file__}]")


class DocumentObject(BaseModel):
    """
    DocumentObject is a class that represents a document with various methods for serialization, deserialization,
    and database operations. It inherits from BaseModel and includes configurations for handling arbitrary types
    and custom JSON encoders.
    Attributes:
        model_config (dict): Configuration for the model, including arbitrary types allowed and custom JSON encoders.
        object (str): A computed property that returns the lowercase name of the class.
        id (str): A computed property that returns a unique identifier for the document.
    Methods:
        serialize(v: Self, info: FieldInfo) -> bytes:
            Serializes the document object to a compressed JSON byte string.
        deserialize(cls, v: bytes) -> Self:
            Deserializes a compressed JSON byte string to a document object.
        scan(cls, *, store_id: str):
            Scans the database for all documents and yields them one by one.
        get(cls, *, store_id: str, id: str):
            Retrieves a document from the database by its ID.
        find(cls, *, store_id: str, limit: int = 25, offset: int = 0, **kwargs: Any):
            Finds documents in the database that match the given criteria.
        delete(cls, *, store_id: str, id: str):
            Deletes a document from the database by its ID.
        destroy(cls, *, store_id: str):
            Destroys the entire database for the given vector store ID.
        flush(cls, *, store_id: str):
            Flushes the database for the given vector store ID.
        create_database(cls, *, store_id: str):
            Creates a new database for the given vector store ID.
        db(cls, *, store_id: str):
            Returns a database instance for the given vector store ID.
        put(self, *, store_id: str):
            Stores the document object in the database.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {
            np.ndarray: lambda v: v.tolist(),
            NDArray: lambda v: v.tolist(),
            io.BytesIO: lambda v: base64.b64encode(v.getvalue()).decode(),
            torch.Tensor: lambda v: v.tolist(),
            bytes: lambda v: base64.b64encode(v).decode(),
        },
        "extra": "allow",
    }

    @computed_field(return_type=str)
    @property
    def object(self):
        return self.__class__.__name__.lower()

    @classmethod
    def scan(cls, *, store_id: str, limit: int = 25, offset: int = 0):
        riter = cls.db(store_id=store_id).iter()
        riter.seek_to_first()
        while riter.valid():
            try:
                riter.next()
                while offset > 0:
                    riter.next()
                    offset -= 1
                if limit > 0:
                    data = orjson.dumps(
                        riter.value(), option=orjson.OPT_SERIALIZE_NUMPY
                    )
                    yield cls.model_validate_json(data)
                    limit -= 1
            except StopIteration:
                break
            except Exception as e:
                logger.error("Error scanning DocumentChunk. %s", e)
                continue

    @classmethod
    @types.coroutine
    def retrieve(cls, *, store_id: str, id: str):
        try:
            data = cls.db(store_id=store_id)[id]
            yield
            return cls.model_validate(data)
        except KeyError as e:
            raise ValueError("DocumentChunk with id %s not found.", e)
        except Exception as e:
            logger.error("Error getting DocumentChunk. %s", e)
            raise e

    @classmethod
    def find(cls, *, store_id: str, limit: int = 25, offset: int = 0, **kwargs: Any):
        riter = cls.db(store_id=store_id).iter()
        riter.seek_to_first()
        while offset > 0:
            riter.next()
            offset -= 1
        while riter.valid() and limit > 0:
            try:
                if all(riter.value().get(k) == v for k, v in kwargs.items()):
                    data = orjson.dumps(
                        riter.value(), option=orjson.OPT_SERIALIZE_NUMPY
                    )
                    yield cls.model_validate_json(data)
                    limit -= 1
                riter.next()
            except ValidationError as e:
                logger.error("Error finding DocumentChunk. %s", e)
                continue
            except StopIteration:
                break
            except Exception as e:
                logger.error("Error finding DocumentChunk. %s", e)
                break

    @classmethod
    @types.coroutine
    def delete(cls, *, store_id: str, id: str):
        try:
            del cls.db(store_id=store_id)[id]
            yield
        except KeyError as e:
            raise ValueError("DocumentChunk with id %s not found.", e)
        except Exception as e:
            logger.error("Error deleting DocumentChunk. %s", e)
            raise e

    @classmethod
    @types.coroutine
    def destroy(cls, *, store_id: str):
        try:
            cls.db(store_id=store_id).destroy(PREFIX + store_id)
            yield
        except Exception as e:
            logger.error("Error destroying DocumentChunk. %s", e)
            raise e

    @classmethod
    @types.coroutine
    def create_store(cls, *, store_id: str):
        try:
            cls.db(store_id=store_id)
            yield
        except Exception as e:
            logger.error("Error creating DocumentChunk database. %s", e)
            raise e

    @classmethod
    def db(cls, *, store_id: str):
        options = Options()
        options.create_if_missing(True)
        options.set_error_if_exists(False)
        options.set_compression_type(DBCompressionType.zstd())
        return Rdict(PREFIX + store_id, options)

    @types.coroutine
    def put(self, *, store_id: str):
        try:
            self.db(store_id=store_id)[self.id] = self.model_dump()
            yield
        except Exception as e:
            logger.error("Error setting DocumentChunk. %s", e)
            raise e
        return self
