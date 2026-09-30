"""BAY-E first-run seed.

First boot is intentionally empty: no invented people, memories, tasks or
conversation. The companion begins learning only from real interaction.
"""
from . import db


def _seed() -> None:
    db.log("info", "core", "Primera inicialización limpia de BAY-E", "seed(clean)")
