from pydantic import BaseModel


class Config(BaseModel):
    """Plugin Config Here"""
    broadcast_sessions: dict = {}
