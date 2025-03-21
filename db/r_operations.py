import json
from datetime import datetime, timedelta, timezone

from db.r_engine import redis_conn


async def redis_upd_admins(admins):
    await redis_conn.delete("admins")
    await redis_conn.sadd("admins", *admins)


async def redis_check_admin(user_id) -> bool:
    return await redis_conn.sismember("admins", user_id)


async def redis_temp_channel(us_id, ch_id):
    await redis_conn.set(f"{us_id}", ch_id, ex=120)


async def redis_check_channel(us_id, ch_id):
    value = await redis_conn.get(f"{us_id}")
    if value is None:
        return False
    else:
        return int(value) == ch_id


async def redis_get_channel_id(us_id):
    value = await redis_conn.get(f"{us_id}")
    return int(value) if value is not None else None


# Add group of users to redis
async def redis_set_mailing_users(users):
    await redis_conn.sadd("users_for_mailing", *users)


async def redis_get_mailing_users():
    users = await redis_conn.smembers("users_for_mailing")
    return set(users)


# Delete user from redis after successful mailing
async def redis_delete_mailing_user(user):
    await redis_conn.srem("users_for_mailing", user)


async def redis_set_mailing_msg(msg_id):
    await redis_conn.set("msg_for_mailing", msg_id, ex=21600)


async def redis_get_mailing_msg():
    return await redis_conn.get("msg_for_mailing")


async def redis_set_msg_from(ch_id):
    await redis_conn.set("msg_from", ch_id, ex=21600)


async def redis_get_msg_from():
    return await redis_conn.get("msg_from")


async def redis_set_mailing_btns(btns):
    await redis_conn.set("btns_for_mailing", json.dumps(btns), ex=21600)


async def redis_get_mailing_btns():
    btns_str = await redis_conn.get("btns_for_mailing")
    btns_dict = json.loads(btns_str)
    return btns_dict


async def get_active_users_count(days: int):
    timestamp = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    active_users = 0
    cursor = "0"

    while cursor != 0:
        cursor, keys = await redis_conn.scan(cursor=cursor, match="user_activity:*")
        for key in keys:
            last_activity = await redis_conn.get(key)
            if int(last_activity) > timestamp:
                active_users += 1

    return active_users


# Функция, которая создаёт словарь giveaway_id: список_айди_участников
async def redis_create_giveaway(giveaway_id: int):
    await redis_conn.set(f"giveaway:{giveaway_id}", json.dumps([]))


# Функция, которая добавляет к этому словарю айди участника
async def redis_add_participant(giveaway_id: int, user_id: int):
    participants = await redis_conn.get(f"giveaway:{giveaway_id}")
    if participants is None:
        participants = []
    else:
        participants = json.loads(participants)

    if user_id not in participants:
        participants.append(user_id)
        await redis_conn.set(f"giveaway:{giveaway_id}", json.dumps(participants))


# Функция, которая получает количество участников
async def redis_get_participants_count(giveaway_id: int):
    participants = await redis_conn.get(f"giveaway:{giveaway_id}")
    if participants is None:
        return 0
    participants = json.loads(participants)
    return len(participants)


# Функция, которая получает список участников
async def redis_get_participants(giveaway_id: int):
    participants = await redis_conn.get(f"giveaway:{giveaway_id}")
    if participants is None:
        return None
    return json.loads(participants)


# Функция, которая возвращает последние 20 участников розыгрыша
async def redis_get_last_participants(giveaway_id: int):
    key = f"giveaway:{giveaway_id}"

    participants_json = await redis_conn.get(key)
    if participants_json is None:
        return []

    participants = json.loads(participants_json)  # Декодируем JSON-строку в список
    return participants[-20:]  # Возвращаем последние 20 участников


# Удаляет словарь с юзерами через неделю timedelta(weeks=1)
async def redis_expire_giveaway(giveaway_id: int):
    await redis_conn.expire(f"giveaway:{giveaway_id}", timedelta(weeks=1))
