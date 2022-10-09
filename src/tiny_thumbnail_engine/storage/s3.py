# Persistence layer
# This module should be lazily imported to avoid import errors
# when using only the client-side functionality

import io
import typing
from pathlib import Path

import attr
import boto3
from botocore.exceptions import ClientError

from tiny_thumbnail_engine.environ import EnvironFactory


ENVIRON_PREFIX = "TINY_THUMBNAIL_ENGINE"


@attr.s
class S3Backend:
    source_bucket: str = attr.field(
        factory=EnvironFactory("SOURCE_BUCKET", "tiny_thumbnail_engine.s3.S3Backend")
    )
    target_bucket: str = attr.field(
        factory=EnvironFactory("TARGET_BUCKET", "tiny_thumbnail_engine.s3.S3Backend")
    )

    # boto3 s3 client
    client = attr.field(init=False)

    def __attrs_post_init__(self) -> None:
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
            f, self.target_bucket, key, ExtraArgs={"ContentType": content_type}
        )


# Currently not supported, but an example for how a file backend might work
# @attr.s
# class FileBackend:
#     # Would be nice to conver these to
#     source_folder: Path = attr.field(factory=EnvironFactory("SOURCE_FOLDER"), converter=Path)
#     target_folder: Path = attr.field(factory=EnvironFactory("TARGET_FOLDER"), converter=Path)

#     def _read(self, path: Path) -> bytes:
#         with path.open("rb") as f:
#             return f.read()

#     def _target_exists(self, path: Path) -> bool:
#         return (self.target_folder / path).exists()

#     def _read_source(self, path: Path) -> bytes:
#         return self._read(self.source_folder / path)

#     # You should use sendfile here
#     def _read_target(self, path: Path) -> bytes:
#         return self._read(self.target_folder / path)

#     def _write_target(self, path: Path, contents: bytes, content_type: str):
#         output = self.target_folder / path

#         output.parent.mkdir(exist_ok=True, parents=True)

#         with output.open("wb") as f:
#             f.write(contents)
