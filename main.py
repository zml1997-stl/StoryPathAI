import logging
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, User, Story, StoryPart, ChoiceOption
from story_generator import generate_story

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/generate")
async def generate_story_form(request: Request, db: Session = Depends(get_db)):
    genres = ["fantasy", "sci-fi", "horror", "mystery", "comedy", "action", "adventure", "romance", "drama"]
    genre = request.query_params.get("genre", "fantasy")
    prompt = request.query_params.get("prompt", "")
    starters = [(i, generate_story(prompt, genre)["story"]) for i in range(3)]  # Pre-zip with indices
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "genres": genres,
        "starters": starters,  # Now a list of (index, story) tuples
        "selected_genre": genre,
        "prompt": prompt
    })

@app.post("/start")
async def start_story(
    request: Request,
    starter: int = Form(...),
    genre: str = Form(...),
    prompt: str = Form(default=""),
    username: str = Form(default="guest"),
    db: Session = Depends(get_db)
):
    starters = [generate_story(prompt, genre)["story"] for _ in range(3)]
    selected_story = starters[starter]
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)

    story = Story(user_id=user.id, title=f"{genre.capitalize()} Tale: {prompt[:20] or 'Untitled'}...")
    db.add(story)
    db.commit()
    db.refresh(story)

    story_data = generate_story(prompt, genre)
    story_part = StoryPart(story_id=story.id, text=selected_story)
    db.add(story_part)
    db.commit()
    db.refresh(story_part)

    choice_objects = [ChoiceOption(story_part_id=story_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    db.commit()
    for choice in choice_objects:
        db.refresh(choice)

    return RedirectResponse(url=f"/story/{story.id}", status_code=303)

@app.get("/story/{story_id}")
async def view_story(request: Request, story_id: int, db: Session = Depends(get_db)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    parts = db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id).all()
    current_part = parts[-1] if parts else None
    choices = db.query(ChoiceOption).filter(ChoiceOption.story_part_id == current_part.id).all() if current_part else []
    return templates.TemplateResponse("story.html", {
        "request": request,
        "story": "\n\n".join(part.text for part in parts),
        "choices": [(choice.text, choice.id) for choice in choices],
        "story_id": story_id
    })

@app.post("/continue/{story_id}/{choice_id}")
async def continue_story(story_id: int, choice_id: int, db: Session = Depends(get_db)):
    choice = db.query(ChoiceOption).filter(ChoiceOption.id == choice_id).first()
    if not choice or choice.story_part.story_id != story_id:
        raise HTTPException(status_code=404, detail="Choice not found")
    
    story = db.query(Story).filter(Story.id == story_id).first()
    genre = story.title.split(':')[0].lower()
    story_data = generate_story(choice.text, genre, is_continuation=True)

    new_part = StoryPart(story_id=story_id, text=story_data["story"], previous_part_id=choice.story_part_id)
    db.add(new_part)
    db.commit()
    db.refresh(new_part)

    choice_objects = [ChoiceOption(story_part_id=new_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    db.commit()

    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/end/{story_id}")
async def end_story(story_id: int, db: Session = Depends(get_db)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    parts = db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id).all()
    genre = story.title.split(':')[0].lower()
    ending = generate_story(f"End this {genre} story based on its current progression.", genre, is_continuation=True)
    new_part = StoryPart(story_id=story_id, text=ending["story"], previous_part_id=parts[-1].id)
    db.add(new_part)
    db.commit()
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/abandon/{story_id}")
async def abandon_story(story_id: int, confirm: bool = Form(False), db: Session = Depends(get_db)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if confirm:
        db.delete(story)
        db.commit()
        return RedirectResponse(url="/generate", status_code=303)
    return templates.TemplateResponse("confirm_abandon.html", {"request": Request, "story_id": story_id})

@app.post("/save/{story_id}")
async def save_story(story_id: int, db: Session = Depends(get_db)):
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)