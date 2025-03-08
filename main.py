import logging
import os
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import async_engine as engine, get_async_db
from models import Base, Story, StoryPart, ChoiceOption, Session, SessionParticipant
from story_generator import generate_story
from auth import fastapi_users, auth_backend, current_active_user, User, get_user_manager
from schemas import UserRead, UserCreate
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables on startup (consider using migrations in production)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await init_db()

# Authentication routes
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

# Registration form
@app.get("/auth/register")
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# Register endpoint with form data
@app.post("/auth/register")
async def register(
    request: Request,  # Added request parameter
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    user_manager=Depends(get_user_manager)
):
    try:
        user = await user_manager.create(
            UserCreate(username=username, email=email, password=password),
            safe=True
        )
        await user_manager.on_after_register(user)
        return RedirectResponse(url="/auth/login", status_code=303)
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return templates.TemplateResponse("register.html", {"request": request, "error": str(e)})

# Login form
@app.get("/auth/login")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Logout
@app.get("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("fastapiusersauth")
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
    db: AsyncSession = Depends(get_async_db),
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
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(current_active_user)
):
    starters = [generate_story(prompt, genre)["story"] for _ in range(3)]
    selected_story = starters[starter]
    
    story = Story(user_id=user.id, title=f"{genre.capitalize()} Tale: {prompt[:20] or 'Untitled'}...")
    db.add(story)
    await db.commit()
    await db.refresh(story)

    story_data = generate_story(prompt, genre)
    story_part = StoryPart(story_id=story.id, text=selected_story)
    db.add(story_part)
    await db.commit()
    await db.refresh(story_part)

    choice_objects = [ChoiceOption(story_part_id=story_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    await db.commit()
    for choice in choice_objects:
        await db.refresh(choice)

    return RedirectResponse(url=f"/story/{story.id}", status_code=303)

@app.get("/story/{story_id}")
async def view_story(request: Request, story_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    story = (await db.execute(db.query(Story).filter(Story.id == story_id))).scalar_one_or_none()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    parts = (await db.execute(db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id))).scalars().all()
    current_part = parts[-1] if parts else None
    choices = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.story_part_id == current_part.id))).scalars().all() if current_part else []
    story_text = []
    for i, part in enumerate(parts):
        story_text.append(part.text)
        if i < len(parts) - 1:
            next_part = parts[i + 1]
            chosen = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.story_part_id == part.id, ChoiceOption.next_part_id == next_part.id))).scalar_one_or_none()
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
async def continue_story(story_id: int, choice_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    story = (await db.execute(db.query(Story).filter(Story.id == story_id))).scalar_one_or_none()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    choice = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.id == choice_id))).scalar_one_or_none()
    if not choice or choice.story_part.story_id != story_id:
        raise HTTPException(status_code=404, detail="Choice not found")
    
    genre = story.title.split(':')[0].lower()
    story_data = generate_story(choice.text, genre, is_continuation=True)

    new_part = StoryPart(story_id=story_id, text=story_data["story"], previous_part_id=choice.story_part_id)
    db.add(new_part)
    await db.commit()
    await db.refresh(new_part)

    choice.next_part_id = new_part.id
    await db.commit()

    choice_objects = [ChoiceOption(story_part_id=new_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    await db.commit()

    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/end/{story_id}")
async def end_story(story_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    story = (await db.execute(db.query(Story).filter(Story.id == story_id))).scalar_one_or_none()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    parts = (await db.execute(db.query(StoryPart).filter(StoryPart.story_id == story_id).order_by(StoryPart.id))).scalars().all()
    genre = story.title.split(':')[0].lower()
    ending = generate_story(f"End this {genre} story based on its current progression.", genre, is_continuation=True)
    new_part = StoryPart(story_id=story_id, text=ending["story"], previous_part_id=parts[-1].id)
    db.add(new_part)
    await db.commit()
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.post("/abandon/{story_id}")
async def abandon_story(story_id: int, confirm: bool = Form(False), db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    story = (await db.execute(db.query(Story).filter(Story.id == story_id))).scalar_one_or_none()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    if confirm:
        db.delete(story)
        await db.commit()
        return RedirectResponse(url="/generate", status_code=303)
    return templates.TemplateResponse("confirm_abandon.html", {"request": request, "story_id": story_id, "user": user})

@app.post("/save/{story_id}")
async def save_story(story_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    story = (await db.execute(db.query(Story).filter(Story.id == story_id))).scalar_one_or_none()
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found or not yours")
    return RedirectResponse(url=f"/story/{story_id}", status_code=303)

@app.get("/sessions")
async def list_sessions(request: Request, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    sessions = (await db.execute(db.query(Session))).scalars().all()
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
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(current_active_user)
):
    story = Story(user_id=user.id, title=f"{genre.capitalize()} Tale: {prompt[:20] or 'Untitled'}...")
    db.add(story)
    await db.commit()
    await db.refresh(story)

    story_data = generate_story(prompt, genre)
    story_part = StoryPart(story_id=story.id, text=story_data["story"])
    db.add(story_part)
    await db.commit()
    await db.refresh(story_part)

    choice_objects = [ChoiceOption(story_part_id=story_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    await db.commit()

    session = Session(story_id=story.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    participant = SessionParticipant(session_id=session.id, user_id=user.id)
    db.add(participant)
    await db.commit()

    return RedirectResponse(url=f"/session/{session.id}", status_code=303)

@app.get("/session/{session_id}")
async def view_session(request: Request, session_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    session = (await db.execute(db.query(Session).filter(Session.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    story = session.story
    parts = (await db.execute(db.query(StoryPart).filter(StoryPart.story_id == story.id).order_by(StoryPart.id))).scalars().all()
    current_part = parts[-1]
    choices = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.story_part_id == current_part.id))).scalars().all()
    participants = (await db.execute(db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id))).scalars().all()
    is_participant = any(p.user_id == user.id for p in participants)
    story_text = []
    for i, part in enumerate(parts):
        story_text.append(part.text)
        if i < len(parts) - 1:
            next_part = parts[i + 1]
            chosen = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.story_part_id == part.id, ChoiceOption.next_part_id == next_part.id))).scalar_one_or_none()
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
async def join_session(session_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    session = (await db.execute(db.query(Session).filter(Session.id == session_id))).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if (await db.execute(db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user.id))).scalar_one_or_none():
        return RedirectResponse(url=f"/session/{session_id}", status_code=303)
    participant = SessionParticipant(session_id=session_id, user_id=user.id)
    db.add(participant)
    await db.commit()
    return RedirectResponse(url=f"/session/{session_id}", status_code=303)

@app.post("/session/{session_id}/{choice_id}")
async def continue_session(session_id: int, choice_id: int, db: AsyncSession = Depends(get_async_db), user: User = Depends(current_active_user)):
    session = (await db.execute(db.query(Session).filter(Session.id == session_id))).scalar_one_or_none()
    if not session or not (await db.execute(db.query(SessionParticipant).filter(SessionParticipant.session_id == session_id, SessionParticipant.user_id == user.id))).scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a participant")
    choice = (await db.execute(db.query(ChoiceOption).filter(ChoiceOption.id == choice_id))).scalar_one_or_none()
    if not choice or choice.story_part.story_id != session.story_id:
        raise HTTPException(status_code=404, detail="Choice not found")
    
    genre = session.story.title.split(':')[0].lower()
    story_data = generate_story(choice.text, genre, is_continuation=True)

    new_part = StoryPart(story_id=session.story_id, text=story_data["story"], previous_part_id=choice.story_part_id)
    db.add(new_part)
    await db.commit()
    await db.refresh(new_part)

    choice.next_part_id = new_part.id
    await db.commit()

    choice_objects = [ChoiceOption(story_part_id=new_part.id, text=text) for text in story_data["choices"]]
    db.add_all(choice_objects)
    await db.commit()

    return RedirectResponse(url=f"/session/{session_id}", status_code=303)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")