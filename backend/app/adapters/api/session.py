"""Browser session identifier sent by the frontend in the X-Session-Id header."""

from fastapi import Header

MAX_SESSION_ID_LENGTH = 64  # matches carts.session_id


class MissingSession(Exception):
    """The request has no X-Session-Id header."""


class InvalidSessionId(Exception):
    """The X-Session-Id header is blank or too long."""


def get_session_id(x_session_id: str | None = Header(default=None)) -> str:
    if x_session_id is None:
        raise MissingSession
    if not x_session_id.strip() or len(x_session_id) > MAX_SESSION_ID_LENGTH:
        raise InvalidSessionId
    return x_session_id
