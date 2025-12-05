from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from database import Base
import datetime
import enum

class GameMode(enum.Enum):
    classic = "classic"
    timed = "timed"

class LeaderboardEntry(Base):
    __tablename__ = "leaderboard"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Идентификация игрока
    device_id = Column(String, index=True, nullable=False)
    player_name = Column(String(50), index=True, nullable=False)
    
    # Основные метрики игры
    time_seconds = Column(Integer, nullable=False)  # время решения
    moves = Column(Integer, nullable=False)         # количество ходов
    
    # Параметры игры
    board_size = Column(Integer, nullable=False)    # 3, 4, 5
    game_mode = Column(Enum(GameMode), nullable=False)  # 'classic', 'timed'
    
    # Метки времени
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Leaderboard {self.player_name}: {self.time_seconds}s, {self.moves} moves, {self.game_mode}, {self.board_size}x{self.board_size}>"
