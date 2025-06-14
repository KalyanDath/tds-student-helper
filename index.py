# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "argparse",
#     "fastapi",
#     "httpx",
#     "markdownify",
#     "numpy",
#     "semantic_text_splitter",
#     "tqdm",
#     "uvicorn",
#     "google-genai",
#     "pillow",
# ]
# ///

from io import BytesIO
import argparse
import base64
import json
import numpy as np
import os
import re
from pathlib import Path
from fastapi import FastAPI,Request
from pydantic import BaseModel
import httpx
from google import genai
from google.genai.types import GenerateContentConfig
from fastapi.middleware.cors import CORSMiddleware
import time
from typing import Optional
from rate_limiter import RateLimiter

app = FastAPI()

# Allow all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or replace with a list of specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rate_limiter = RateLimiter(requests_per_minute=5, requests_per_second=2)
url  = "https://aipipe.org/openai/v1/embeddings"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
}


def get_image_description(base64_data_url: str):
    # Parse the data URL: "data:image/png;base64,..."
    match = re.match(r"data:(image/\w+);base64,(.+)", base64_data_url)
    if not match:
        raise ValueError("Invalid base64 image format")

    mime_type, base64_data = match.groups()

    # Decode the base64 data
    image_data = base64.b64decode(base64_data)
    image = BytesIO(image_data)
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    print("Reached here")
    my_file = client.files.upload(file=image,config={
            "mime_type": mime_type
        })

    response = client.models.generate_content(
        model= "gemini-2.0-flash-lite",
        contents=[my_file,
                  "Describe the image in detail, including objects, actions, and context."]
    )

    return response.text or ""

def load_embeddings():
    data = np.load("content_embeddings.npz", allow_pickle=True)
    return data["chunks"], data["embeddings"]

def get_embedding(text: str, max_retries: int = 3) -> list[float]:
    """Get embedding for text chunk with rate limiting and retry logic"""
    
    for attempt in range(max_retries):
        try:
            # Apply rate limiting
            rate_limiter.wait_if_needed()
            
            json_data = {
                "input": text,
                "model": "text-embedding-3-small"
            }
            response = httpx.post(url=url,headers=headers,json=json_data)
            response.raise_for_status()  # Raise an error for bad responses

            json_response = response.json()

            if "data" in json_response and isinstance(json_response["data"], list):
                return json_response["data"][0]["embedding"]
            else:
                raise ValueError("Unexpected response format from embedding API")
            
        except Exception as e:
            if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                # Exponential backoff for rate limit errors
                wait_time = 2 ** attempt
                print(f"Rate limit hit, waiting {wait_time} seconds...")
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                print(f"Failed to get embedding after {max_retries} attempts: {e}")
                raise
            else:
                print(f"Attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(1)
    
    raise Exception("Max retries exceeded")
    
def generate_llm_response(question: str, context: str) -> str:
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Load system prompt from file
    with open("system_prompt.txt", "r") as f:
        system_prompt = f.read()

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=[
            system_prompt,
            f"Context: {context}",
            f"Question: {question}",
        ],
        config=GenerateContentConfig(
            max_output_tokens=512,
            top_p=0.95,
            top_k=40,
        )
    )

    return response.text or ""

with open("topic_ids_and_slugs.json", "r") as f:
    topic_slug_map = json.load(f)

def extract_links_with_text(chunks: list[str]) -> list[dict]:
    """Extract [Source](url) links and provide context snippets."""
    link_pattern = re.compile(
        r'\[(Source|View Original Thread)\]\((https?://[^\)]+)\)',
        re.IGNORECASE
    )
    links = []
    seen_urls = set()

    for chunk in chunks:
        match = link_pattern.search(chunk)
        if match:
            url = match.group(2)
            # Fix the URL if it's missing the slug (e.g., ends with /t/176077)
            corrected_url = url
            if re.match(r"https://discourse\.onlinedegree\.iitm\.ac\.in/t/\d+$", url):
                topic_id = url.rstrip("/").split("/")[-1]
                slug = topic_slug_map.get(topic_id)
                if slug:
                    corrected_url = f"https://discourse.onlinedegree.iitm.ac.in/t/{slug}/{topic_id}"

            if corrected_url in seen_urls:
                continue
            seen_urls.add(corrected_url)
            # Remove the link itself from the chunk to extract a clean text preview
            text_preview = re.sub(link_pattern, "", chunk)
            text_preview = re.sub(r"[#*_>`]", "", text_preview)  # Remove markdown characters
            text_preview = " ".join(text_preview.strip().split()[:20])

            links.append({
                "url": corrected_url,
                "text": text_preview + "..." if text_preview else "Referenced content"
            })

    return links


def answer(question: str, image: Optional[str] = None):
    loaded_chunks, loaded_embeddings = load_embeddings()
    if image:
        image_description = get_image_description(image)
        question += f" {image_description}"

    question_embedding = get_embedding(question)

    # Calculate cosine similarity
    similarities = np.dot(loaded_embeddings, question_embedding) / (
        np.linalg.norm(loaded_embeddings, axis=1) * np.linalg.norm(question_embedding)
    )

    # Get the index of the top 10 similar chunks
    top_indices = np.argsort(similarities)[-10:][::-1]

    # Get the top chunks
    top_chunks = [loaded_chunks[i] for i in top_indices]

    with open("debug_top_chunks.txt", "w", encoding="utf-8") as debug_file:
        debug_file.write("Question:\n" + question + "\n\n")
        debug_file.write("Top 10 Matching Chunks:\n")
        for i, chunk in enumerate(top_chunks, 1):
            debug_file.write(f"--- Chunk {i} ---\n{chunk.strip()}\n\n")


    # Extract links with text from the top chunks
    links = extract_links_with_text(top_chunks)

    response = generate_llm_response(question, "\n".join(top_chunks))
    return{
        "answer": response,
        "links": links,
    }


@app.post("/api")
async def get_answer(request: Request):
    try:
        data = await request.json()
        print(data)
        return answer(data.get("question",""),data.get("image"))
    except Exception as e:
        print(f"Error processing request: {e}")
        return {"error": str(e)}
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8000)