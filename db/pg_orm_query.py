from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, update, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.pg_models import User, Channel, user_channel_association, Giveaway, GiveawayStatus


async def orm_user_start(session: AsyncSession, data: dict):
    obj = User(
        user_id=data.get("user_id"),
        username=data.get("username"),
        name=data.get("name"),
    )
    session.add(obj)
    await session.commit()
    await session.close()


async def orm_get_user_data(session: AsyncSession, user_id: int):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    await session.close()
    return result.scalar()


async def orm_count_users(session: AsyncSession):
    query = select(func.count(User.user_id))
    result = await session.execute(query)
    await session.close()
    return result.scalar()


async def orm_get_all_users(session: AsyncSession):
    query = select(User).order_by(User.id)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_get_last_10_users(session: AsyncSession):
    query = select(User).order_by(User.id.desc()).limit(10)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_mailing_change(session: AsyncSession, user_id: int, mailing: bool):
    query = (
        update(User)
        .where(User.user_id == user_id)
        .values(mailing=mailing)
    )
    await session.execute(query)
    await session.commit()
    await session.close()


async def orm_mailing_status(session: AsyncSession, user_id: int):
    query = select(User.mailing).where(User.user_id == user_id)
    result = await session.execute(query)
    await session.close()
    return result.scalar()


async def orm_get_mailing_list(session: AsyncSession):
    query = select(User.user_id).where(User.mailing == True)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_not_mailing_users_count(session: AsyncSession):
    query = select(func.count(User.id)).where(User.mailing == False)
    result = await session.execute(query)
    await session.close()
    return result.scalar()


async def orm_add_channel(session: AsyncSession, channel_id: int):
    obj = Channel(channel_id=channel_id)
    session.add(obj)
    await session.commit()
    await session.close()


async def orm_delete_channel(session: AsyncSession, channel_id: int):
    # Удаляем записи из таблицы user_channel_association, связанные с этим каналом
    await session.execute(
        delete(user_channel_association).where(user_channel_association.c.channel_id == channel_id)
    )
    # Удаляем сам канал
    await session.execute(
        delete(Channel).where(Channel.channel_id == channel_id)
    )
    await session.commit()
    await session.close()


async def orm_get_channels_for_admin(session: AsyncSession, admin_user_id: int):
    query = select(Channel).join(user_channel_association).where(user_channel_association.c.user_id == admin_user_id)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_add_admin_to_channel(session: AsyncSession, user_id: int, channel_id: int):
    query = (
        insert(user_channel_association)
        .values(user_id=user_id, channel_id=channel_id)
    )
    await session.execute(query)
    await session.commit()
    await session.close()


async def orm_get_admins(session: AsyncSession):
    query = select(User).where(User.is_admin == True)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_get_admins_id(session: AsyncSession):
    query = select(User.user_id).where(User.is_admin == True)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_add_admin(session: AsyncSession, user_id: int):
    query = update(User).where(User.user_id == user_id).values(is_admin=True)
    await session.execute(query)
    await session.commit()
    await session.close()


async def orm_delete_admin(session: AsyncSession, user_id: int):
    query = update(User).where(User.user_id == user_id).values(is_admin=False)
    await session.execute(query)
    await session.commit()
    await session.close()


async def orm_get_required_channels(session: AsyncSession):
    query = select(Channel).where(Channel.is_required == True)
    result = await session.execute(query)
    await session.close()
    return result.scalars().all()


async def orm_change_required_channel(session: AsyncSession, channel_id: int, required: bool):
    query = update(Channel).where(Channel.channel_id == channel_id).values(is_required=required)
    await session.execute(query)
    await session.commit()
    await session.close()


async def orm_is_required_channel(session: AsyncSession, channel_id: int) -> bool:
    query = select(Channel.is_required).where(Channel.channel_id == channel_id)
    result = await session.execute(query)
    await session.close()
    return result.scalar()


async def orm_create_giveaway(session, data, user_id):
    try:
        end_datetime_str = data.get('end_datetime')
        if isinstance(end_datetime_str, str):
            end_datetime = datetime.fromisoformat(end_datetime_str)
        else:
            end_datetime = None

        post_datetime_str = data.get('post_datetime')
        post_datetime = datetime.fromisoformat(post_datetime_str)

        new_giveaway = Giveaway(
            media_type=data.get('media_type'),
            media=data.get('media'),
            text=data.get('text'),
            button=data.get('button'),
            winners_count=data.get('winners_count'),
            channel_id=data.get('channel_id'),
            post_datetime=post_datetime,
            end_datetime=end_datetime,
            end_count=data.get('end_count'),
            captcha=data.get('captcha', False),
            extra_conditions=data.get('extra_conditions'),
            sponsor_channel_ids=data.get('sponsor_channels', []),
            post_url=data.get('post_url'),
            participants_count=data.get('participants_count', 0),
            winner_ids=data.get('winner_ids', []),
            status='NOT_PUBLISHED',
            user_id=user_id
        )
        session.add(new_giveaway)
        await session.commit()
    except Exception as e:
        print(f"Error creating giveaway: {e}")
        await session.rollback()


async def orm_get_user_giveaways(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(Giveaway.id, Giveaway.text, Giveaway.status)
        .where(Giveaway.user_id == user_id)
        .order_by(Giveaway.id.desc())
    )
    giveaways = result.fetchall()
    await session.close()
    return [(row.id, row.text[:35], row.status) for row in giveaways]


async def orm_delete_giveaway(session: AsyncSession, giveaway_id: int):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    if giveaway:
        await session.delete(giveaway)
        await session.commit()
        await session.close()
        return True
    await session.close()
    return False


async def orm_update_giveaway_end_conditions(session: AsyncSession, giveaway_id: int,
                                             end_datetime: Optional[str], end_count: Optional[int]):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    if giveaway:
        if end_datetime:
            end_time_str = end_datetime
            end_time = datetime.fromisoformat(end_time_str)
            giveaway.end_datetime = end_time
            giveaway.end_count = None
        elif end_count:
            giveaway.end_count = end_count
            giveaway.end_datetime = None
        await session.commit()
        await session.close()
        return True
    await session.close()
    return False


async def orm_get_giveaway_by_id(session: AsyncSession, giveaway_id: int):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    await session.close()
    return giveaway


async def orm_add_winners(session: AsyncSession, giveaway_id: int, new_winners: list[int]):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    if giveaway:
        # Объединяем текущий список победителей с новыми победителями
        current_winners = giveaway.winner_ids or []
        updated_winners = current_winners + new_winners

        # Обновляем запись в базе данных
        await session.execute(
            update(Giveaway).where(Giveaway.id == giveaway_id).values(winner_ids=updated_winners)
        )
        await session.commit()
        await session.close()
        return True
    await session.close()
    return False


# Needed for joining mechanism
async def orm_get_join_giveaway_data(session: AsyncSession, giveaway_id: int):
    result = await session.execute(
        select(Giveaway.sponsor_channel_ids, Giveaway.captcha, Giveaway.status, Giveaway.end_count)
        .where(Giveaway.id == giveaway_id)
    )
    giveaway = result.one_or_none()
    await session.close()
    if giveaway:
        sponsor_channel_ids, captcha, status, end_count = giveaway
        if status == GiveawayStatus.PUBLISHED:
            return sponsor_channel_ids, captcha, end_count
    return None, None, None


async def orm_get_due_giveaways(session: AsyncSession, current_time: datetime):
    result = await session.execute(
        select(Giveaway).where(
            (Giveaway.post_datetime <= current_time) |
            (Giveaway.end_datetime <= current_time) |
            (Giveaway.end_count.is_not(None))
        )
    )
    giveaways = result.scalars().all()
    await session.close()

    not_published = [giveaway for giveaway in giveaways if giveaway.status == GiveawayStatus.NOT_PUBLISHED]
    ready_for_results = [giveaway for giveaway in giveaways if giveaway.status == GiveawayStatus.PUBLISHED]

    return not_published, ready_for_results


async def orm_update_giveaway_status(session: AsyncSession, giveaway_id: int, status: GiveawayStatus):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    if giveaway:
        giveaway.status = status
        await session.commit()
        await session.close()
        return True
    await session.close()
    return False


async def orm_update_giveaway_post_data(session: AsyncSession, giveaway_id: int, post_url: str, message_id: int):
    result = await session.execute(
        select(Giveaway).where(Giveaway.id == giveaway_id)
    )
    giveaway = result.scalar_one_or_none()
    if giveaway:
        giveaway.post_url = post_url
        giveaway.message_id = message_id
        await session.commit()
        await session.close()
        return True
    await session.close()
    return False


async def orm_get_giveaway_end_count(session: AsyncSession, giveaway_id: int) -> Optional[int]:
    result = await session.execute(
        select(Giveaway.end_count).where(Giveaway.id == giveaway_id)
    )
    end_count = int(result.scalar_one_or_none())
    await session.close()
    return end_count


async def orm_update_participants_count(session: AsyncSession, giveaway_id: int, participants_count: int):
    await session.execute(
        update(Giveaway).where(Giveaway.id == giveaway_id).values(participants_count=participants_count)
    )
    await session.commit()


async def orm_get_users_with_giveaways(session: AsyncSession):
    query = (
        select(User.id, User.username, User.user_id)
        .join(Giveaway, User.user_id == Giveaway.user_id)
        .distinct()
        .order_by(User.id.asc())
    )
    result = await session.execute(query)
    return result.all()


async def orm_get_giveaways_by_sponsor_channel_id(session: AsyncSession, sponsor_channel_id: int):
    result = await session.execute(
        select(Giveaway.id).where(Giveaway.sponsor_channel_ids.contains([sponsor_channel_id]))
    )
    giveaway_ids = result.scalars().all()
    await session.close()
    return giveaway_ids
