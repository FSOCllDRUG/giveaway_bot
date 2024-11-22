from sqlalchemy import BigInteger, String, Boolean, DateTime, func, ForeignKey, Table, Column
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
    admins: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_channel_association,
        back_populates="channels"
    )
