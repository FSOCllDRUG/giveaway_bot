from decouple import config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from db.pg_models import Base

engine = create_async_engine(url=config("DB_URL"))

session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
