# Helper for reading from environment
# 'KeyError' on os.environ tends to be very unhelpful
# Raise a more helpful error message
# There's probably some dedicated python package just for doing this

import os
from tiny_thumbnail_engine.exceptions import ImproperlyConfigured

ENVIRON_PREFIX = "TINY_THUMBNAIL_ENGINE"


def EnvironFactory(key, class_name):
    def inner():
        # Should wrap key error and re-raise with more helpful message
        # Some keys are required on the server and some are required on the client
        try:
            value = os.environ[f"{ENVIRON_PREFIX}_{key}"]
        except KeyError as e:
            raise ImproperlyConfigured(f"{class_name} requires the environmental variable {ENVIRON_PREFIX}_{key} to function.") from e
        
        if not value:
            raise ImproperlyConfigured(f"{class_name} requires the environmental variable {ENVIRON_PREFIX}_{key} to function.")
        
        return value

    return inner

