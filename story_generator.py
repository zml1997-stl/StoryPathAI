import os
import httpx

async def generate_story(prompt: str = "", genre: str = "fantasy", is_continuation: bool = False) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    base_prompt = f"Write a short {genre} story" + (f" based on this prompt: {prompt}" if prompt else "") + "."
    if is_continuation:
        instruction = f" Continue the {genre} story from the previous part ending with '{prompt}'. Do not repeat the previous part verbatim."
    else:
        instruction = " Format the story in 2-3 short paragraphs for readability."
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{base_prompt}{instruction} End the story with three distinct, relevant choice options for the next part. "
                                f"Each choice should be a full sentence describing an action, scenario, item, or decision "
                                f"that continues the narrative naturally (e.g., 'She draws her sword to fight the beast,' "
                                f"'She searches the cave for a hidden exit,' 'She offers the gem to the stranger'). "
                                f"Do not use labels like 'Choice 1' or ask questions in the story or choices."
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, params=params, json=data)
        response.raise_for_status()
        result = response.json()
        story_text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No story generated.")
    
    lines = [line.strip() for line in story_text.split("\n") if line.strip()]
    choices = lines[-3:] if len(lines) >= 3 else [
        "She takes a step forward.",
        "She turns back to reconsider.",
        "She calls out for help."
    ]
    story_body = "\n\n".join(lines[:-3]) if len(lines) > 3 else story_text
    
    return {"story": story_body, "choices": choices}