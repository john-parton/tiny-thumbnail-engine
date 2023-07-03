# Persistence layer
# This module should be lazily imported to avoid import errors
# when using only the client-side functionality

import dataclasses
import io
import typing
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from tiny_thumbnail_engine.environ import EnvironFactory


ENVIRON_PREFIX = "TINY_THUMBNAIL_ENGINE"

DEFAULT_TIME_TO_LIVE: typing.Final[int] = (
    60 * 60 * 24 * 180
)  # 180 days, kind of bonkers. That's what Google says


@dataclasses.dataclass
class S3Backend:
    source_bucket: str = dataclasses.field(
        factory=EnvironFactory("SOURCE_BUCKET", "tiny_thumbnail_engine.s3.S3Backend")
    )
    target_bucket: str = dataclasses.field(
        factory=EnvironFactory("TARGET_BUCKET", "tiny_thumbnail_engine.s3.S3Backend")
    )

    # boto3 s3 client
    client = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.client = boto3.client("s3")

    def _read_source(self, path: Path) -> bytes:
        key = path.as_posix()
        data = self.client.get_object(Bucket=self.source_bucket, Key=key)

        # Not sure why boto3-stubs is suggesting this is typing.Any
        body: bytes = data["Body"].read()

        return body

    # Function can fail
    # Probably should raise a wrapped file not found exceptions instead
    def _read_target(self, path: Path) -> typing.Optional[bytes]:
        key = path.as_posix()

        try:
            data = self.client.get_object(Bucket=self.source_bucket, Key=key)
        # Catches more exceptions than "NoSuchKey"
        # Probably fine failure mode
        except ClientError:
            return None

        # Not sure why boto3-stubs is suggesting this is typing.Any
        body: bytes = data["Body"].read()

        return body

    def _write_target(self, path: Path, contents: bytes, content_type: str) -> None:
        key = path.as_posix()
        f = io.BytesIO(contents)
        self.client.upload_fileobj(
            f,
            self.target_bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "CacheControl": f"public, max-age={DEFAULT_TIME_TO_LIVE}",
            },
        )
