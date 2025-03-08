from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)

class StoryPart(Base):
    __tablename__ = "story_parts"
    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    text = Column(String, nullable=False)
    previous_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=True)

class ChoiceOption(Base):
    __tablename__ = "choice_options"
    id = Column(Integer, primary_key=True, index=True)
    story_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=False)
    text = Column(String, nullable=False)
    next_part_id = Column(Integer, ForeignKey("story_parts.id"), nullable=True)