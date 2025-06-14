from tqdm import tqdm
import os
import re
import json
import time
import requests
import tempfile
from PIL import Image
from io import BytesIO
from google import genai

# Assume this is already configured
from google import genai

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise EnvironmentError("GOOGLE_API_KEY environment variable not set.")
client = genai.Client(api_key=api_key)

# Directory with Markdown files
MD_DIR = "./Markdowns/tds_data/"
CACHE_FILE = "image_descriptions_cache.json"

# Prompt used with Gemini
# read prompt to send to gemini from a file
prompt_file = "prompt_tds.txt"
if os.path.exists(prompt_file):
    with open(prompt_file, "r") as f:
        prompt = f.read().strip()
else:
    prompt = "Please describe the image clearly and concisely in a sentence suitable for alt text."

# Load or initialize cache
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        image_descriptions = json.load(f)
else:
    image_descriptions = {}

# Image captioning function (your provided code)
def describe_image_with_gemini(image: Image.Image):
    time.sleep(3)  # Respect rate limits
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_file:
            image.convert("RGB").save(tmp_file.name)
            uploaded_file = client.files.upload(file=tmp_file.name)

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[uploaded_file, prompt]
        )

        return response.text.strip()

    except Exception as e:
        print(f"Error describing image with Gemini: {e}")
        if "503" in str(e):
            time.sleep(10)
            return describe_image_with_gemini(image)
        return "[Image]"

# Regex to find Markdown image with .webp URL
image_pattern = re.compile(r'!\[(.*?)\]\((.*?\.(?:webp|png|jpg|jpeg))\)', re.IGNORECASE)

# Process .md files
for filename in os.listdir(MD_DIR):
    if filename.endswith(".md"):
        filepath = os.path.join(MD_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        def replace_image(match):
            alt_text, url = match.groups()

            if url in image_descriptions:
                description = image_descriptions[url]
            else:
                try:
                    response = requests.get(url, timeout=10)
                    image = Image.open(BytesIO(response.content))
                    description = describe_image_with_gemini(image)
                    image_descriptions[url] = description
                except Exception as e:
                    print(f"Error fetching or processing {url}: {e}")
                    description = "[Image]"

            return f"![{description}]({url})"

        new_content = image_pattern.sub(replace_image, content)

        filepath = os.path.join("./data/result", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"Updated: {filename}")

# Save updated cache
with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(image_descriptions, f, indent=2)
