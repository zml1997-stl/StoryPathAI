import logging
import os
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, Story, StoryPart, ChoiceOption, Session, SessionParticipant
from story_generator import generate_story
from auth import fastapi_users, auth_backend, current_active_user, User, get_user_manager  # Added get_user_manager import
from schemas import UserRead, UserCreate  # Import the schemas
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables on startup (consider using migrations in production)
Base.metadata.create_all(bind=engine)

# Authentication routes with schemas
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Add GET endpoint for registration form
@app.get("/auth/register")
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Override POST /auth/register to accept form data
@app.post("/auth/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user_manager = next(get_user_manager(db))  # Get the UserManager instance
    try:
        # Create the user using the UserManager
        user = await user_manager.create(
            UserCreate(username=username, email=email, password=password),
            safe=True  # Prevents overwriting existing users
        )
        await user_manager.on_after_register(user)
        return RedirectResponse(url="/auth/login", status_code=303)
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return templates.TemplateResponse("register.html", {"request": Request, "error": str(e)})

# Add GET endpoint for login form
@app.get("/auth/login")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Add logout endpoint
@app.get("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("fastapiusersauth")  # Clear the JWT cookie
    return response

@app.get("/")
async def root(request: Request, user: User = Depends(current_active_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/generate")
async def generate_story_form(request: Request, user: User = Depends(current_active_user)):
    genres = ["fantasy", "sci-fi", "horror", "mystery", "comedy", "action", "adventure", "romance", "drama"]
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "genres": genres,
        "selected_genre": "fantasy",
        "prompt": "",
        "user": user
    })

@app.post("/generate")
async def generate_starters(
    request: Request,
    genre: str = Form(...),
    prompt: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    genres = ["fantasy", "sci-fi", "horror", "mystery", "comedy", "action", "adventure", "romance", "drama"]
    starters = [(i, generate_story(prompt, genre)["story"]) for i in range(3)]
    return templates.TemplateResponse("generate.html", {
        "request": request,
        "genres": genres,
        "starters": starters,
        "selected_genre": genre,
        "prompt": prompt,
        "user": user
    })

@app.post("/start")
async def start_story(
    request: Request,
    starter: int = Form(...),
    genre: str = Form(...),
    prompt: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    starters = [generate_story(prompt, genre)["story"] for _ in range(3)]
    selected_story = starters[starter]
    
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
async def view_story(request: Request, story_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    parts = db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id).all()
    current_part = parts[-1] if parts else None
    choices = db.query(ChoiceOption).filter(ChoiceOption.story_part_id == current_part.id).all() if current_part else []
    story_text = []
    for i, part in enumerate(parts):
        story_text.append(part.text)
        if i < len(parts) - 1:
            next_part = parts[i + 1]
            chosen = db.query(ChoiceOption).filter(ChoiceOption.story_part_id == part.id, ChoiceOption.next_part_id == next_part.id).first()
            if chosen:
                story_text.append(f"<span class='chosen'>{chosen.text}</span>")
    return templates.TemplateResponse("story.html", {
        "request": request,
        "story": "\n\n".join(story_text),
        "choices": [(choice.text, choice.id) for choice in choices],
        "story_id": story_id,
        "user": user
    })

@app.post("/continue/{story_id}/{choice_id}")
async def continue_story(story_id: int, choice_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    choice = db.query(ChoiceOption).filter(ChoiceOption.id == choice_id).first()
    if not choice or choice.story_part.story_id != story_id:
        raise HTTPException(status_code=404, detail="Choice not found")
    
    genre = story.title.split(':')[0].lower()
    story_data = generate_story(choice.text, genre, is_continuation=True)

    new_part = StoryPart(story_id=story_id, text=story_data["story"], previous_part_id=choice.story_part_id)
    db.add(new_part)
    db.commit()
    db.refresh(new_part)

    choice.next_part_id = new_part.id
    db.commit()

    choice_objects = [ChoiceOption(story_part_id=new_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    db.commit()

    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/end/{story_id}")
async def end_story(story_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    parts = db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id).all()
    genre = story.title.split(':')[0].lower()
    ending = generate_story(f"End this {genre} story based on its current progression.", genre, is_continuation=True)
    new_part = StoryPart(story_id=story_id, text=ending["story"], previous_part_id=parts[-1].id)
    db.add(new_part)
    db.commit()
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/abandon/{story_id}")
async def abandon_story(story_id: int, confirm: bool = Form(False), db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    if confirm:
        db.delete(story)
        db.commit()
        return RedirectResponse(url="/generate", status_code=303)
    return templates.TemplateResponse("confirm_abandon.html", {"request": Request, "story_id": story_id, "user": user})

@app.post("/save/{story_id}")
async def save_story(story_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.get("/sessions")
async def list_sessions(request: Request, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    sessions = db.query(Session).all()
    return templates.TemplateResponse("sessions.html", {
        "request": request,
        "sessions": sessions,
        "user": user
    })

@app.post("/sessions/new")
async def create_session(
    request: Request,
    genre: str = Form(...),
    prompt: str = Form(default=""),
    db: Session = Depends(get_db),
    user: User = Depends(current_active_user)
):
    story = Story(user_id=user.id, title=f"{genre.capitalize()} Tale: {prompt[:20] or 'Untitled'}...")
    db.add(story)
    db.commit()
    db.refresh(story)

    story_data = generate_story(prompt, genre)
    story_part = StoryPart(story_id=story.id, text=story_data["story"])
    db.add(story_part)
    db.commit()
    db.refresh(story_part)

    choice_objects = [ChoiceOption(story_part_id=story_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    db.commit()

    session = Session(story_id=story.id)
    db.add(session)
    db.commit()
    db.refresh(session)

    participant = SessionParticipant(session_id=session.id, user_id=user.id)
    db.add(participant)
    db.commit()

    return RedirectResponse(url=f"/session/{session.id}", status_code=303)

@app.get("/session/{session_id}")
async def view_session(request: Request, session_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    story = session.story
    parts = db.query(StoryPart).filter(StoryPart.story_id == story.id).order_by(StoryPart.id).all()
    current_part = parts[-1]
    choices = db.query(ChoiceOption).filter(ChoiceOption.story_part_id == current_part.id).all()
    participants = db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id).all()
    is_participant = any(p.user_id == user.id for p in participants)
    story_text = []
    for i, part in enumerate(parts):
        story_text.append(part.text)
        if i < len(parts) - 1:
            next_part = parts[i + 1]
            chosen = db.query(ChoiceOption).filter(ChoiceOption.story_part_id == part.id, ChoiceOption.next_part_id == next_part.id).first()
            if chosen:
                story_text.append(f"<span class='chosen'>{chosen.text}</span>")
    return templates.TemplateResponse("session.html", {
        "request": request,
        "story": "\n\n".join(story_text),
        "choices": [(choice.text, choice.id) for choice in choices],
        "session_id": session_id,
        "story_id": story.id,
        "is_participant": is_participant,
        "participants": [p.user_id for p in participants],
        "user": user
    })

@app.post("/session/{session_id}/join")
async def join_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user.id).first():
        return RedirectResponse(url=f"/session/{session_id}", status_code=303)
    participant = SessionParticipant(session_id=session_id, user_id=user.id)
    db.add(participant)
    db.commit()
    return RedirectResponse(url=f"/session/{session_id}", status_code=303)

@app.post("/session/{session_id}/{choice_id}")
async def continue_session(session_id: int, choice_id: int, db: Session = Depends(get_db), user: User = Depends(current_active_user)):
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session or not db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user.id).first():
        raise HTTPException(status_code=403, detail="Not a participant")
    choice = db.query(ChoiceOption).filter(ChoiceOption.id == choice_id).first()
    if not choice or choice.story_part.story_id != session.story_id:
        raise HTTPException(status_code=404, detail="Choice not found")
    
    genre = session.story.title.split(':')[0].lower()
    story_data = generate_story(choice.text, genre, is_continuation=True)

    new_part = StoryPart(story_id=session.story_id, text=story_data["story"], previous_part_id=choice.story_part_id)
    db.add(new_part)
    db.commit()
    db.refresh(new_part)

    choice.next_part_id = new_part.id
    db.commit()

    choice_objects = [ChoiceOption(story_part_id=new_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    db.commit()

    return RedirectResponse(url=f"/session/{session_id}", status_code=303)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Heroku provides PORT, default to 8000 locally
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")