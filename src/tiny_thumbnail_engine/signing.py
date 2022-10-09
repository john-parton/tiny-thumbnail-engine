# This is inspired by Django's signing methods
# It attempts to use very basic cryptography primitives with sane defaults
# The purpose of this module is to add a cryptographic signature
# to the thumbnail URL so that a malicious entity cannot tie up
# arbitrary amounts of resources by manipulating thumbnail URLs
# For instance, someone could step through every combination of width and height
# from 1x1 to 1000x1000 and generate a million different images
# This will increase storage requirements on S3, and possibly generate issues
# with our CDN
# Furthermore, jpegs are optimized with mozjpeg, which is very CPU intensive,
# an attack like that could cost a large amount of money in lambda charges

# Some other approaches which were considered before settling on this

# 1. Have a pre-defined whitelist of thumbnail sizes

# This would probably be OK if the thumbnail sizes were stored in an environmental
# variable,
# but we have a CMS in front of this were content authors can specify exact dimensions
# of thumbnails
# It can be tricky to anticipate the exact requirements here
# It is my experience that if a content author cannot generate the correct sized image,
# they will just
# put the absolute largest image in the template so it "looks right"

# 2. Other prototypes involving two way authentication or a seperate memcache layer
# (or redis layer)

# Avoid putting cryptographic signatures in URLs by first consulting some cache table
# if the thumbnail has
# been generated yet, and then eliding the crytographic signture if it exists.

# This created a reliance on a separate caching layer and overall increased latency
# in our app

# 3. Just use sorl thumbnail engine

# We did use that for a time, but it didn't integrate well with mozjpeg and often had
# performance hiccups

# These functions are internal to tiny-thumbnail-engine and aren't meant to be exposed
# as part of the public API


import base64
import hmac
import secrets
import time
import typing


# These are not configurable
# DIGEST_MOD should probably never be changed.
# Honestly sha224 is overkill for this use-case. We could easily get away with sha1
DIGEST_MOD: typing.Final[str] = "sha224"

# TODO Make this configurable via an environmental variable
# It's not critical that this be any particular variable,
# we could probably have even implemented this entire system
# without a max age feature at all
MAX_AGE: typing.Final[int] = 30 * 24 * 60 * 60


class SignatureDict(typing.TypedDict):
    salt: str
    signature: str
    timestamp: int


class BadSignatureError(Exception):
    """Signature does not match."""


class SignatureExpiredError(BadSignatureError):
    # If you use an f-string here, flake8 will produce an error
    """Signature timestamp is too old."""


def salted_hmac(secret_key: bytes, salt: bytes, value: bytes) -> bytes:

    # We want to make sure that the key for HMAC has more than
    # 224 bytes of entropy
    # It's recommended to generate the secrets key using
    # secrets.token_urlsafe(224)
    # for the secret key
    # TODO probably just move this check to the App
    if len(secret_key) <= 224:
        raise ValueError("secret_key does not have enough entropy")

    return hmac.digest(key=salt + secret_key, msg=value, digest=DIGEST_MOD)


def sign(*, secret_key: str, value: str, timestamp: int, salt: str) -> str:
    """Create a base64 encoded cryptographic signature of 'value'"""
    value_with_timestamp = f"{value}:{timestamp}"

    signature = salted_hmac(
        secret_key.encode(), salt.encode(), value_with_timestamp.encode()
    )

    return base64.urlsafe_b64encode(signature).decode().rstrip("=")


def generate(*, secret_key: str, value: str) -> SignatureDict:
    """Shortcut utility to create a signature with sign. Uses current time as timestamp and randomly generates a salt."""
    timestamp = int(time.time())
    salt = secrets.token_urlsafe()

    signature = sign(secret_key=secret_key, value=value, timestamp=timestamp, salt=salt)

    return {
        "salt": salt,
        "signature": signature,
        "timestamp": timestamp,
    }


def unsign(
    *,
    secret_key: str,
    value: str,
    salt: str,
    signature: str,
    timestamp: typing.Union[str, int],
) -> None:
    if isinstance(timestamp, str):
        timestamp = int(timestamp)

    if (time.time() - timestamp) > MAX_AGE:
        raise SignatureExpiredError

    compare = sign(secret_key=secret_key, value=value, timestamp=timestamp, salt=salt)

    if not secrets.compare_digest(signature, compare):
        raise BadSignatureError
