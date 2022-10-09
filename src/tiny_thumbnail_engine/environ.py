# Helper for reading from environment
# 'KeyError' on os.environ tends to be very unhelpful
# Raise a more helpful error message
# There's probably some dedicated python package just for doing this

import os
import typing

from tiny_thumbnail_engine.exceptions import ImproperlyConfiguredError


ENVIRON_PREFIX: typing.Final[str] = "TINY_THUMBNAIL_ENGINE"


def EnvironFactory(key: str, class_name: str) -> typing.Callable[[], str]:
    def inner() -> str:
        # Should wrap key error and re-raise with more helpful message
        # Some keys are required on the server and some are required on the client
        try:
            value = os.environ[f"{ENVIRON_PREFIX}_{key}"]
        except KeyError as e:
            raise ImproperlyConfiguredError(
                f"{class_name} requires the environmental variable "
                f"{ENVIRON_PREFIX}_{key} to function."
            ) from e

        if not value:
            raise ImproperlyConfiguredError(
                f"{class_name} requires the environmental variable "
                f"{ENVIRON_PREFIX}_{key} to function."
            )

        return value

    return inner
