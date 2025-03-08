import logging
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, User
from story_generator import generate_story  # Absolute import

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize database tables
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
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"id": user.id, "username": user.username}

@app.get("/generate")
async def generate_story_form(request: Request):
    return templates.TemplateResponse("generate.html", {"request": request})

@app.post("/generate")
async def generate_story_submit(request: Request, prompt: str = Form(...), genre: str = Form(...)):
    try:
        story_data = generate_story(prompt, genre)
        return templates.TemplateResponse("story.html", {
            "request": request,
            "story": story_data["story"],
            "choices": story_data["choices"]
        })
    except Exception as e:
        logger.error(f"Story generation failed: {str(e)}")
        return templates.TemplateResponse("generate.html", {
            "request": request,
            "error": str(e)
        })