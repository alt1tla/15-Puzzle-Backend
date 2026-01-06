from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
import models
import schemas
from database import engine, get_db, Base
from fastapi.middleware.cors import CORSMiddleware

# Создаем таблицы в базе данных
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="15-Puzzle Leaderboard API",
    description="API для таблицы рейтинга игры 15-Puzzle (Классика и На время)",
    version="1.0.0"
)

# Настройка CORS для React Native приложения
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
        # "http://localhost",
        # "http://localhost:8081",
        # "http://localhost:3000",
        # "http://localhost:19006",  # Expo Dev Tools
        # "http://10.0.2.2:8000",    # Android эмулятор
        # "http://10.0.2.2:19006",   # Android Expo
        # "exp://localhost:19000",    # Expo
        # "exp://1fwpitk-anonymous-8081.exp.direct",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "15-Puzzle Leaderboard API",
        "modes": ["classic", "timed"],
        "board_sizes": [3, 4, 5]
    }

@app.post("/leaderboard/", response_model=schemas.LeaderboardEntryResponse)
async def add_leaderboard_entry(
    entry: schemas.LeaderboardEntryCreate,
    db: Session = Depends(get_db)
):
    """
    Добавить новую запись в таблицу рейтинга
    """
    # Проверяем валидность размера поля
    if entry.board_size not in [3, 4, 5]:
        raise HTTPException(status_code=400, detail="Board size must be 3, 4 or 5")
    
    db_entry = models.LeaderboardEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

@app.get("/leaderboard/", response_model=schemas.LeaderboardResponse)
async def get_leaderboard(
    board_size: int = Query(..., ge=3, le=5, description="Размер поля: 3, 4 или 5"),
    game_mode: schemas.GameMode = Query(..., description="Режим игры: classic или timed"),
    limit: int = Query(50, ge=1, le=100, description="Количество записей"),
    device_id: str = Query(..., description="Device ID пользователя"),
    db: Session = Depends(get_db)
):
    """
    Получить таблицу лидеров для конкретного режима и размера поля
    """
    # 1. Получаем топ игроков по limit
    entries = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.board_size == board_size,
        models.LeaderboardEntry.game_mode == game_mode
    ).order_by(
        models.LeaderboardEntry.time_seconds,
        models.LeaderboardEntry.moves
    ).limit(limit).all()
    
    # 2. Общее количество записей в категории
    total_count = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.board_size == board_size,
        models.LeaderboardEntry.game_mode == game_mode
    ).count()
    
    # 3. Проверяем, есть ли пользователь в топе (среди entries)
    user_in_top = False
    user_position = None
    
    # 4. Если пользователя НЕТ в топе, тогда ищем его позицию отдельно
    if not user_in_top:
        # Найти лучший результат пользователя в этой категории
        user_best_entry = db.query(models.LeaderboardEntry).filter(
            models.LeaderboardEntry.device_id == device_id,
            models.LeaderboardEntry.board_size == board_size,
            models.LeaderboardEntry.game_mode == game_mode
        ).order_by(
            models.LeaderboardEntry.time_seconds,
            models.LeaderboardEntry.moves
        ).first()
        
        if user_best_entry:
            # Подсчитываем позицию пользователя
            # Считаем сколько игроков имеют лучшее время или такое же время, но меньше ходов
            better_players_count = db.query(func.count(models.LeaderboardEntry.id)).filter(
                models.LeaderboardEntry.board_size == board_size,
                models.LeaderboardEntry.game_mode == game_mode,
                (
                    (models.LeaderboardEntry.time_seconds < user_best_entry.time_seconds) |
                    (
                        (models.LeaderboardEntry.time_seconds == user_best_entry.time_seconds) &
                        (models.LeaderboardEntry.moves < user_best_entry.moves)
                    )
                )
            ).scalar()
            
            user_position = better_players_count + 1 if better_players_count is not None else 1
    
    return schemas.LeaderboardResponse(
        entries=entries,
        total_count=total_count,
        board_size=board_size,
        game_mode=game_mode,
        user_position=user_position  
    )


@app.get("/leaderboard/top", response_model=List[schemas.LeaderboardEntryResponse])
async def get_top_players(
    board_size: int = Query(..., ge=3, le=5),
    game_mode: schemas.GameMode = Query(...),
    top_n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Получить топ N игроков для конкретного режима и размера поля
    """
    entries = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.board_size == board_size,
        models.LeaderboardEntry.game_mode == game_mode
    ).order_by(
        models.LeaderboardEntry.time_seconds,
        models.LeaderboardEntry.moves
    ).limit(top_n).all()
    
    return entries

@app.get("/stats/{device_id}", response_model=schemas.PlayerStats)
async def get_player_stats(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Получить общую статистику игрока
    """
    # Общее количество игр
    total_games = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.device_id == device_id
    ).count()
    
    # Лучшее время и ходы
    best_time = db.query(func.min(models.LeaderboardEntry.time_seconds)).filter(
        models.LeaderboardEntry.device_id == device_id
    ).scalar()
    
    best_moves = db.query(func.min(models.LeaderboardEntry.moves)).filter(
        models.LeaderboardEntry.device_id == device_id
    ).scalar()
    
    # Средние показатели
    avg_time = db.query(func.avg(models.LeaderboardEntry.time_seconds)).filter(
        models.LeaderboardEntry.device_id == device_id
    ).scalar()
    
    avg_moves = db.query(func.avg(models.LeaderboardEntry.moves)).filter(
        models.LeaderboardEntry.device_id == device_id
    ).scalar()
    
    return schemas.PlayerStats(
        device_id=device_id,
        total_games=total_games,
        best_time=best_time,
        best_moves=best_moves,
        average_time=float(avg_time) if avg_time else None,
        average_moves=float(avg_moves) if avg_moves else None
    )

@app.get("/stats/{device_id}/detailed")
async def get_detailed_stats(
    device_id: str,
    db: Session = Depends(get_db)
):
    """
    Получить детальную статистику по всем режимам и размерам
    """
    stats = {}
    
    for board_size in [3, 4, 5]:
        for game_mode in [models.GameMode.classic, models.GameMode.timed]:
            key = f"{game_mode.value}_{board_size}x{board_size}"
            
            entries = db.query(models.LeaderboardEntry).filter(
                models.LeaderboardEntry.device_id == device_id,
                models.LeaderboardEntry.board_size == board_size,
                models.LeaderboardEntry.game_mode == game_mode
            ).all()
            
            if entries:
                best_time = min(e.time_seconds for e in entries)
                best_moves = min(e.moves for e in entries)
                avg_time = sum(e.time_seconds for e in entries) / len(entries)
                avg_moves = sum(e.moves for e in entries) / len(entries)
                
                stats[key] = {
                    "games_played": len(entries),
                    "best_time": best_time,
                    "best_moves": best_moves,
                    "average_time": round(avg_time, 2),
                    "average_moves": round(avg_moves, 2)
                }
    
    return {"device_id": device_id, "statistics": stats}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
