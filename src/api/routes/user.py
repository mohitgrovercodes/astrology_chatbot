# src/api/routes/user.py
# src\api\routes\user.py
"""
User Management Routes — RETIRED
==================================

These routes are no longer active. User profiles are managed via
the stateless Redis session flow:

  1. POST /api/v1/chat/initialize  — send user profile + birth data
  2. POST /api/v1/chat/message     — send messages

The backend (mobile app server) is responsible for persisting user
data in MongoDB and forwarding relevant fields on each session open.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/user/{user_id}", include_in_schema=False)
@router.put("/user/{user_id}", include_in_schema=False)
@router.post("/user", include_in_schema=False)
async def user_routes_retired(*args, **kwargs):
    raise HTTPException(
        status_code=501,
        detail=(
            "User CRUD endpoints have been retired. "
            "Use POST /api/v1/chat/initialize to start a session "
            "with user profile data."
        )
    )
