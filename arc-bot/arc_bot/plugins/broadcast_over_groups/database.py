import nonebot
import nonebot_plugin_localstore as store
import sqlite3
import time

db_file = store.get_data_file("broadcast-over-groups", "broadcast.db")
nonebot.logger.debug(f"Database file: {db_file}")
con = sqlite3.connect(db_file)
cursor = con.cursor()


def create_table(*, name: str, columns: list[str]):
    res = cursor.execute(f"SELECT name FROM sqlite_master WHERE name='{name}'")
    if res.fetchone():
        return
    nonebot.logger.info(f"Creating db table {name}")
    cursor.execute(f"CREATE TABLE {name}({', '.join(columns)})")


create_table(name="message", columns=["message_id", "group_id", "original_id", "timestamp"])


def store_broadcast_message(*, original_message_id: int, broadcast_message_id: int, broadcast_group_id: int):
    cursor.execute(f"""
        INSERT INTO message VALUES
            ({broadcast_message_id}, {broadcast_group_id}, {original_message_id}, {int(time.time())})
    """)
    con.commit()

def get_message_clones(*, message_id: int):
    res = cursor.execute(f"SELECT original_id FROM message WHERE message_id={message_id}")
    if original_id := res.fetchone():
        original_id = original_id[0]
        res = cursor.execute(f"SELECT message_id, group_id FROM message WHERE original_id={original_id}")
        return res.fetchall()
    return []

def delete_message_clones(*, message_id: int):
    res = cursor.execute(f"SELECT original_id FROM message WHERE message_id={message_id}")
    if original_id := res.fetchone():
        original_id = original_id[0]
        cursor.execute(f"DELETE FROM message WHERE original_id={original_id}")
        con.commit()
