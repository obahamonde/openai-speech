import typing as tp
import typing_extensions as tpe
import functools as ft
from uuid import uuid4
from fastapi import HTTPException, status
from botocore.exceptions import (
	ClientError,
	ParamValidationError,
	ValidationError,
	NoCredentialsError,
	PartialCredentialsError,
)
import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from pydantic import BaseModel, Field
from .proto import RepositoryProtocol
from .utils import asyncify, get_logger

logger = get_logger(__name__)
T = tp.TypeVar("T")
T_co = tp.TypeVar("T_co", bound=BaseModel)
P = tpe.ParamSpec("P")
DynamoTypeEnum = tp.Literal["S", "N", "B", "SS", "NS", "BS", "BOOL", "NULL", "L", "M"]


def handle_exception(
	func: tp.Callable[P, tp.Awaitable[T]]
) -> tp.Callable[P, tp.Awaitable[T]]:
	@ft.wraps(func)
	async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
		try:
			return await func(*args, **kwargs)
		except (
			ClientError,
			ParamValidationError,
			ValidationError,
			NoCredentialsError,
			PartialCredentialsError,
		) as e:
			logger.info(
				f"AWS SDK Error: {func.__name__} failed: {e.__class__.__name__}: {e}"
			)
			raise HTTPException(
				status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
				detail=f"{func.__name__} failed: {e.__class__.__name__}: {e}",
			) from e

	return wrapper


class DynaModel(BaseModel):
	
	model_config = {"extra": "allow", "arbitrary_types_allowed": True}

	id: str = Field(default_factory=lambda: str(uuid4()), alias="primary_key")
	@property
	def sort_key(self) -> str:
		return "::".join([field.alias for field in self.model_fields.values() if field.alias])


D = tp.TypeVar("D", bound=DynaModel)
D_co = tp.TypeVar("D_co", bound=DynaModel)


class DynamoRepository(RepositoryProtocol[D, D_co]):
	__entities__: list[tp.Type[D]] = []

	@classmethod
	def __class_getitem__(cls, item: tp.Type[D]) -> tp.Type[D]:
		cls.__entities__.append(item)
		return item

	@classmethod
	def table_name(cls) -> str:
		return f"-".join([entity.__name__ for entity in cls.__entities__])

	@ft.cached_property
	def _serializer(self) -> TypeSerializer:
		return TypeSerializer()

	@ft.cached_property
	def _deserializer(self) -> TypeDeserializer:
		return TypeDeserializer()

	@ft.cached_property
	def client(self):
		return boto3.client("dynamodb", region_name="us-east-1")

	def serialize(self, *, model: D):
		return self._serializer.serialize(model.model_dump()["M"])

	def deserialize(self, *, data: tp.Dict[str, DynamoTypeEnum]) -> D:
		return self._deserializer.deserialize(value={"M": data})

	@handle_exception
	@asyncify
	def create(self, *, params: D) -> D_co:
		item = self.serialize(model=params)
		return cls.deserialize(
			data=self.client.put_item(TableName=cls.table_name, Item=item)["Attributes"]
		)

	@classmethod
	@handle_exception
	@asyncify
	def get(cls, *, id: str) -> T_co:
		return cls.deserialize(
			data=cls.client.get_item(
				TableName=cls.table_name, Key={"primary_key": {"S": id}}
			)["Item"]
		)

	@classmethod
	def list(cls, *, params: D) -> tp.List[T_co]:
		for item in cls.deserialize(data=item)
			for item in cls.client.query(
				TableName=cls.table_name(),
				KeyConditionExpression=f"primary_key = :pk",
				ExpressionAttributeValues={":pk": {"S": params.primary_key}},
			)["Items"]:


	@classmethod
	@handle_exception
	@asyncify
	def update(cls, *, id: str, params: D):
		data = cls.client.update_item(
			TableName=cls.table_name(),
			Key={"primary_key": {"S": id}},
			UpdateExpression="set #attr = :val",
			ExpressionAttributeNames={"#attr": params.primary_key},
			ExpressionAttributeValues={":val": {"S": params.primary_key}},
		)["Attributes"]
		return cls.deserialize(data=data)
	@classmethod
	@asyncify
	@handle_exception
	def delete(cls, *, id: str):
		return cls.client.delete_item(
			TableName=cls.table_name(), Key={"primary_key": {"S": id}}
		)

	@classmethod
	def scan(cls, *, params: D) -> tp.List[T_co]:
		for item in cls.client.scan(
			TableName=cls.table_name,
			ExclusiveStartKey={"primary_key": {"S": params.primary_key}},
			Limit=100,
			ConsistentRead=True,
			ScanFilter={
				"primary_key": {
					"AttributeValueList": [{"S": params.primary_key}],
					"ComparisonOperator": "EQ",
				}
			},
		):
			for i in item["Items"]:
				yield cls.deserialize(data=i)
