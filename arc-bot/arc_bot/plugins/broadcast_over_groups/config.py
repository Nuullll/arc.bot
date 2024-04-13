from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""
    broadcast_sessions: dict = {}
    docker_path_map: str = ""
    local_tmp_storage: str = ""
