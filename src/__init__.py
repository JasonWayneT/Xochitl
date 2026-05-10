"""Xochitl package exports."""

# Expose router for unittest.mock patch targets such as
# `patch("src.router.TieredRouter.route")`.
try:
    from . import router  # noqa: F401
except Exception:
    router = None  # type: ignore[assignment]
