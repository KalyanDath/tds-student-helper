from pathlib import Path
from tqdm import tqdm
import numpy as np
from semantic_text_splitter import MarkdownSplitter
import time
import os
from rate_limiter import RateLimiter
import httpx
import re

rate_limiter = RateLimiter(requests_per_minute=5, requests_per_second=2)
url = "https://aipipe.org/openai/v1/embeddings"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
}

def get_chunks(file_path: str, chunk_size: int = 15000):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    splitter = MarkdownSplitter(chunk_size)
    chunks = splitter.chunks(content)

    normalized_path = str(file_path).replace(os.sep, "/")
    if "Markdown/discourse_data" in normalized_path:
        match = re.search(r"# Thread (\d+)", content)
        topic_id = match.group(1) if match else None
        if topic_id:
            topic_url = f"https://discourse.onlinedegree.iitm.ac.in/t/{topic_id}"
            chunks = [f"{chunk}\n\n[Source]({topic_url})" for chunk in chunks]
        else:
            print(f"⚠️  Could not find thread ID in {file_path}")  
    elif "Markdown/tds_data" in normalized_path:
        filename = Path(file_path).name
        tds_url = f"https://tds.s-anand.net/#/{filename}"
        chunks = [f"{chunk}\n\n[Source]({tds_url})" for chunk in chunks]


    return chunks

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

if __name__ == "__main__":
    # files stores all markdown files in the "Markdowns" directory
    files = [*Path("Markdowns").glob("*.md"), *Path("Markdowns").rglob("*.md")]
    
    all_chunks = []
    all_embeddings = []
    total_chunks = 0
    file_chunks = {}

    # Getting chunks form all markdown files and store in file_chunks with
    # filepath as key and chunks as value
    for file_path in files:
        chunks = get_chunks(str(file_path))
        file_chunks[file_path] = chunks
        total_chunks += len(chunks)

    with tqdm(total=total_chunks, desc="Creating embeddings") as pbar:
        for file_path, chunks in file_chunks.items():
            for chunk in chunks:
                if not chunk.strip():
                    pbar.update(1)
                    continue
                try:
                    embedding =get_embedding(chunk)
                    all_chunks.append(chunk)
                    all_embeddings.append(embedding)
                    pbar.update(1)
                except Exception as e:
                    print(f"Skipping chunk from {file_path.name} due to error: {e}")
                    pbar.update(1)
                    continue
    
    # Save all the embeddings and chunks to a numpy archive file
    np.savez("embeddings_final.npz", chunks=np.array(all_chunks), embeddings=np.array(all_embeddings))
    print("✅ Saved embeddings to embeddings.npz")
    print(f"\n✅ Finished embedding generation.")
    print(f"📄 Files processed: {len(files)}")
    print(f"📦 Chunks embedded: {len(all_chunks)}")