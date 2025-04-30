from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment, Bot, GroupRecallNoticeEvent, GroupIncreaseNoticeEvent, GroupUploadNoticeEvent, PrivateMessageEvent
from nonebot.rule import is_type
from .broadcast import BroadcastManager

class CommandDescriptor:
    def __init__(self, name, func_name, description, identifier='#'):
        self.name = name
        self.func_name = func_name
        self.description = description
        self.identifier = identifier
    
    def __repr__(self):
        return f"{self.identifier}{self.name} - {self.description}"

command_registry = {}

def register(name: str, identifier='#'):
    def wrapper(func):
        command_registry[name] = CommandDescriptor(name, func.__name__, func.__doc__, identifier)
        return func
    return wrapper

class CommandManager:

    def __init__(self, broadcaster: BroadcastManager):
        self.broadcaster = broadcaster

    def match_command(self, msg: str):
        if not msg.startswith('#'):
            return None
        name = msg.split(sep=None, maxsplit=1)[0][1:]
        return command_registry[name].func_name if name in command_registry else None

    async def is_admin(self, bot: Bot, group_id: int, user_id: int):
        try:
            member = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
            return member['role'] in ['owner', 'admin']
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    @register('帮助')
    async def help(self, bot, event):
        """显示此帮助信息"""
        greet = "我是机器人闹闹，会跨群转发消息。除此以外，也支持以下命令：\n"
        msg = greet + '\n'.join(str(cmd) for cmd in command_registry.values())
        await self.broadcaster.send_global_notices(bot, msg, event.group_id)

    @register('禁言')
    async def mute(self, bot, event):
        """禁言消息发送者1小时(仅管理员可用)"""
        if isinstance(event, GroupMessageEvent):
            if not await self.is_admin(bot, event.group_id, event.user_id):
                return
            if event.reply is None:
                await bot.send(event, "请引用回复违规用户的消息")
                return

            _, target_id = await self.broadcaster.get_reply_clone_ids(bot, event.reply)
            groups = self.broadcaster.user_db.query_groups(user_id=target_id)
            if not groups:
                logger.info(f"用户 {target_id} 不在任何群组中")
                return
            nickname = await self.broadcaster.get_user_nickname(bot, groups[0], target_id)
            for group in groups:
                try:
                    await bot.set_group_ban(group_id=group, user_id=target_id, duration=3600)
                except Exception as e:
                    logger.error(f"禁言失败: {e}")
            await self.broadcaster.send_global_notices(bot, f"{nickname}({target_id})已被管理员禁言1小时", event.group_id)

    @register('资源')
    async def resource(self, bot, event):
        """获取Intel显卡AI资源信息"""
        msg = """--- AI绘画 ---
+ Intel Arc A系列独立显卡专用整合包《Arc-SD-v2.1》
  https://www.bilibili.com/video/BV12C4y1q78k (视频简介)
+ Intel Core Ultra 核显专用整合包《Ultra-SD-v2.2》
  https://www.bilibili.com/video/BV1Ku4m1g7gd (视频简介)

--- 其他资源汇总 ---
+ ComfyUI, Fooocus, SD-OpenVINO, kohya_ss, lora-scripts
+ text-generation-webui, ollama, whisper, RVC, facefusion
  https://pd.qq.com/s/5cj75s5pz
"""
        await self.broadcaster.send_global_notices(bot, msg, event.group_id)

