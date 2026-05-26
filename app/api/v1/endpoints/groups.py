"""Group endpoints — CRUD and member management."""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.schemas.group import GroupCreate, AddMember, GroupResponse, MemberResponse
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("/", response_model=list[GroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all groups the current user belongs to."""
    result = await db.execute(
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(Group.created_at.desc())
    )
    groups = result.scalars().unique().all()
    return [await _build_group_response(g, db) for g in groups]


@router.post("/", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    group = Group(name=data.name, description=data.description, created_by=current_user.id)
    db.add(group)
    await db.flush()

    # Add creator as admin
    member = GroupMember(group_id=group.id, user_id=current_user.id, role="admin")
    db.add(member)
    await db.flush()

    return await _build_group_response(group, db)


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return await _build_group_response(group, db)


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: uuid.UUID,
    data: AddMember,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify user exists
    user_result = await db.execute(select(User).where(User.id == data.user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    member = GroupMember(group_id=group_id, user_id=data.user_id, role=data.role)
    db.add(member)
    await db.flush()
    return {"message": "Member added"}


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: uuid.UUID, user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    return {"message": "Member removed"}


async def _build_group_response(group: Group, db: AsyncSession) -> GroupResponse:
    result = await db.execute(
        select(GroupMember, User)
        .join(User, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group.id)
    )
    rows = result.all()
    members = [
        MemberResponse(
            id=m.id,
            user_id=m.user_id,
            username=u.username,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m, u in rows
    ]
    return GroupResponse(
        id=group.id, name=group.name, description=group.description,
        created_by=group.created_by, members=members, created_at=group.created_at,
    )
