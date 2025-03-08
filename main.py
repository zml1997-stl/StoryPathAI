import logging
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from .database import engine
from .models import Base

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
    raise  # Still raise to see the error in logs

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "message": "Welcome to StoryPath!"})