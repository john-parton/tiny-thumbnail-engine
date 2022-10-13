"""Classes and utilities for generating the thumbnail.

Reposible for taking in-memory copy of the image and producing
an in-memory thumbnail.

Not responsible for fetching/upload data to filesystem(s) or s3
Not responsible directly for generating or validating signatures or auth tokens
"""

import re
import typing
from functools import cached_property
from pathlib import PurePosixPath

import attr


try:
    import pyvips
except ImportError:
    pyvips = None

# Avoid circular dependency unless type checkgin
if typing.TYPE_CHECKING:
    from .app import App


# TODO Move to exceptions
class ServerMissingDependancyError(RuntimeError):
    """Missing dependancy for server-side functionality. Did you install tiny-thumbnail-engine[server]"""


def _convert_int(value: typing.Any) -> typing.Optional[int]:
    if value in {"", None}:
        return None
    return int(value)


def _clamped_int(value: int) -> int:
    return max(int(round(value)), 1)


@attr.s
class ThumbnailSpec:
    """A string representation of the desired thumbnail operations including

    desired width
    desired height
    whether or not to pad the final image
    whether or not to upscale
    whether or not to crop the final image

    Examples

    200x300 - Resize image so that it is contained within a 200 by 300 pixel rectangle.
      If the image
      already fits within that box, no scaling is performed

    200x300c - Scale image down such that it covers a 200 by 300 pixel rectangle.
      If the image
      already fits within that box, no scaling is performed

    200x300u - Resize image so that it is contained within a 200 by 300 pixel rectangle.
      If the image
      is smaller than that box, upscale the image (creating a blurry image)
      It's generally preferred that you should save this image using CSS or HTML, but
      we have some
      legacy code that still expects this function

    200x300p - Scale image so that it is contained within a 200 by 300 pixel rectangle.
      Fill the rest
      of the rectangle with white.
      (TODO this should probably be alpha for transparent images)

    200 - Scale image so that the width is at most 200 pixels. Height is unconstrained

    x300 - Scale image so that the height is at most 300 pixels. Width is unconstrained
    """

    # I'm not sure if some combinations of padding/upscale/crop are nonsense?
    # Probably some duplication in here
    SPEC_PATTERN = re.compile(
        r"""
        ^
            (?P<width>\d*)
            (?:x(?P<height>\d+))?
            (?P<padding>p?)
            (?P<upscale>u?)
            (?P<crop>c?)
        $
    """,
        flags=re.VERBOSE,
    )

    # Despite these attributes being called "width" and "height", they are more
    # accurately referred to as "desired width" and "desired height"
    # The final width and height of the image will likely not be the same due to
    # padding, upscale, crop, etc.
    # TODO Validate width > 0 and height > 0
    width: typing.Optional[int] = attr.field(converter=_convert_int)
    height: typing.Optional[int] = attr.field(converter=_convert_int)

    padding: bool = attr.field(kw_only=True, default=False, converter=bool)
    upscale: bool = attr.field(kw_only=True, default=False, converter=bool)
    crop: bool = attr.field(kw_only=True, default=False, converter=bool)

    @classmethod
    def from_string(cls, spec: str) -> "ThumbnailSpec":
        match = cls.SPEC_PATTERN.search(spec)

        if match is None:
            raise ValueError(f"Invalid spec: {spec!r}")

        return cls(**match.groupdict())

    def to_string(self) -> str:
        spec = ""

        # String concat, string builder might be faster: "".join(parts)
        # Honestly isn't going to matter
        if self.width:
            spec += f"{self.width}"

        if self.height:
            spec += f"x{self.height}"

        # Padding is meaningless without a provided height or width
        if (self.width or self.height) and self.padding:
            spec += "p"

        # Upscaling is meaningless without a provided height or width
        if (self.width or self.height) and self.upscale:
            spec += "u"

        # If you don't provide a height and width, it will never crop
        if self.width and self.height and self.crop:
            spec += "c"

        # It's not recommended to try and create a thumbnail without specifying
        # at least width and height
        # TODO Subclass this error?
        if not spec:
            raise ValueError("Not actually transforming thumbnail")

        return spec


@attr.s
class Thumbnail:

    path: str = attr.field()
    spec: ThumbnailSpec = attr.field()
    format: str = attr.field(kw_only=True)  # TODO make this an enum

    # Reference to the app so that we can
    # retrieve fiels and persist the final image
    # Missing type annotation
    app: "App" = attr.field(kw_only=True)

    @format.validator
    def check_format(self, attribute, value: typing.Any) -> None:
        if value not in {".webp", ".jpg"}:
            raise ValueError

    def _get_thumbnail_path(self) -> PurePosixPath:
        """Relative path to the final thumbnail"""

        path = PurePosixPath(self.path)

        return path / self.spec.to_string() / path.with_suffix(self.format).name

    # Should this just be __str__ ?
    @cached_property
    def url(self) -> str:

        thumbnail_path = self._get_thumbnail_path()

        signature = self.app._sign(value=str(thumbnail_path))

        # Used urlencode before, but we know signature is already urlsafe
        return f"{thumbnail_path}?signature={signature}"

    def get_or_generate(self, *, signature: str) -> bytes:
        thumbnail_path = self._get_thumbnail_path()

        data = self.app.storage_backend._read_target(thumbnail_path)

        if data is not None:
            return data

        # raises if invalid
        self.app._unsign(
            value=str(thumbnail_path),
            signature=signature,
        )

        return self._generate(thumbnail_path)

    @property
    def content_type(self) -> str:
        # Could use dict lookup
        # Could use mimetype standard library
        # TODO improve this when switching to enum
        if self.format == ".jpg":
            return "image/jpeg"

        if self.format == ".webp":
            return "image/webp"

        raise ValueError(f"Unknown content_type: {self.format!r}")

    def _generate(self, target_path: PurePosixPath) -> bytes:
        if pyvips is None:
            raise ServerMissingDependancyError

        spec = self.spec

        # Can create an error
        # Read data using storage backend
        buffer: bytes = self.app.storage_backend._read_source(PurePosixPath(self.path))

        # "" means no options
        # Not sure what options are available
        image = pyvips.Image.new_from_buffer(buffer, "")

        # We need to do this because we need to calculate image aspect
        # ratio in the next step
        image = image.autorot()

        if spec.width is None:
            width = _clamped_int(spec.height * (image.width / image.height))
        else:
            width = spec.width

        thumbnail_kwargs = {
            "size": pyvips.enums.Size.BOTH if spec.upscale else pyvips.enums.Size.DOWN,
            # There are ENTROPY and ATTENTION
            # options which are probably useful here
            # I tested ENTROPY and it actually worked pretty well as a sane default
            "crop": pyvips.enums.Interesting.ENTROPY
            if spec.crop
            else pyvips.enums.Interesting.NONE,
        }

        if spec.height is not None:
            thumbnail_kwargs["height"] = spec.height

        image = image.thumbnail_image(width, **thumbnail_kwargs)

        # TODO Add more explict handling for RGBA

        if spec.padding:
            image = image.gravity(
                pyvips.enums.CompassDirection.CENTRE,
                max(width, image.width),
                max(spec.height or image.height, image.height),
                background=[255, 255, 255],
            )

        write_kwargs = {
            "Q": 80,
            "strip": True,
        }

        # TODO Use enum
        if self.format == ".jpg":
            write_kwargs.update(
                {
                    "trellis_quant": True,
                    "overshoot_deringing": True,
                    "optimize_scans": True,
                    "quant_table": 3,
                    "optimize_coding": True,
                    "interlace": True,  # is this correct?
                    # "chroma_subscampling": "4:2:0",
                    "background": [255, 255, 255],
                }
            )
        elif self.format == ".webp":
            write_kwargs.update(
                {
                    "min_size": True,
                    "effort": 6,
                }
            )
        else:
            raise ValueError(f"Unhandled format format: {self.format!r}")

        finished_image: bytes = image.write_to_buffer(self.format, **write_kwargs)

        # Persist to bucket
        self.app.storage_backend._write_target(
            target_path, finished_image, content_type=self.content_type
        )

        return finished_image
