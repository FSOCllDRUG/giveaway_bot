from sqlalchemy import BigInteger, String, Boolean, DateTime, func, ForeignKey, Table, Column, Text, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    created: Mapped[str] = mapped_column(DateTime, default=func.now())
    updated: Mapped[str] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


# Association table for the many-to-many relationship
user_channel_association = Table(
    'user_channel_association',
    Base.metadata,
    Column('user_id', ForeignKey('Users.user_id'), primary_key=True),
    Column('channel_id', ForeignKey('Channels.channel_id'), primary_key=True)
)


class User(Base):
    __tablename__ = "Users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    mailing: Mapped[bool] = mapped_column(Boolean, default=True)

    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        secondary=user_channel_association,
        back_populates="admins"
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


# class Giveaway(Base):
#     __tablename__ = "Giveaways"
#
#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     text: Mapped[str] = mapped_column(Text, nullable=True)
#     media_id: Mapped[str] = mapped_column(Text, nullable=True)
#     captcha: Mapped[bool] = mapped_column(Boolean, default=False)
#     end_time: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
#     max_participants: Mapped[int] = mapped_column(Integer, nullable=True)
#     is_active: Mapped[bool] = mapped_column(Boolean, default=True)
#
#     sponsor_channels: Mapped[list["SponsorChannel"]] = relationship(
#         "SponsorChannel",
#         back_populates="giveaway"
#     )
#
#
# class SponsorChannel(Base):
#     __tablename__ = "SponsorChannels"
#
#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
#     giveaway_id: Mapped[int] = mapped_column(ForeignKey('Giveaways.id'), nullable=False)
#
#     giveaway: Mapped["Giveaway"] = relationship(
#         "Giveaway",
#         back_populates="sponsor_channels"
#     )
