from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, status

from app.api.schemas import LoginRequest, LoginResponse
from app.core.auth import authenticate_user, create_access_token, get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

settings = get_settings()


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate user and get access token",
    description="Login with username and password to receive a JWT access token"
)
async def login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()]
) -> LoginResponse:
    """
    Authenticate user and return JWT access token.

    Args:
        username: The username (Analytics Vidhya)
        password: The password (Hire@2026)

    Returns:
        LoginResponse with access token and expiration info

    Raises:
        HTTPException: If credentials are invalid
    """
    if not authenticate_user(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"username": username},
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60  # Convert to seconds
    )


@router.post(
    "/login-json",
    response_model=LoginResponse,
    summary="Authenticate user with JSON payload",
    description="Alternative login endpoint that accepts JSON instead of form data"
)
async def login_json(request: LoginRequest) -> LoginResponse:
    """
    Authenticate user and return JWT access token (JSON version).

    Args:
        request: LoginRequest with username and password

    Returns:
        LoginResponse with access token and expiration info

    Raises:
        HTTPException: If credentials are invalid
    """
    if not authenticate_user(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"username": request.username},
        expires_delta=access_token_expires
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60  # Convert to seconds
    )


@router.get(
    "/me",
    summary="Get current user info",
    description="Get information about the currently authenticated user"
)
async def get_me(current_user: str = Depends(get_current_user)) -> dict:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from token

    Returns:
        Dict with user information
    """
    return {
        "username": current_user,
        "authenticated": True,
        "message": "Successfully authenticated"
    }


@router.post(
    "/verify",
    summary="Verify token validity",
    description="Verify if the current token is valid and not expired"
)
async def verify_token(current_user: str = Depends(get_current_user)) -> dict:
    """
    Verify token validity.

    Args:
        current_user: Current authenticated user from token

    Returns:
        Dict with verification status
    """
    return {
        "valid": True,
        "username": current_user,
        "message": "Token is valid"
    }