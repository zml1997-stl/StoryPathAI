import os
import requests

def generate_story(prompt: str, genre: str = "fantasy") -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"Write a short {genre} story based on this prompt: {prompt}. "
                                f"Format the story in 2-3 short paragraphs for readability. "
                                f"End the story with three distinct, relevant choice options for the next part. "
                                f"Each choice should be a full sentence describing an action, scenario, item, or decision "
                                f"that continues the narrative naturally (e.g., 'She draws her sword to fight the beast,' "
                                f"'She searches the cave for a hidden exit,' 'She offers the gem to the stranger'). "
                                f"Do not use labels like 'Choice 1' or ask questions in the story or choices."
                    }
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()
    story_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No story generated.")
    
    # Split into lines and filter out empty ones
    lines = [line.strip() for line in story_text.split("\n") if line.strip()]
    
    # Assume last 3 lines are choices; rest is story
    choices = lines[-3:] if len(lines) >= 3 else [
        "She takes a step forward.",
        "She turns back to reconsider.",
        "She calls out for help."
    ]
    story_lines = lines[:-3] if len(lines) > 3 else lines
    
    # Group story lines into paragraphs (every 2-3 sentences or respect existing breaks)
    paragraphs = []
    current_paragraph = []
    for line in story_lines:
        current_paragraph.append(line)
        # If we hit 2-3 sentences or a clear paragraph break (double newline in original), start a new paragraph
        if len(current_paragraph) >= 2 and (line.endswith('.') or line.endswith('!') or line.endswith('?')):
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph = []
    if current_paragraph:  # Add any remaining lines
        paragraphs.append(" ".join(current_paragraph))
    
    # Join paragraphs with double newlines for Jinja2 to render as <p> tags
    story_body = "\n\n".join(paragraphs) if paragraphs else "No story generated."
    
    return {"story": story_body, "choices": choices}