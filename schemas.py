from pydantic import BaseModel, EmailStr
from typing import Optional

# Read schema (response)
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    is_superuser: bool

    class Config:
        from_attributes = True  # Updated for Pydantic V2

# Create schema (request)
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False

    class Config:
        from_attributes = True  # Updated for Pydantic V2