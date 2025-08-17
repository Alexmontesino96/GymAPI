from typing import Callable
from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Adds common security headers to every response.

    Intended for API responses; headers are conservative and safe by default.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = message.setdefault("headers", [])

                def set_header(name: str, value: str):
                    headers.append((name.encode("latin-1"), value.encode("latin-1")))

                # Enforce HTTPS (only meaningful when served over TLS)
                set_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
                # Prevent clickjacking
                set_header("X-Frame-Options", "DENY")
                # Prevent MIME sniffing
                set_header("X-Content-Type-Options", "nosniff")
                # Limit referrer leakage
                set_header("Referrer-Policy", "strict-origin-when-cross-origin")
                # Conservative CSP for API responses
                set_header(
                    "Content-Security-Policy",
                    "default-src 'none'; img-src https: data:; connect-src https:; frame-ancestors 'none'",
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)

