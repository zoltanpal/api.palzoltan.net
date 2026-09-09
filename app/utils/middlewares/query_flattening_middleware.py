"""
Convert comma-delimited query parameter strings into repeated query parameters.
Example:
  ?id=1,2&id=3  ->  ?id=1&id=2&id=3
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode

from starlette.types import ASGIApp, Receive, Scope, Send


class QueryStringFlatteningMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        separator: str = ",",
        strip: bool = True,
        keep_blank_values: bool = True,
    ) -> None:
        self.app = app
        self.separator = separator
        self.strip = strip
        self.keep_blank_values = keep_blank_values

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw_qs: bytes = scope.get("query_string", b"") or b""
        if not raw_qs:
            await self.app(scope, receive, send)
            return

        parsed = parse_qs(
            raw_qs.decode("utf-8", errors="replace"),
            keep_blank_values=self.keep_blank_values,
        )

        flattened: dict[str, list[str]] = {}
        for name, values in parsed.items():
            out: list[str] = []
            for v in values:
                parts = v.split(self.separator) if self.separator else [v]
                if self.strip:
                    parts = [p.strip() for p in parts]
                # drop empty parts created by ",," or leading/trailing commas
                out.extend([p for p in parts if p != ""])
            flattened[name] = (
                out if out else values
            )  # fallback: keep original if everything filtered

        new_qs = urlencode(flattened, doseq=True).encode("utf-8")

        if new_qs != raw_qs:
            # scope is mutable in Starlette/FastAPI middleware
            scope["query_string"] = new_qs

        await self.app(scope, receive, send)
