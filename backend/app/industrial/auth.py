import hashlib
import hmac
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.industrial.models import AuditEvent, Company, Invitation, LoginSession, Membership, User
from app.industrial.schemas import CompanyCreate, Credentials, InvitationAccept, Registration, utc

router = APIRouter(prefix="/industrial/auth", tags=["industrial identity"])
COOKIE = "telemetryx_session"
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f"scrypt${salt}${value.hex()}"


_dummy = password_hash("not-a-real-account-password")


def password_matches(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
        return hmac.compare_digest(password_hash(password, salt), stored)
    except (ValueError, TypeError):
        return False


def audit(
    db: Session,
    company_id: uuid.UUID,
    actor: str,
    action: str,
    entity: object,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            company_id=company_id,
            actor=actor,
            action=action,
            entity_id=str(entity),
            details=details or {},
        )
    )


def login_session(db: Session, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=7 * 86400,
        httponly=True,
        samesite="lax",
        secure=get_settings().environment != "development",
        path="/",
    )


def current_user(request: Request, db: Session = Depends(get_db_session)) -> User:
    token = request.cookies.get(COOKIE)
    session = db.get(LoginSession, digest(token)) if token else None
    if not session or utc(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Sign in to continue")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Account unavailable")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
Database = Annotated[Session, Depends(get_db_session)]


def membership(company_id: uuid.UUID, user: CurrentUser, db: Database) -> Membership:
    member = db.scalars(
        select(Membership).where(
            Membership.company_id == company_id,
            Membership.user_id == user.id,
        )
    ).first()
    if not member:
        raise HTTPException(404, "Workspace not found")
    return member


Member = Annotated[Membership, Depends(membership)]


def require(member: Membership, *roles: str) -> None:
    if member.role not in roles:
        raise HTTPException(403, "Your workspace role cannot perform this action")


def profile(db: Session, user: User) -> dict[str, Any]:
    companies = db.execute(
        select(Company, Membership)
        .join(
            Membership,
            Membership.company_id == Company.id,
        )
        .where(Membership.user_id == user.id)
        .order_by(Company.created_at)
    ).all()
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "companies": [
            {"id": str(company.id), "name": company.name, "role": member.role}
            for company, member in companies
        ],
    }


def rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        # Bound the development limiter's memory. Use a shared gateway limiter in production.
        if len(_attempts) > 10000:
            for stale in list(_attempts):
                if not _attempts[stale] or _attempts[stale][-1] < now - 900:
                    del _attempts[stale]
            if len(_attempts) > 10000:
                raise HTTPException(429, "Sign-in capacity exceeded; try again later")
        queue = _attempts[key]
        while queue and queue[0] < now - 900:
            queue.popleft()
        if len(queue) >= 30:
            raise HTTPException(429, "Too many sign-in attempts; try again in 15 minutes")
        queue.append(now)


@router.post("/register", status_code=201)
def register(
    req: Registration, request: Request, response: Response, db: Database
) -> dict[str, Any]:
    rate_limit(request)
    user = User(email=req.email, name=req.name.strip(), password_hash=password_hash(req.password))
    company = Company(name=req.company_name.strip())
    db.add_all([user, company])
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Account could not be created. Try signing in.") from error
    db.add(Membership(company_id=company.id, user_id=user.id, role="admin"))
    login_session(db, user, response)
    audit(db, company.id, str(user.id), "workspace.created", company.id)
    db.commit()
    return profile(db, user)


@router.post("/login")
def login(req: Credentials, request: Request, response: Response, db: Database) -> dict[str, Any]:
    rate_limit(request)
    user = db.scalars(select(User).where(User.email == req.email)).first()
    matches = password_matches(req.password, user.password_hash if user else _dummy)
    if not user or not matches:
        raise HTTPException(401, "Email or password is incorrect")
    login_session(db, user, response)
    db.commit()
    return profile(db, user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database) -> None:
    token = request.cookies.get(COOKIE)
    session = db.get(LoginSession, digest(token)) if token else None
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(user: CurrentUser, db: Database) -> dict[str, Any]:
    return profile(db, user)


@router.post("/companies", status_code=201)
def company_create(req: CompanyCreate, user: CurrentUser, db: Database) -> dict[str, Any]:
    company = Company(name=req.name.strip())
    db.add(company)
    db.flush()
    db.add(Membership(company_id=company.id, user_id=user.id, role="admin"))
    audit(db, company.id, str(user.id), "workspace.created", company.id)
    db.commit()
    return profile(db, user)


@router.post("/join")
def join(req: InvitationAccept, user: CurrentUser, db: Database) -> dict[str, Any]:
    invite = db.scalars(
        select(Invitation)
        .where(
            Invitation.token_hash == digest(req.token),
        )
        .with_for_update()
    ).first()
    if not invite or invite.used or utc(invite.expires_at) <= datetime.now(UTC):
        raise HTTPException(400, "Invitation is invalid or expired")
    if invite.email != user.email:
        raise HTTPException(403, "Sign in using the invited email address")
    existing = db.scalars(
        select(Membership).where(
            Membership.company_id == invite.company_id,
            Membership.user_id == user.id,
        )
    ).first()
    if existing:
        raise HTTPException(409, "You already belong to this workspace")
    invite.used = True
    db.add(Membership(company_id=invite.company_id, user_id=user.id, role=invite.role))
    audit(db, invite.company_id, str(user.id), "membership.joined", user.id, {"role": invite.role})
    db.commit()
    return profile(db, user)
