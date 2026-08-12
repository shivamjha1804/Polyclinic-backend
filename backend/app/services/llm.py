from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def complete_json(system: str, user_message: str, model: str, max_tokens: int = 2000) -> str:
    response = client.chat.completions.create(
        model = model,
        max_tokens = max_tokens,
        response_format = {"type" : "json_object"},
        messages = [
            {"role" : "system", "content" : system},
            {"role" : "user", "content" : user_message}
        ],
    )
    return response.choices[0].message.content


def complete_text(system: str, user_message: str, model: str, max_tokens: int = 500) -> str:
    respone = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": system
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )
    return respone.choices[0].message.content

