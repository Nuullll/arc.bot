from .database import MessageDB, UserDB
from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment, Bot, GroupRecallNoticeEvent, GroupIncreaseNoticeEvent, GroupUploadNoticeEvent
from nonebot.adapters.onebot.v11.event import Reply
import requests
import os

class BroadcastManager:
    def __init__(self, config):
        self.msg_db = MessageDB
        self.user_db = UserDB
        self.broadcast_sessions = config.broadcast_sessions
        self.docker_path_map = config.docker_path_map
        self.local_tmp_storage = config.local_tmp_storage
    
    @property
    def local_path_prefix(self):
        return self.docker_path_map.split(':')[0]
    
    @property
    def container_path_prefix(self):
        return self.docker_path_map.split(':')[1]

    def get_groups_to_broadcast(self, group_id: int):
        for session_name, groups in self.broadcast_sessions.items():
            if group_id in groups:
                return groups
        return []

    async def init_user_db(self, bot: Bot):
        if self.user_db.initialized:
            return
        # initialize user db for all sessions
        for groups in self.broadcast_sessions.values():
            for group in groups:
                members = await bot.get_group_member_list(group_id=group)
                logger.info(f"Retrieved {len(members)} member infos for {group}")
                self.user_db.batch_update(member_infos=members)
        logger.info(f"{self.user_db.count()} unique users!")
        self.user_db.initialized = True

    async def postprocess_msg(self, bot: Bot, msg: Message, group_id: int):
        new_msg = Message("")
        for seg in msg:
            new_seg = seg
            if seg.type == "at":
                # translate [cq:at] to @nickname if user is not in the group
                atee_id = seg.data.get("qq") or 0
                groups = self.user_db.query_groups(user_id=atee_id)
                if not groups:
                    new_seg = ""
                if group_id not in groups:
                    nickname = await self.get_user_nickname(bot, groups[0], atee_id)
                    new_seg = f"@{nickname}"
            elif seg.type == "image":
                # W/A for unable to forward images from multimedia.nt.qq.com.cn
                url = seg.data.get("url")
                if url.startswith("https://multimedia.nt.qq.com.cn/"):
                    img_bytes = self.get_url_content(url)
                    if img_bytes:
                        new_seg = MessageSegment.image(img_bytes)
                    else:
                        new_seg = MessageSegment.text("[图片转发失败]")
            new_msg += new_seg
        return new_msg
        
    # If message is a reply to another message "M", find the message clone ids of "M" in each group to broadcast
    async def get_reply_clone_ids(self, bot: Bot, reply: Reply):
        reply_msg_id = reply.message_id
        reply_original_id = self.msg_db.query_original_id(message_id=reply_msg_id)
        reply_original_msg = await bot.get_msg(message_id=reply_original_id)
        atee_id = reply_original_msg['sender']['user_id']
        message_clones = self.msg_db.query_clones(message_id=reply_msg_id)
        return {group_id: msg_id for msg_id, group_id in message_clones}, atee_id

    async def generate_broadcast_messages(self, bot: Bot, event: GroupMessageEvent, nickname: str, group_list: list[int]):
        if event.reply:
            reply_clone_ids, atee_id = await self.get_reply_clone_ids(bot, event.reply)

        assert event.group_id in group_list
        source_group_idx = group_list.index(event.group_id)
        for group_id in group_list:
            if group_id == event.group_id:
                continue
            msg = event.get_message() + f'\n  -- {nickname}[{source_group_idx+1}群]'
            if event.reply:
                if reply_clone_id := reply_clone_ids.get(group_id):
                    msg = MessageSegment.reply(reply_clone_id) + MessageSegment.at(user_id=atee_id) + MessageSegment.at(user_id=atee_id) + '\n' + msg
            
            msg = await self.postprocess_msg(bot, msg, group_id)
            yield group_id, msg

    async def get_user_nickname(self, bot: Bot, group_id: int, user_id: int):
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        return user_info["nickname"]

    async def on_group_message_event(self, bot: Bot, event: GroupMessageEvent):
        await self.init_user_db(bot)
        groups = self.get_groups_to_broadcast(event.group_id)
        if not groups:
            return

        nickname = await self.get_user_nickname(bot, event.group_id, event.user_id)

        self.msg_db.store(message_id=event.message_id, group_id=event.group_id)

        async for group_id, msg in self.generate_broadcast_messages(bot, event, nickname, groups):
            response = await bot.send_group_msg(group_id=group_id, message=msg)
            self.msg_db.store(message_id=response['message_id'], group_id=group_id, original_message_id=event.message_id)

    async def on_group_recall_notice_event(self, bot: Bot, event: GroupRecallNoticeEvent):
        recalled_msg_id = event.message_id
        message_clones = self.msg_db.query_clones(message_id=recalled_msg_id)
        logger.debug(f"Recalled msg id = {recalled_msg_id}, Clones = {message_clones}")
        for msg_id, _ in message_clones:
            await bot.delete_msg(message_id=msg_id)
        self.msg_db.delete_clones(message_id=recalled_msg_id)

    async def send_global_notices(self, bot: Bot, msg: Message, group_list: list[int]):
        orig_msg_id = None
        for group_id in group_list:
            response = await bot.send_group_msg(group_id=group_id, message=msg)
            if orig_msg_id is None:
                orig_msg_id = response['message_id']
            self.msg_db.store(message_id=response['message_id'], group_id=group_id, original_message_id=orig_msg_id)

    async def on_group_increase_notice_event(self, bot: Bot, event: GroupIncreaseNoticeEvent):
        await self.init_user_db(bot)
        self.user_db.store(user_id=event.user_id, group_id=event.group_id)
        num_members = self.user_db.count()
        user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=event.user_id)

        groups = self.get_groups_to_broadcast(event.group_id)

        msg = MessageSegment.at(user_id=event.user_id)
        msg += f"""欢迎 Arc.AI.Next 社群的第{num_members}位成员 {user_info["nickname"]} !
我是机器人闹闹，我会在Arc.AI.Next的所有({len(groups)}个)群里同步转发所有人的发言！
祝您玩得开心！"""

        await self.send_global_notices(bot, msg, groups)

    def download_file(self, url: str, filename: str):
        filepath = os.path.join(self.local_tmp_storage, filename)
        # make sure absolute path is still under self.local_tmp_storage
        # to avoid path traversal attacks
        filepath = os.path.abspath(filepath)
        if not filepath.startswith(self.local_tmp_storage):
            logger.error(f"Invalid filepath {filepath}")
            return None

        content = self.get_url_content(url)
        if content is None:
            return None

        with open(filepath, "wb") as f:
            f.write(content)
        return self.get_path_in_container(filepath)

    def get_url_content(self, url: str):
        r = requests.get(url, verify=False)
        if r.status_code != 200:
            logger.error(f"Failed to download file from {url}")
            return None
        return r.content

    def delete_file(self, filepath: str):
        filepath = self.get_path_on_local(filepath)
        if not filepath.startswith(self.local_tmp_storage):
            return
        if not os.path.exists(filepath):
            return
        os.remove(filepath)
        
    def get_path_in_container(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if not filepath.startswith(self.local_path_prefix):
            return None
        return filepath.replace(self.local_path_prefix, self.container_path_prefix)

    def get_path_on_local(self, filepath: str):
        filepath = os.path.abspath(filepath)
        if not filepath.startswith(self.container_path_prefix):
            return None
        return filepath.replace(self.container_path_prefix, self.local_path_prefix)

    async def on_group_upload_notice_event(self, bot: Bot, event: GroupUploadNoticeEvent):
        if event.user_id == int(bot.self_id):
            return

        groups = self.get_groups_to_broadcast(event.group_id)
        if not groups:
            return

        filename, filesize, url = event.file.name, event.file.size, event.file.url
        if filesize >= 20*1024*1024:
            nickname = await self.get_user_nickname(bot, event.group_id, event.user_id)
            await self.send_global_notices(bot, MessageSegment.text(f"{nickname} 上传了一个超大文件，无法转发"), groups)
            return
        filename = f"{event.user_id}-{filename}"
        logger.debug(f"Downloading file {filename} ({filesize}B) from {url}")
        downloaded = self.download_file(url, filename)
        if downloaded is None:
            return

        try:
            for group in groups:
                if group == event.group_id:
                    continue
                r = await bot.call_api("upload_group_file", group_id=group, file=downloaded, name=filename)
                logger.debug(r)
        finally:
            self.delete_file(downloaded)
