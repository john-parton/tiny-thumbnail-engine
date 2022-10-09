import typing
from pathlib import PurePath


class StorageProtocol(typing.Protocol):
    def _read_source(self, path: PurePath) -> bytes:
        ...

    def _read_target(self, path: PurePath) -> typing.Optional[bytes]:
        ...

    def _write_target(self, path: PurePath, contents: bytes, content_type: str) -> None:
        ...
