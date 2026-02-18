# src/api/routes/user.py
# src\api\routes\user.py
"""
User Management Routes
========================

User profile CRUD operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.schemas.user import UserProfile, UserUpdate, UserResponse
from src.api.middleware.auth import verify_api_key
from src.api.middleware.rate_limit import check_rate_limit
from src.api.dependencies import get_user_manager

router = APIRouter()


@router.get("/user/{user_id}", response_model=UserResponse)
async def get_user(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get user profile by ID.
    
    Returns complete user profile including birth data and preferences.
    
    **Authentication:** Requires X-API-Key header
    """
    await check_rate_limit(request, api_key)
    
    user_manager = get_user_manager()
    
    try:
        user_data = user_manager.get_user(user_id)
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"User {user_id} not found"
            )
        
        return UserResponse(**user_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving user: {str(e)}"
        )


@router.put("/user/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: str,
    user_update: UserUpdate,
    api_key: str = Depends(verify_api_key)
):
    """
    Update user profile.
    
    Updates user information including name, birth data, and preferences.
    
    **Authentication:** Requires X-API-Key header
    """
    await check_rate_limit(request, api_key)
    
    user_manager = get_user_manager()
    
    try:
        # Get existing user
        existing_user = user_manager.get_user(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=404,
                detail=f"User {user_id} not found"
            )
        
        # Prepare update data
        update_data = user_update.model_dump(exclude_unset=True)
        
        # Update user
        updated_user = user_manager.update_user(user_id, update_data)
        
        return UserResponse(**updated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating user: {str(e)}"
        )


@router.post("/user", response_model=UserResponse, status_code=201)
async def create_user(
    request: Request,
    user_profile: UserProfile,
    api_key: str = Depends(verify_api_key)
):
    """
    Create new user profile.
    
    Creates a new user with birth data and preferences.
    
    **Authentication:** Requires X-API-Key header
    """
    await check_rate_limit(request, api_key)
    
    user_manager = get_user_manager()
    
    try:
        # Check if user already exists
        existing_user = user_manager.get_user(user_profile.user_id)
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail=f"User {user_profile.user_id} already exists"
            )
        
        # Create user
        user_data = user_profile.model_dump()
        created_user = user_manager.create_user(user_data)
        
        return UserResponse(**created_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating user: {str(e)}"
        )
