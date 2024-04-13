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
create_table(name="user", columns=["user_id", "group_id"])


class MessageDB:
    @staticmethod
    def store(*, message_id: int, group_id: int, original_message_id: int = None):
        if original_message_id is None:
            original_message_id = message_id
        cursor.execute(f"""
            INSERT INTO message VALUES ({message_id}, {group_id}, {original_message_id}, {int(time.time())})
        """)
        con.commit()
    
    @staticmethod
    def query_original_id(*, message_id: int):
        res = cursor.execute(f"SELECT original_id FROM message WHERE message_id={message_id}")
        if row := res.fetchone():
            return row[0]
        return None

    @staticmethod
    def query_clones(*, message_id: int):
        original_id = MessageDB.query_original_id(message_id=message_id)
        if original_id is None:
            return []
        res = cursor.execute(f"SELECT message_id, group_id FROM message WHERE original_id={original_id}")
        return res.fetchall()

    @staticmethod
    def delete_clones(*, message_id: int):
        original_id = MessageDB.query_original_id(message_id=message_id)
        if original_id:
            cursor.execute(f"DELETE FROM message WHERE original_id={original_id}")
            con.commit()


class UserDB:
    initialized = False

    @staticmethod
    def query_groups(*, user_id: int):
        res = cursor.execute(f"SELECT group_id FROM user WHERE user_id={user_id}")
        if rows := res.fetchall():
            return [row[0] for row in rows]
        return []

    @staticmethod
    def store(*, user_id: int, group_id: int):
        res = UserDB.query_groups(user_id=user_id)
        if group_id not in res:
            cursor.execute(f"INSERT INTO user VALUES ({user_id}, {group_id})")
        con.commit()

    @staticmethod
    def batch_update(*, member_infos: list[dict]):
        for info in member_infos:
            UserDB.store(user_id=info['user_id'], group_id=info['group_id'])

    @staticmethod
    def count():
        res = cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user")
        return res.fetchone()[0]
