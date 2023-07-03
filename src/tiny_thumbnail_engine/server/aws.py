"""Default handler to deploy tiny-thumbnail-engine on AWS Lambda."""

import base64
import os
import secrets
import typing

from tiny_thumbnail_engine import App
from tiny_thumbnail_engine.signing import BadSignatureError
from tiny_thumbnail_engine.exceptions import UrlError


app = App()

DEFAULT_TIME_TO_LIVE: typing.Final[int] = (
    60 * 60 * 24 * 180
)  # 180 days, kind of bonkers. That's what Google says


# This is to make sure access it only through our cloudfront cdn
try:
    CLOUDFRONT_VERIFY: typing.Final[str] = os.environ["CLOUDFRONT_VERIFY"]
except KeyError as e:
    raise ValueError(
        "Set CLOUDFRONT_VERIFY in environment. "
        "Set to blank to disable verification check."
    ) from e


class LambdaHttpRequest(typing.TypedDict, total=False):
    httpMethod: str
    path: str
    multiValueQueryStringParameters: dict[str, list[str]]
    multiValueHeaders: dict[str, list[str]]
    body: str
    isBase64Encoded: bool


# I think this could be a set and we could just do set
# arithmetic
_HTTP_REQUEST_KEYS: typing.Final[list[str]] = [
    "httpMethod",
    "path",
    "multiValueQueryStringParameters",
    "multiValueHeaders",
    "body",
    "isBase64Encoded",
]


def _http_request_handler(event: LambdaHttpRequest, context):
    if event.get("httpMethod", "") != "GET":
        return {
            "statusCode": 405,
            "body": "405 Method Not Allowed",
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "text/plain",
            },
        }

    """Called by lambda to run application."""
    # TODO Consider factoring out into its own method
    if CLOUDFRONT_VERIFY:
        try:
            verification_header: str = event.get("multiValueHeaders", {}).get(
                "x-cloudfront-verify", []
            )[0]
        except IndexError:
            verification_header = ""

        if not secrets.compare_digest(CLOUDFRONT_VERIFY, verification_header):
            return {
                "statusCode": 403,
                "body": (
                    "403 Forbidden: "
                    "Only access this service using the canonical domain names."
                ),
                "isBase64Encoded": False,
                "headers": {
                    "Content-Type": "text/plain",
                },
            }

    # Must slice leading /
    path = event["path"][1:]

    # Verify that it's not a malformed request
    try:
        thumbnail = app.get_thumbnail(path)
    # A garbage URL was passed
    except UrlError:
        return {
            "statusCode": 403,
            "body": "403 Forbidden: Malformed URL.",
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "text/plain",
            },
        }

    try:
        signature = event.get("multiValueQueryStringParameters", {}).get(
            "signature", []
        )[0]
    except IndexError:
        return {
            "statusCode": 403,
            "body": "403 Forbidden: Signature is required.",
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "text/plain",
            },
        }

    # TODO Make sure thumbnail doesn't exceed max size
    try:
        data = thumbnail.get_or_generate(signature=signature)

    # TODO More helpful error messages
    except BadSignatureError:
        return {
            "statusCode": 403,
            "body": "403 Forbidden: Invalid signature.",
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "text/plain",
            },
        }

    return {
        "statusCode": 200,
        "body": base64.b64encode(data),
        "isBase64Encoded": True,
        "headers": {
            "Cache-Control": f"public, max-age={DEFAULT_TIME_TO_LIVE}",
            "Content-Type": thumbnail.content_type,
        },
    }


# TODO Consider a class-based approach
def lambda_handler(
    event: dict[typing.Any, typing.Any], context
) -> dict[typing.Any, typing.Any]:
    """Called by lambda to run application."""

    # I believe this could be done with a set operation
    if all(key in event for key in _HTTP_REQUEST_KEYS):
        return _http_request_handler(event, context)
