import logging
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db  # Absolute imports
from models import Base, User        # Absolute imports

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize database tables with error handling
try:
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}")
    raise

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message": "Welcome to StoryPath!"})

@app.get("/test-user/{username}")
async def test_user(username: str, db: Session = Depends(get_db)):
    # Check if user exists, if not create one
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"id": user.id, "username": user.username}