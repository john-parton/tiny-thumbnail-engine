"""Main module."""

import dataclasses
import os
import typing
from functools import partial
from importlib import import_module

from tiny_thumbnail_engine import signing
from tiny_thumbnail_engine.environ import ENVIRON_PREFIX
from tiny_thumbnail_engine.environ import EnvironFactory
from tiny_thumbnail_engine.model import Thumbnail
from tiny_thumbnail_engine.storage.protocol import StorageProtocol


def get_storage_backend() -> StorageProtocol:
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


# Some of these are needed for the client and some for the server
@dataclasses.dataclass
class App:
    secret_key: str = dataclasses.field(
        factory=EnvironFactory("SECRET_KEY", "tiny_thumbnail_engine.App")
    )

    _: dataclasses.KW_ONLY

    # This could just be a factory?
    storage_backend: StorageProtocol = dataclasses.field(factory=get_storage_backend)

    _sign: typing.Any = dataclasses.field(init=False)
    _unsign: typing.Any = dataclasses.field(init=False)

    def __post_init__(self):
        self._sign = partial(signing.sign, secret_key=self.secret_key)
        self._unsign = partial(signing.unsign, secret_key=self.secret_key)

    def get_thumbnail(self, path: str) -> Thumbnail:
        return Thumbnail.from_path(path, app=self)
