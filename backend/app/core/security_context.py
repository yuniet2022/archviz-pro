"""Request identity for repository ownership checks; absent only in trusted local tools."""
from contextvars import ContextVar

owner_id: ContextVar[str | None] = ContextVar('project_owner',default=None)
