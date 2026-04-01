import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
    )
    return response.choices[0].message.content


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