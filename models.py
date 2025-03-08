from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# User model from auth.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    stories = relationship("Story", back_populates="user")
    sessions = relationship("SessionParticipant", back_populates="user")

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    user = relationship("User", back_populates="stories")
    parts = relationship("StoryPart", back_populates="story")
    session = relationship("Session", back_populates="story", uselist=False)

class StoryPart(Base):
    __tablename__ = "story_parts"
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    text = Column(String, nullable=False)
    previous_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=True)
    story = relationship("Story", back_populates="parts")
    choices = relationship("ChoiceOption", back_populates="story_part", foreign_keys="ChoiceOption.story_part_id")
    previous_part = relationship("StoryPart", remote_side=[id])

class ChoiceOption(Base):
    __tablename__ = "choice_options"
    id = Column(Integer, primary_key=True, index=True)
    story_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=False)
    text = Column(String, nullable=False)
    next_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=True)
    story_part = relationship("StoryPart", back_populates="choices", foreign_keys=[story_part_id])
    next_part = relationship("StoryPart", foreign_keys=[next_part_id])

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    story = relationship("Story", back_populates="session")
    participants = relationship("SessionParticipant", back_populates="session")

class SessionParticipant(Base):
    __tablename__ = "session_participants"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session = relationship("Session", back_populates="participants")
    user = relationship("User", back_populates="sessions")