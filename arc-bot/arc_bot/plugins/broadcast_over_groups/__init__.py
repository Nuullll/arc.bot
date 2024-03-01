from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment, Bot, GroupRecallNoticeEvent
from nonebot import on_message, logger, on_notice
from nonebot.rule import is_type
from .database import store_broadcast_message, get_message_clones, delete_message_clones

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="broadcast-over-groups",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)


broadcast = on_message(rule=is_type(GroupMessageEvent))
@broadcast.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    session = None
    for session_name, groups in config.broadcast_sessions.items():
        if event.group_id in groups:
            session = session_name
            break
    if session is None:
        return

    logger.debug(f"Broadcasting over session {session}")
    store_broadcast_message(original_message_id=event.message_id, broadcast_message_id=event.message_id, broadcast_group_id=event.group_id)
    user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)
    for group in config.broadcast_sessions[session]:
        if group == event.group_id:
            continue

        reply_clone_id = None
        if reply := event.reply:
            reply_msg_id = reply.message_id
            message_clones = get_message_clones(message_id=reply_msg_id)
            for msg_id, group_id in message_clones:
                if group == group_id:
                    reply_clone_id = msg_id
        msg = f'{user_info["nickname"]}:\n' + event.get_message()
        if reply_clone_id is not None:
            msg = MessageSegment.reply(reply_clone_id) + msg
        response = await bot.send_group_msg(group_id=group, message=msg)
        store_broadcast_message(original_message_id=event.message_id, broadcast_message_id=response['message_id'], broadcast_group_id=group)


recall = on_notice(rule=is_type(GroupRecallNoticeEvent))
@recall.handle()
async def _(bot: Bot, event: GroupRecallNoticeEvent):
    recalled_msg_id = event.message_id
    message_clones = get_message_clones(message_id=recalled_msg_id)
    logger.debug(f"Recalled msg id = {recalled_msg_id}, Clones = {message_clones}")
    for msg_id, _ in message_clones:
        await bot.delete_msg(message_id=msg_id)
    delete_message_clones(message_id=recalled_msg_id)
