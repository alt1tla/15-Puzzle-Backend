from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum

class GameMode(str, Enum):
    CLASSIC = "classic"
    TIMED = "timed"

class LeaderboardEntryBase(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=100)
    player_name: str = Field(..., min_length=1, max_length=50)
    time_seconds: int = Field(..., ge=1)  # минимум 1 секунда
    moves: int = Field(..., ge=1)         # минимум 1 ход
    board_size: int = Field(..., ge=3, le=5)  # только 3,4,5
    game_mode: GameMode

class LeaderboardEntryCreate(LeaderboardEntryBase):
    pass

class LeaderboardEntryResponse(LeaderboardEntryBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class LeaderboardResponse(BaseModel):
    entries: List[LeaderboardEntryResponse]
    total_count: int
    board_size: int
    game_mode: GameMode

class PlayerStats(BaseModel):
    device_id: str
    total_games: int
    best_time: Optional[int]
    best_moves: Optional[int]
    average_time: Optional[float]
    average_moves: Optional[float]
