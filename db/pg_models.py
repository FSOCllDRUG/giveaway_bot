import enum

from sqlalchemy import BigInteger, String, Boolean, DateTime, func, ForeignKey, Table, Column, Text, Integer, ARRAY, \
    Enum, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    created: Mapped[str] = mapped_column(DateTime, default=func.now())
    updated: Mapped[str] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


# Association table for the many-to-many relationship
user_channel_association = Table(
    "user_channel_association",
    Base.metadata,
    Column("user_id", ForeignKey("Users.user_id"), primary_key=True),
    Column("channel_id", ForeignKey("Channels.channel_id"), primary_key=True)
)


class User(Base):
    __tablename__ = "Users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    mailing: Mapped[bool] = mapped_column(Boolean, default=True)

    giveaways: Mapped[list["Giveaway"]] = relationship("Giveaway", back_populates="creator")

    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        secondary=user_channel_association,
        back_populates="admins"
    )

    __table_args__ = (
        Index('idx_user_user_id', 'user_id'),
        Index('idx_user_mailing', 'mailing'),
    )


class Channel(Base):
    __tablename__ = "Channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    admins: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_channel_association,
        back_populates="channels"
    )

    __table_args__ = (
        Index('idx_channel_channel_id', 'channel_id'),
    )


class GiveawayStatus(enum.Enum):
    NOT_PUBLISHED = "Not published"
    PUBLISHED = "Published"
    FINISHED = "Finished"


class Giveaway(Base):
    __tablename__ = "Giveaways"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    media_type: Mapped[str] = mapped_column(Text, nullable=True)
    media: Mapped[str] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    button: Mapped[str] = mapped_column(Text, nullable=True)
    winners_count: Mapped[int] = mapped_column(Integer, nullable=False)
    post_datetime: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    end_datetime: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    end_count: Mapped[int] = mapped_column(Integer, nullable=True)
    captcha: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_conditions: Mapped[str] = mapped_column(Text, nullable=True)
    sponsor_channel_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    post_url: Mapped[str] = mapped_column(Text, nullable=True)
    participants_count: Mapped[int] = mapped_column(Integer, default=0)
    winner_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=True)
    status: Mapped[GiveawayStatus] = mapped_column(Enum(GiveawayStatus), default=GiveawayStatus.NOT_PUBLISHED)
    user_id: Mapped[int] = mapped_column(ForeignKey("Users.user_id"), nullable=False)
    creator: Mapped["User"] = relationship("User", back_populates="giveaways")

    __table_args__ = (
        Index('idx_giveaway_user_id', 'user_id'),
        Index('idx_giveaway_id', 'id'),
        Index('idx_giveaway_status', 'status'),
        Index('idx_giveaway_post_datetime', 'post_datetime'),
    )
