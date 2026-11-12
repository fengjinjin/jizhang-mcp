from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CHAR, Date, DateTime, ForeignKey, Identity, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from jizhang_mcp.db.models.base import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="CNY")
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"))
    root_category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"))
    category_path: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    wishlist_item_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("wishlist_items.id", ondelete="SET NULL"), nullable=True
    )
    recurring_rule_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("recurring_rules.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_for_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
