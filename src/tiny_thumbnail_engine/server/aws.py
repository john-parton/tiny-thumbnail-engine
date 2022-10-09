"""Default handler to deploy tiny-thumbnail-engine on AWS Lambda."""

import base64
import os
import secrets
import typing

from tiny_thumbnail_engine import App
from tiny_thumbnail_engine.signing import BadSignatureError


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


# TODO Consider a class-based approach
def lambda_handler(
    event: typing.Dict[typing.Any, typing.Any], context
) -> typing.Dict[typing.Any, typing.Any]:
    """Called by lambda to run application."""
    # TODO Consider factoring out into its own method
    if CLOUDFRONT_VERIFY:
        try:
            verification_header = event.get("multiValueHeaders", {}).get(
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
        thumbnail = app.from_path(path)
    # A garbage URL was passed
    except app.UrlError:
        return {
            "statusCode": 403,
            "body": "403 Forbidden",
            "isBase64Encoded": False,
            "headers": {
                "Content-Type": "text/plain",
            },
        }

    query_params = event.get("multiValueQueryStringParameters", {})

    # TODO Make sure thumbnail doesn't exceed max size
    try:
        data = thumbnail.get_or_generate(query_params=query_params)

    # TODO More helpful error messages
    except (BadSignatureError, IndexError, ValueError):
        return {
            "statusCode": 403,
            "body": "403 Forbidden",
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
