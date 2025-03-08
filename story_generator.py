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
                    {"text": f"Write a short {genre} story based on this prompt: {prompt}. End with 3 distinct choice options for the next part."}
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, params=params, json=data)
    response.raise_for_status()
    result = response.json()
    story_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No story generated.")
    
    # Extract choices (assuming they’re at the end of the text)
    lines = story_text.split("\n")
    story_body = "\n".join(lines[:-3]) if len(lines) > 3 else story_text
    choices = lines[-3:] if len(lines) >= 3 else ["Choice 1", "Choice 2", "Choice 3"]
    
    return {"story": story_body, "choices": choices}