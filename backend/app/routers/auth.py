from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.rate_limit import limiter, login_rate, register_rate
from app.schemas.auth import (
    AccessToken,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserOut,
)
from app.services.auth import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    TotpRequiredError,
    authenticate,
    issue_token_pair,
    refresh_access_token,
    register_tenant_and_admin,
    request_password_reset,
    reset_password_with_token,
)
from app.services.security_management import record_session, touch_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limiter.limit(register_rate)
async def register(request: Request, payload: RegisterRequest, db: DbSession) -> TokenPair:
    try:
        user = await register_tenant_and_admin(
            db,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            tenant_name=payload.tenant_name,
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email_already_registered"
        ) from exc

    access, refresh = issue_token_pair(user)
    await record_session(
        db,
        user=user,
        refresh_token=refresh,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair)
@limiter.limit(login_rate)
async def login(request: Request, payload: LoginRequest, db: DbSession) -> TokenPair:
    try:
        user = await authenticate(
            db,
            email=payload.email,
            password=payload.password,
            totp_code=payload.totp_code,
            backup_code=payload.backup_code,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials"
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive"
        ) from exc
    except TotpRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="totp_required"
        ) from exc

    access, refresh = issue_token_pair(user)
    await record_session(
        db,
        user=user,
        refresh_token=refresh,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AccessToken)
async def refresh(payload: RefreshRequest, db: DbSession) -> AccessToken:
    try:
        token = await refresh_access_token(db, refresh_token=payload.refresh_token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token"
        ) from exc

    await touch_session(db, refresh_token=payload.refresh_token)
    return AccessToken(access_token=token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit(login_rate)
async def forgot_password(
    request: Request, payload: ForgotPasswordRequest, db: DbSession
) -> ForgotPasswordResponse:
    reset_link = await request_password_reset(db, email=payload.email)
    settings = get_settings()
    return ForgotPasswordResponse(
        ok=True,
        reset_link=reset_link if reset_link and not settings.is_production else None,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(login_rate)
async def reset_password(
    request: Request, payload: ResetPasswordRequest, db: DbSession
) -> None:
    try:
        await reset_password_with_token(db, token=payload.token, new_password=payload.password)
    except InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_or_expired_reset_token"
        ) from exc


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
