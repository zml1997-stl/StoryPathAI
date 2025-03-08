from fastapi_users import FastAPIUsers, BaseUserManager, IntegerIDMixin
from fastapi_users.authentication import CookieTransport, AuthenticationBackend, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from models import Base, User  # Import Base and User from models.py
from database import get_db
from fastapi import Depends
from sqlalchemy.orm import Session

SECRET = "SECRET"  # Replace with a secure key in production (e.g., via env var)

class UserManager(IntegerIDMixin, BaseUserManager[User, Integer]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.username} has registered.")

async def get_user_manager(db: Session = Depends(get_db)):
    yield UserManager(SQLAlchemyUserDatabase(User, db))

cookie_transport = CookieTransport(cookie_max_age=3600)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)