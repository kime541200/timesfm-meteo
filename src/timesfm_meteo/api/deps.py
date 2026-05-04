from __future__ import annotations

from typing import Generator

import psycopg
from fastapi import Request


def get_conn(request: Request) -> Generator[psycopg.Connection, None, None]:
    """Yield a psycopg connection from the app-level pool."""
    with request.app.state.pool.connection() as conn:
        yield conn
