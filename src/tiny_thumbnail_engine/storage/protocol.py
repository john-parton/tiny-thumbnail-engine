import typing
from pathlib import Path

class StorageProtocol(typing.Protocol):

    def _read_source(self, path: Path) -> bytes:
        ...

    def _read_target(self, path: Path) -> typing.Optional[bytes]:
        ...

    def _write_target(self, path: Path, contents: bytes, content_type: str) -> None:
        ...