# test_gemini.py
import os
import google.generativeai as genai

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not set!")
    exit(1)

genai.configure(api_key=api_key)

# Test with a simple prompt
model = genai.GenerativeModel('gemini-1.5-flash')
response = model.generate_content("Say 'Hello, Astrology!'")
print("✅ Gemini API working!")
print(f"Response: {response.text}")