from nonebot import get_plugin_config, on_message, logger, on_notice, on_command
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment, Bot, GroupRecallNoticeEvent, GroupIncreaseNoticeEvent, GroupUploadNoticeEvent, PrivateMessageEvent
from nonebot.rule import is_type, to_me
from nonebot.permission import SUPERUSER

from .config import Config
from .broadcast import BroadcastManager

__plugin_meta__ = PluginMetadata(
    name="broadcast-over-groups",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)
broadcaster = BroadcastManager(config)

broadcast = on_message(rule=is_type(GroupMessageEvent))
@broadcast.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    await broadcaster.on_group_message_event(bot, event)

recall = on_notice(rule=is_type(GroupRecallNoticeEvent))
@recall.handle()
async def _(bot: Bot, event: GroupRecallNoticeEvent):
    await broadcaster.on_group_recall_notice_event(bot, event)

welcome = on_notice(rule=is_type(GroupIncreaseNoticeEvent))
@welcome.handle()
async def _(bot: Bot, event: GroupIncreaseNoticeEvent):
    await broadcaster.on_group_increase_notice_event(bot, event)

group_file = on_notice(rule=is_type(GroupUploadNoticeEvent))
@group_file.handle()
async def _(bot: Bot, event: GroupUploadNoticeEvent):
    await broadcaster.on_group_upload_notice_event(bot, event)

help = on_command('help', rule=is_type(GroupMessageEvent), permission=SUPERUSER, aliases=set("帮助"))
@help.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    logger.info(f"Entering help command: {event}")
