"""Shared error types."""


class ProbeError(RuntimeError):
    """Probe or yt-dlp failure with a machine-readable code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code
