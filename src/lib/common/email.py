from __future__ import annotations
import orjson
import logging
from datetime import datetime
import base64c as base64  # type: ignore
import typing as tp
import dataclasses as dc
import abc as abc
import typing_extensions as tpe
from email.message import EmailMessage
from pydantic import BaseModel
import smtplib
import imaplib
import poplib

from api.lib.proto import RepositoryProtocol
from .storage import Storage, StoredObject
from .pubsub import PubSubChannel

T_contra = tp.TypeVar("T_contra", contravariant=True)
T_co = tp.TypeVar("T_co", covariant=True)


class Config(tp.TypedDict, total=False):
    host: tpe.Required[str]
    port: tpe.Required[int]
    username: tpe.Required[str]
    password: tpe.Required[str]


class EmailAttachment(tpe.TypedDict, total=False):
    filename: tpe.Required[str]
    content: tpe.Required[str]
    mime_type: tpe.Required[str]


class EmailRecipient(tpe.TypedDict, total=False):
    name: tp.Optional[str]
    address: tpe.Required[str]


class Email(tp.TypedDict, total=False):
    id: tpe.Required[str]
    timestamp: tpe.Required[datetime]
    to: tpe.Required[tp.Iterable[EmailRecipient]]
    from_: tpe.Required[EmailRecipient]
    subject: tpe.Required[str]
    body: tpe.Required[str]
    mime_type: tpe.Required[tp.Literal["text/plain", "text/html"]]
    attachments: tpe.NotRequired[tp.Iterable[EmailAttachment]]


class EmailResponse(tpe.TypedDict, total=False):
    status: tpe.Required[str]
    code: tpe.Required[int]
    error: tpe.Optional[str]


class Fs(tpe.Protocol[T_contra]):
    parent: tp.Optional[Fs[T_contra]]
    content: tp.List[Fs[T_contra]]
    type: tp.Literal["file", "folder"]

    def __init__(self, *, parent: tp.Optional[tpe.Self] = None): ...


@dc.dataclass
class Inbox(Fs[Email]):
    parent: tp.Optional[Fs[Email]] = dc.field(default=None)
    content: tp.List[Fs[Email]] = dc.field(default_factory=list)
    type: tp.Literal["file", "folder"] = dc.field(default="folder")


@dc.dataclass
class EmailStack:
    smtp: smtplib.SMTP
    pop3: poplib.POP3
    imap: imaplib.IMAP4


class EmailMetadata(BaseModel):
    id: str
    subject: str
    from_addr: str
    to_addrs: list[str]
    timestamp: datetime
    size: int
    has_attachments: bool


@dc.dataclass
class EmailServer(RepositoryProtocol[Email, EmailMetadata]):
    smtp_config: Config
    pop3_config: Config
    imap_config: Config
    logger: logging.Logger
    storage: Storage = dc.field(default_factory=Storage)
    pubsub: PubSubChannel[EmailMetadata] = dc.field(
        default_factory=lambda: PubSubChannel(
            namespace="email_notifications", data_type=EmailMetadata
        )
    )

    def __post_init__(self):
        self.smtp = smtplib.SMTP(self.smtp_config["host"], self.smtp_config["port"])
        self.smtp.starttls()
        self.smtp.login(
            user=self.smtp_config["username"],
            password=self.smtp_config["password"],
            initial_response_ok=True,
        )
        self.smtp.ehlo()
        self.smtp.set_debuglevel(True)

    async def retrieve(self, *, id: str) -> EmailMetadata:
        body = await self.storage.retrieve(id=f"emails/{id}/email.json")
        email = Email(**orjson.loads(body.body))
        return EmailMetadata(
            id=id,
            subject=email["subject"],
            from_addr=email["from_"]["address"],
            to_addrs=[r["address"] for r in email["to"]],
            timestamp=datetime.now(),
            size=len(body.body),
            has_attachments="attachments" in email,
        )

    async def create(self, *, params: Email) -> EmailMetadata:
        id_ = params["id"]
        stored_obj = StoredObject(
            key=f"emails/{id_}/email.json", body=orjson.dumps(params)
        )
        await self.storage.create(params=stored_obj)
        return EmailMetadata(
            id=id_,
            subject=params["subject"],
            from_addr=params["from_"]["address"],
            to_addrs=[r["address"] for r in params["to"]],
            timestamp=datetime.now(),
            size=len(stored_obj.body),
            has_attachments="attachments" in params,
        )

    async def update(self, *, params: Email) -> EmailMetadata:
        id_ = params["id"]
        stored_obj = StoredObject(
            key=f"emails/{id_}/email.json", body=orjson.dumps(params)
        )
        await self.storage.update(params=stored_obj)
        return EmailMetadata(
            id=id_,
            subject=params["subject"],
            from_addr=params["from_"]["address"],
            to_addrs=[r["address"] for r in params["to"]],
            timestamp=datetime.now(),
            size=len(stored_obj.body),
            has_attachments="attachments" in params,
        )

    async def delete(self, *, id: str) -> None:
        await self.storage.delete(id=f"emails/{id}")

    async def _list(
        self, *, after: str | None = None, limit: int = 100
    ) -> tp.AsyncIterator[EmailMetadata]:
        for obj in self.storage.list(after=f"emails/{after}", limit=limit)
            email = orjson.loads(obj.body)
            yield EmailMetadata(
                id=email["id"],
                subject=email["subject"],
                from_addr=email["from_"]["address"],
                to_addrs=[r["address"] for r in email["to"]],
                timestamp=datetime.now(),
                size=len(obj.body),
                has_attachments="attachments" in email,
            )

    async def list(
        self, *, after: str | None = None, limit: int | None = 100
    ) -> tp.Iterator[EmailMetadata] | tp.AsyncIterator[EmailMetadata]:
        async_iterator = self._list(after=after, limit=limit or 100)
        return tp.cast(tp.Iterator[EmailMetadata], [i async for i in async_iterator])

    async def send_email(self, email: Email) -> EmailResponse:
        try:
            # Store email in S3
            stored_email = await self.create(params=email)
            # Send via SMTP
            msg = EmailMessage()
            msg.set_content(email["body"])
            msg["Subject"] = email["subject"]
            msg["From"] = email["from_"]["address"]
            msg["To"] = ", ".join(r["address"] for r in email["to"])
            response = self.smtp.send_message(msg)
            if isinstance(response, tuple) and 250 in response:
                metadata = EmailMetadata(
                    id=stored_email.id,
                    subject=email["subject"],
                    from_addr=email["from_"]["address"],
                    to_addrs=[r["address"] for r in email["to"]],
                    timestamp=datetime.now(),
                    size=len(email["body"]),
                    has_attachments="attachments" in email,
                )
                await self.pubsub.pub(data=metadata)
            return EmailResponse(status="OK", code=200)

        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return {"status": "ERROR", "code": 500, "error": str(e)}

    async def search_emails(
        self, *, query: str, limit: int = 100
    ) -> tp.AsyncIterator[EmailMetadata]:
        """Search emails in S3"""
        async_iterator = await self.list(after=query, limit=limit)
        return tp.cast(tp.AsyncIterator[EmailMetadata], async_iterator)

    async def subscribe(self) -> tp.AsyncIterator[EmailMetadata]:
        """Subscribe to real-time email notifications"""
        async_iterator = self.pubsub.sub()
        assert isinstance(async_iterator, tp.AsyncIterator)
        async for notification in async_iterator:
            yield notification

    async def archive(self, *, id: str) -> None:
        """Archive email to S3"""
        await self.storage.create(
            params=StoredObject(
                key=f"archive/emails/{id}",
                body=(await self.storage.retrieve(id=f"emails/{id}")).body,
            )
        )
        await self.storage.delete(id=f"emails/{id}")

    async def get_attachments(self, *, email_id: str, filename: str) -> str:
        """Generate presigned URL for attachment download"""
        key = f"attachments/{email_id}/{filename}"
        return await self.storage.get_presigned_url(key=key)

    async def _store_attachments(
        self, email_id: str, attachments: list[EmailAttachment]
    ) -> None:
        """Store email attachments in S3"""
        for attachment in attachments:
            stored_obj = StoredObject(
                key=f"attachments/{email_id}/{attachment['filename']}",
                body=base64.b64decode(attachment["content"]),
            )
            await self.storage.create(params=stored_obj)

    async def _delete_attachments(self, email_id: str) -> None:
        """Delete email attachments from S3"""
        await self.storage.delete(id=f"attachments/{email_id}")

    def _list_attachments(self, email_id: str) -> tp.AsyncIterator[EmailAttachment]:
        """List email attachments from S3"""
        for obj in self.storage.list(after=f"attachments/{email_id}", limit=100):
            yield EmailAttachment(**orjson.loads(obj.body))

    async def _store_attachment(
        self, email_id: str, attachment: EmailAttachment
    ) -> None:
        """Store email attachment in S3"""
        stored_obj = StoredObject(
            key=f"attachments/{email_id}/{attachment['filename']}",
            body=base64.b64decode(attachment["content"]),
        )
        await self.storage.create(params=stored_obj)

    async def _delete_attachment(self, email_id: str, filename: str) -> None:
        """Delete email attachment from S3"""
        await self.storage.delete(id=f"attachments/{email_id}/{filename}")

    async def _list_emails(
        self, *, after: str | None = None, limit: int = 100
    ) -> tp.AsyncIterator[EmailMetadata]:
        """List emails from S3"""
        async_iterator = await self.list(after=after, limit=limit)
        assert isinstance(async_iterator, tp.AsyncIterator)
        async for obj in async_iterator:
            yield obj
