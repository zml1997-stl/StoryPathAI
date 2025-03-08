from fastapi_users import FastAPIUsers, BaseUserManager, IntegerIDMixin
from fastapi_users.authentication import CookieTransport, AuthenticationBackend, BearerTransport
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from database import engine, get_db
from fastapi import Depends
from sqlalchemy.orm import Session

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

class UserManager(IntegerIDMixin, BaseUserManager[User, Integer]):
    reset_password_token_secret = "SECRET"
    verification_token_secret = "SECRET"

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.username} has registered.")

async def get_user_manager(db: Session = Depends(get_db)):
    yield UserManager(SQLAlchemyUserDatabase(User, db))

cookie_transport = CookieTransport(cookie_max_age=3600)
bearer_transport = BearerTransport(tokenUrl="auth/login")

auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_user_manager=get_user_manager,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)