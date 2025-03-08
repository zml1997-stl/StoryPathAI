from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database import engine, get_db
from .models import Base, User
from .story_generator import generate_story

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize database tables
Base.metadata.create_all(bind=engine)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message": "Welcome to StoryPath!"})

@app.post("/api/users")
async def create_user(username: str = Form(...), db: Session = Depends(get_db)):
    db_user = User(username=username)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
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
        return templates.TemplateResponse("generate.html", {
            "request": request,
            "error": str(e)
        })