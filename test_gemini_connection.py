import os
from dotenv import load_dotenv
from google import genai

print("Starting Gemini connection test...")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY was not found in .env")
else:
    try:
        print("API key found. Sending request to Gemini...")

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents="Reply with exactly: Gemini connection successful"
        )

        print("SUCCESS:", response.text)

    except Exception as e:
        print("ERROR:", type(e).__name__)
        print(str(e)[:1000])