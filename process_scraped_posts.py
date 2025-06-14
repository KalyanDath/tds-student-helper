import requests
import json
import time
import re
import os
import io
from bs4 import BeautifulSoup
from PIL import Image
import html2text
import hashlib
from scrape_discourse_topics import load_cookie_dict, save_cookie_dict, update_forum_session_cookie
md_converter = html2text.HTML2Text()
md_converter.ignore_links = False
md_converter.ignore_images = False
md_converter.body_width = 0  # Prevent line wrapping

BASE_URL = "https://discourse.onlinedegree.iitm.ac.in"
MARKDOWN_OUTPUT_DIR = "Markdowns/discourse"

from google import genai
import tempfile

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def hash_url(url):
    return hashlib.md5(url.encode()).hexdigest()


cache_file = "caption_cache.json"
if os.path.exists(cache_file):
    with open(cache_file) as f:
        image_descriptions = json.load(f)
else:
    image_descriptions = {}

# read prompt to send to gemini from a file
prompt_file = "prompt.txt"
if os.path.exists(prompt_file):
    with open(prompt_file, "r") as f:
        prompt = f.read().strip()
else:
    prompt = "Describe this image in detail."
# Function to describe an image using Gemini

def describe_image_with_gemini(image: Image.Image):
    time.sleep(3) # Respect rate limits
    try:
        # Save image to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_file:
            image.convert("RGB").save(tmp_file.name)
            # Upload image file to Gemini
            uploaded_file = client.files.upload(file=tmp_file.name)

        # Generate caption
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[uploaded_file, prompt]
        )

        return response.text.strip() if response.text is not None else "[Image]"
    
    except Exception as e:
        print(f"Error describing image with Gemini: {e}")
        # if error due to 503, retry after 10 seconds
        if "503" in str(e):
            time.sleep(10)
            return describe_image_with_gemini(image)
        return "[Image]"

def download_image(image_url):
    response = requests.get(image_url)
    if response.status_code == 200:
        return Image.open(io.BytesIO(response.content))
    else:
        print(f"Failed to download image: {image_url}")
        return None

with open("cookie.txt", "r") as file:
    cookie = file.read()

headers = {
    "cookie": cookie
}

with open("topic_ids_and_slugs.json", 'r') as file:
    post_data = json.load(file)

def get_stream_ids(post_name, post_id):
    cookie_dict = load_cookie_dict()
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    url = f"{BASE_URL}/t/{post_name}/{post_id}.json"

    print(url)
    response = requests.get(url, headers={"cookie": cookie_header})
    if response.status_code == 200:
        data = response.json()
        update_forum_session_cookie(response, cookie_dict)
        return data['post_stream']['stream']
    else:
        print(response.json())
        print(f"Failed to retrieve data for {post_name} with ID {post_id}")
        return []

def get_posts_json(stream_ids, post_id):
    base_url = f"{BASE_URL}/t/{post_id}/posts.json?"
    post_ids_param = "&".join([f"post_ids%5B%5D={pid}" for pid in stream_ids])
    request_url = f"{base_url}{post_ids_param}&include_suggested=false"
    print(request_url)
    response = requests.get(request_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to retrieve posts JSON for stream IDs: {stream_ids}")
        print(response.json())
        return {}

def split_stream_ids(stream_ids, chunk_size=20):
    for i in range(0, len(stream_ids), chunk_size):
        yield stream_ids[i:i + chunk_size]

def extract_image_urls(post_data):
    image_urls = set()
    for post in post_data.get("post_stream", {}).get("posts", []):
        matches = re.findall(r'<img[^>]+src="([^"]+)"', post["cooked"])
        for url in matches:
            if "/uploads/" in url:
                image_urls.add(url)
    return list(image_urls)

def extract_post_details(post_data, topic_id):
    post_details = []
    image_counter = 1

    for post in post_data["post_stream"]["posts"]:
        cooked_html = post["cooked"]
        content_md = md_converter.handle(cooked_html)

        # Extract images manually for metadata
        soup = BeautifulSoup(cooked_html, "html.parser")
        images = soup.find_all("img")
        image_info = []

        for img in images:
            src = img.get("src")
            if src and "/uploads/" in src:
                image_filename = f"{topic_id}_image_{image_counter}.png"
                image_info.append({
                    "url": src,
                    "filename": image_filename
                })
                image_counter += 1

        post_details.append({
            "username": post["username"],
            "created_at": post["created_at"],
            "content": content_md.strip(),
            "post_url": f"{BASE_URL}/t/{topic_id}/{post['post_number']}",
            "images": image_info
        })

    return post_details

def save_markdown(post_details, post_id,image_descriptions):
    os.makedirs(MARKDOWN_OUTPUT_DIR, exist_ok=True)
    lines = [f"# Thread {post_id}\n"]

    for post in post_details:
        lines.append(f"---\n**{post['username']}**  \n*{post['created_at']}*\n")
        content = post["content"]

        # 1. Replace ![alt](URL) where URL contains /uploads/ → just alt text
        def process_image_markdown(match):
            alt_text, url = match.groups()
            if not url.startswith("http"):
                url = BASE_URL + url
            if "/uploads/" in url:
                return image_descriptions.get(url,"[Image]")
            else:
                return ""

        content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', process_image_markdown, content)

        # 2. Additionally, remove all empty-alt image links: ![](...)
        content = re.sub(r'!\[\]\([^)]+\)', '', content)

        lines.append(content.strip())
        lines.append(f"[View original post]({post['post_url']})\n")

    with open(f"{MARKDOWN_OUTPUT_DIR}/{post_id}.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))

# Main loop
for post_id, post_name in post_data.items():
    print(f"\nProcessing topic {post_id}: {post_name}")
    stream_ids = get_stream_ids(post_name, post_id)
    if stream_ids:
        all_image_urls = set()
        full_post_details = []

        for chunk in split_stream_ids(stream_ids):
            posts_json = get_posts_json(chunk, post_id)
            if posts_json:
                all_image_urls.update(extract_image_urls(posts_json))
                post_details = extract_post_details(posts_json, post_id)
                full_post_details.extend(post_details)

        for idx, image_url in enumerate(all_image_urls, 1):
            print(f"[{idx}/{len(all_image_urls)}] Processing image: {image_url}")
            try:
                if not image_url.startswith("http"):
                    image_url = BASE_URL + image_url

                if image_url in image_descriptions:
                    print(f"[→] Skipping cached: {image_url}")
                    save_markdown(full_post_details, post_id, image_descriptions)
                    continue

                image = download_image(image_url)
                if image:
                    caption = describe_image_with_gemini(image)
                    image_descriptions[image_url] = caption
                    print(f"[✓] Gemini caption: {caption}")
                    save_markdown(full_post_details, post_id, image_descriptions)
                    # Write progress to cache
                    with open(cache_file, "w") as f:
                        json.dump(image_descriptions, f, indent=2)
            except Exception as e:
                print(f"❌ Error generating Gemini caption for {image_url}: {e}")
                image_descriptions[image_url] = "[Image]"

                # Still write progress
                save_markdown(full_post_details, post_id, image_descriptions)

                # Graceful early exit if quota or rate limit hit
                if "quota" in str(e).lower() or "limit" in str(e).lower():
                    print("❗ Exiting early due to Gemini quota/limit. Progress saved.")
                    exit(1)
        save_markdown(full_post_details, post_id, image_descriptions)
    with open(cache_file, "w") as f:
        json.dump(image_descriptions, f, indent=2)