from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, asc, cast, Integer
from typing import List
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
    if entry.board_size not in [3, 4, 5]:
        raise HTTPException(status_code=400, detail="Board size must be 3, 4 or 5")

    game_mode_db = models.GameMode(entry.game_mode.value)

    # 1. Ищем ЛУЧШУЮ существующую запись пользователя
    existing_entries = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.device_id == entry.device_id,
        models.LeaderboardEntry.board_size == entry.board_size,
        models.LeaderboardEntry.game_mode == game_mode_db
    ).all()

    def is_new_better(new, old):
        if game_mode_db == models.GameMode.classic:
            return (new.moves, new.time_seconds) < (old.moves, old.time_seconds)
        else:  # timed
            return (new.time_seconds, new.moves) < (old.time_seconds, old.moves)

    best_existing = None
    if existing_entries:
        best_existing = min(
            existing_entries,
            key=lambda e: (
                e.moves, e.time_seconds
            ) if game_mode_db == models.GameMode.classic
            else (
                e.time_seconds, e.moves
            )
        )

        # 2. Если новая запись ХУЖЕ — отклоняем
        if not is_new_better(entry, best_existing):
            raise HTTPException(
                status_code=409,
                detail="Existing result is better or equal"
            )

        # 3. Удаляем старую лучшую запись
        db.delete(best_existing)
        db.commit()

    # 4. Сохраняем новую
    db_entry = models.LeaderboardEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    return db_entry

@app.get("/leaderboard/", response_model=schemas.LeaderboardResponse)
async def get_leaderboard(
    board_size: int = Query(..., ge=3, le=5),
    game_mode: schemas.GameMode = Query(...),
    limit: int = Query(50, ge=1, le=100),
    device_id: str = Query(...),
    db: Session = Depends(get_db)
):
    # 1. Получаем топ игроков
    if game_mode.value == models.GameMode.classic.value:
        query = db.query(models.LeaderboardEntry).filter(
            models.LeaderboardEntry.board_size == board_size,
            models.LeaderboardEntry.game_mode == game_mode
        ).order_by(
            asc(cast(models.LeaderboardEntry.moves, Integer)),  # Явный ASC
            asc(cast(models.LeaderboardEntry.time_seconds, Integer))
        )
    else:  # timed
        query = db.query(models.LeaderboardEntry).filter(
            models.LeaderboardEntry.board_size == board_size,
            models.LeaderboardEntry.game_mode == game_mode
        ).order_by(
            asc(cast(models.LeaderboardEntry.time_seconds, Integer)),
            asc(cast(models.LeaderboardEntry.moves, Integer))
        )
    
    entries = query.limit(limit).all()
    total_count = db.query(models.LeaderboardEntry).filter(
        models.LeaderboardEntry.board_size == board_size,
        models.LeaderboardEntry.game_mode == game_mode
    ).count()
    
    # 2. Проверяем, есть ли пользователь в топе
    user_position = None
    user_in_top = False
    
    for i, entry in enumerate(entries, 1):
        if entry.device_id == device_id:
            user_in_top = True
            user_position = i
            break
    
    # 3. Если пользователя нет в топе, ищем его позицию
    if not user_in_top:
        # Найти ВСЕ записи пользователя
        user_entries = db.query(models.LeaderboardEntry).filter(
            models.LeaderboardEntry.device_id == device_id,
            models.LeaderboardEntry.board_size == board_size,
            models.LeaderboardEntry.game_mode == game_mode
        ).all()
        if user_entries:
            # Находим лучший результат пользователя
            if game_mode.value == models.GameMode.classic.value:
                user_best_entry = min(user_entries, key=lambda x: (x.moves, x.time_seconds))
            else:  # timed
                user_best_entry = min(user_entries, key=lambda x: (x.time_seconds, x.moves))
            # Подсчитываем позицию
            # Получаем ВСЕ записи в категории с правильной сортировкой
            all_query = db.query(models.LeaderboardEntry).filter(
                models.LeaderboardEntry.board_size == board_size,
                models.LeaderboardEntry.game_mode == game_mode
            )
            
            if game_mode.value == models.GameMode.classic.value:
                all_entries = all_query.order_by(
                    asc(cast(models.LeaderboardEntry.moves, Integer)),  # Явный ASC
                    asc(cast(models.LeaderboardEntry.time_seconds, Integer))
                ).all()
            else:
                all_entries = all_query.order_by(
                    asc(cast(models.LeaderboardEntry.time_seconds, Integer)),
                    asc(cast(models.LeaderboardEntry.moves, Integer))
                ).all()
            
            # Ищем позицию пользователя
            for i, entry in enumerate(all_entries, 1):
                if (entry.device_id == device_id and 
                    entry.moves == user_best_entry.moves and
                    entry.time_seconds == user_best_entry.time_seconds):
                    user_position = i
                    break
    return schemas.LeaderboardResponse(
        entries=entries,
        total_count=total_count,
        board_size=board_size,
        game_mode=game_mode,
        user_position=user_position
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
