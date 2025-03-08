import logging
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, User, Story, StoryPart, ChoiceOption
from story_generator import generate_story

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
async def generate_story_submit(
    request: Request,
    prompt: str = Form(...),
    genre: str = Form(...),
    username: str = Form(default="guest"),  # Optional username for now
    db: Session = Depends(get_db)
):
    try:
        # Get or create user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(username=username)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Generate story
        story_data = generate_story(prompt, genre)
        
        # Create a new story
        story = Story(user_id=user.id, title=f"{genre.capitalize()} Adventure: {prompt[:20]}...")
        db.add(story)
        db.commit()
        db.refresh(story)

        # Save initial story part
        story_part = StoryPart(story_id=story.id, text=story_data["story"])
        db.add(story_part)
        db.commit()
        db.refresh(story_part)

        # Save choices
        for choice_text in story_data["choices"]:
            choice = ChoiceOption(story_part_id=story_part.id, text=choice_text)
            db.add(choice)
        db.commit()

        return templates.TemplateResponse("story.html", {
            "request": request,
            "story": story_data["story"],
            "choices": story_data["choices"],
            "story_id": story.id,
            "story_part_id": story_part.id
        })
    except Exception as e:
        logger.error(f"Story generation failed: {str(e)}")
        return templates.TemplateResponse("generate.html", {
            "request": request,
            "error": str(e)
        })

@app.get("/continue/{story_id}/{choice_id}")
async def continue_story(request: Request, story_id: int, choice_id: int, db: Session = Depends(get_db)):
    try:
        # Get the chosen option
        choice = db.query(ChoiceOption).filter(ChoiceOption.id == choice_id).first()
        if not choice or choice.story_part.story_id != story_id:
            raise HTTPException(status_code=404, detail="Choice or story not found")

        # Generate next part based on the choice
        story = db.query(Story).filter(Story.id == story_id).first()
        prompt = f"Continue this {story.title.split(':')[0].lower()} story where the previous part ended with '{choice.text}'"
        story_data = generate_story(prompt, story.title.split(':')[0].lower())

        # Save new story part
        new_part = StoryPart(
            story_id=story_id,
            text=story_data["story"],
            previous_part_id=choice.story_part_id
        )
        db.add(new_part)
        db.commit()
        db.refresh(new_part)

        # Save new choices
        for choice_text in story_data["choices"]:
            new_choice = ChoiceOption(story_part_id=new_part.id, text=choice_text)
            db.add(new_choice)
        db.commit()

        return templates.TemplateResponse("story.html", {
            "request": request,
            "story": story_data["story"],
            "choices": story_data["choices"],
            "story_id": story_id,
            "story_part_id": new_part.id
        })
    except Exception as e:
        logger.error(f"Continuing story failed: {str(e)}")
        return templates.TemplateResponse("story.html", {
            "request": request,
            "story": "An error occurred while continuing the story.",
            "choices": [],
            "error": str(e),
            "story_id": story_id
        })