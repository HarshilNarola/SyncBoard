from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Board, BoardMember, Task, User
from ..schemas import (
    BoardCreate,
    BoardDetail,
    BoardResponse,
    MemberResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from ..security import get_current_user
from ..websocket_manager import manager


router = APIRouter(prefix="/api/boards", tags=["boards"])


def require_member(db: Session, board_id: int, user_id: int) -> Board:
    board = db.get(Board, board_id)
    if board is None or db.scalar(
        select(BoardMember.id).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
    ) is None:
        raise HTTPException(status_code=404, detail="Board not found")
    return board


def task_response(task: Task) -> TaskResponse:
    return TaskResponse.model_validate(task)


@router.get("/", response_model=list[BoardResponse])
def list_boards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Board]:
    return list(
        db.scalars(
            select(Board).join(BoardMember).where(BoardMember.user_id == current_user.id).order_by(Board.created_at)
        )
    )


@router.post("/", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
def create_board(
    payload: BoardCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Board:
    board = Board(title=payload.title, owner_id=current_user.id)
    db.add(board)
    db.flush()
    db.add(BoardMember(board_id=board.id, user_id=current_user.id))
    db.commit()
    db.refresh(board)
    return board


@router.get("/{board_id}", response_model=BoardDetail)
def get_board(board_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BoardDetail:
    board = require_member(db, board_id, current_user.id)
    members = list(db.scalars(select(User).join(BoardMember).where(BoardMember.board_id == board_id)))
    tasks = list(db.scalars(select(Task).where(Task.board_id == board_id).order_by(Task.status, Task.position, Task.id)))
    return BoardDetail(
        id=board.id, title=board.title, owner_id=board.owner_id, created_at=board.created_at,
        members=[MemberResponse.model_validate(member) for member in members],
        tasks=[task_response(task) for task in tasks],
    )


@router.post("/{board_id}/members", response_model=MemberResponse)
def invite_member(
    board_id: int, email: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    require_member(db, board_id, current_user.id)
    user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if user is None:
        raise HTTPException(status_code=404, detail="User with that email was not found")
    if db.scalar(select(BoardMember.id).where(BoardMember.board_id == board_id, BoardMember.user_id == user.id)):
        raise HTTPException(status_code=409, detail="User is already a board member")
    db.add(BoardMember(board_id=board_id, user_id=user.id))
    db.commit()
    return user


@router.post("/{board_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    board_id: int, payload: TaskCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Task:
    require_member(db, board_id, current_user.id)
    position = db.scalar(select(func.coalesce(func.max(Task.position), -1) + 1).where(Task.board_id == board_id, Task.status == payload.status))
    task = Task(board_id=board_id, position=position or 0, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    await manager.broadcast(board_id, {"event": "task_created", "task": task_response(task).model_dump(mode="json")})
    return task


@router.patch("/{board_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    board_id: int, task_id: int, payload: TaskUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Task:
    require_member(db, board_id, current_user.id)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.board_id == board_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    await manager.broadcast(board_id, {"event": "task_updated", "task": task_response(task).model_dump(mode="json")})
    return task


@router.delete("/{board_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    board_id: int, task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    require_member(db, board_id, current_user.id)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.board_id == board_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    await manager.broadcast(board_id, {"event": "task_deleted", "task_id": task_id})
