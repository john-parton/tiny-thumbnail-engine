"""Main module."""

import os
import typing
from functools import cached_property
from functools import partial
from importlib import import_module
from pathlib import PosixPath

import attr

from tiny_thumbnail_engine import signing
from tiny_thumbnail_engine.environ import ENVIRON_PREFIX
from tiny_thumbnail_engine.environ import EnvironFactory
from tiny_thumbnail_engine.model import Thumbnail
from tiny_thumbnail_engine.model import ThumbnailSpec
from tiny_thumbnail_engine.storage.protocol import StorageProtocol


# Some of these are needed for the client and some for the server
@attr.s
class App:

    # Wrap "not enough values to unpack"
    # TODO Move to exceptions ?
    class UrlError(ValueError):
        pass

    secret_key: str = attr.field(
        factory=EnvironFactory("SECRET_KEY", "tiny_thumbnail_engine.App")
    )

    def __attrs_post_init__(self):
        self._sign = partial(signing.sign, secret_key=self.secret_key)
        self._unsign = partial(signing.unsign, secret_key=self.secret_key)

    @cached_property
    def storage_backend(self) -> StorageProtocol:
        # Default to the S3 backend
        backend_string: str = os.environ.get(
            f"{ENVIRON_PREFIX}_STORAGE_BACKEND",
            "tiny_thumbnail_engine.storage.s3.S3Backend",
        )

        # I think some people prefer a colon for this purpose
        # I've seen it in lambda documentation
        module, __, class_name = backend_string.rpartition(".")

        # TODO wrap these errors
        cls: typing.Callable[[], StorageProtocol] = getattr(
            import_module(module), class_name
        )

        # TODO Consider a run-time check that this class actually
        # implements the storage protocol

        return cls()

    def get_instance(self, path, *args, format="jpg", **kwargs):
        return Thumbnail(
            app=self, path=path, format=format, spec=ThumbnailSpec(*args, **kwargs)
        )

    def from_path(self, path):
        # Example
        # "/path/to/filename.jpg/200x120ucp20/filename.webp"

        if not isinstance(path, PosixPath):
            path = PosixPath(path)

        # Could just use posixpath.split
        try:
            *path_parts, spec, desired_filename = path.parts
        except ValueError as e:
            raise self.UrlError from e

        try:
            spec = ThumbnailSpec.from_string(spec)
        except ValueError as e:
            raise self.UrlError from e

        # Could use splitext here
        # I do like pathlib, but it's kind of hard to read
        file_system_path = PosixPath(*path_parts)
        output_name = PosixPath(desired_filename)

        # This should probably be a method on the thumbnail
        return Thumbnail(
            str(file_system_path),
            app=self,
            format=output_name.suffix,
            spec=spec,
        )
