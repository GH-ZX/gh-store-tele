"""Compress the large public catalog without buffering event streams."""
from starlette.middleware.gzip import GZipMiddleware


class CatalogCompressionMiddleware:
    def __init__(self, app):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=1024, compresslevel=4)

    async def __call__(self, scope, receive, send):
        handler = self.compressed if scope["type"] == "http" and scope["path"] == "/api/catalog" else self.app
        await handler(scope, receive, send)
