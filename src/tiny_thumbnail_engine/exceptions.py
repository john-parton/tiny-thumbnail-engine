class ImproperlyConfiguredError(Exception):
    """tiny-thumbnail-engine is somehow improperly configured"""


# Wrap "not enough values to unpack"
class UrlError(ValueError):
    pass
