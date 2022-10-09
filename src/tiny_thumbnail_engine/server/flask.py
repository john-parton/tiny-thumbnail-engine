# This is very broken and only meant as a loose example
# Only deploying onto Lambda is supported at the moment

# import base64
# from flask import Flask, abort, send_file

# from tiny_thumbnail_engine import App
# from tiny_thumbnail_engine.app import FileBackend

# thumbnail_engine = App(
#     storage_backend=FileBackend()
# )

# app = Flask(__name__)


# @app.route('/<path:path>')
# def get_dir(path):
#     # Verify first
#     # We don't want to do I/O if we can avoid it
#     try:
#         thumbnail = thumbnail_engine.from_path(
#             path
#         )
#     except (thumbnail_engine.UrlError, thumbnail_engine.SignatureError):
#         return abort(403)

#     thumbnail_path, __ = thumbnail.get_or_generate()

#     filesystem_path = thumbnail.app.storage_backend.target_folder / thumbnail_path

#     return send_file(filesystem_path)