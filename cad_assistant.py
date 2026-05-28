import os
from dotenv import load_dotenv
from backend.ai.provider import AIProviderUnavailable, get_ai_provider

load_dotenv()

SYSTEM_PROMPT = """
You are an AI CAD assistant.

Convert the user's request into JSON.

Tasks:
- rectangle
- slab_with_footing
- beam_diagram
- text_note

Rules:
- Default origin = [0,0]
- Always include assumptions
"""

def build_plan(user_text):
    try:
        response = get_ai_provider().generate_text(
            model=os.getenv("CIVORA_CAD_ASSISTANT_MODEL", os.getenv("CIVORA_CHAT_MODEL", "gpt-5")),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        return response.output_text
    except AIProviderUnavailable as exc:
        return (
            '{"error":"language_provider_unavailable",'
            f'"message":"{str(exc).replace(chr(34), chr(39))}",'
            '"fallback":"Use structured UI inputs or enable CIVORA_AI_PROVIDER=openai/local."}'
        )


def main():
    print("AI CAD Assistant Running...\n")

    while True:
        user = input("Type something: ")

        if user.lower() == "quit":
            break

        try:
            result = build_plan(user)
            print("\nAI Output:\n")
            print(result)
            print("\n-------------------\n")

        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    main()
