"""
Database models (tables), split into one file per area of the site.

Importing this package imports every model so SQLAlchemy knows about all
tables before `db.create_all()` runs. Elsewhere you can simply write:
    from app.models import Product, Order
"""
from .car import BuildLogEntry, CarPhoto, FundEntry, FundingGoal, Install, InstallPhoto, RevivalCar
from .codes import CodeBatch, FreshenerCode
from .garage import CarOfTheMonth, GarageMember
from .meets import MeetDrop
from .security import FailedAttempt
from .shop import BlindBagResult, BlindBagScent, Order, OrderItem, Product
from .voting import PartOption, PartTier, Vote, VoteRound

__all__ = [
    "RevivalCar", "CarPhoto", "BuildLogEntry", "Install", "InstallPhoto", "FundingGoal", "FundEntry",
    "CodeBatch", "FreshenerCode",
    "GarageMember", "CarOfTheMonth",
    "MeetDrop",
    "FailedAttempt",
    "Product", "BlindBagScent", "BlindBagResult", "Order", "OrderItem",
    "VoteRound", "PartOption", "PartTier", "Vote",
]
