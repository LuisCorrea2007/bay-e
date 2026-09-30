"""BAY-E first-run seed.

The real companion must never start with invented people, pets, medical
reminders or experiences.  First boot therefore seeds only a greeting.
"""
from . import db


def _seed() -> None:
    db.log("info", "core", "Primera inicialización limpia de BAY-E", "seed(clean)")
    db.add_message(
        "baye",
        "Hola. Soy BAY-E. Aún no tengo recuerdos personales: quiero aprenderlos contigo, a partir de experiencias reales.",
        emotion="curious",
    )
