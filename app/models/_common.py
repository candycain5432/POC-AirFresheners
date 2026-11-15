"""Small helpers shared by several model files."""
from datetime import datetime, timezone


def utcnow():
    """Current time in UTC. Stored times are always UTC; convert when displaying."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
