# 🧠 TDS Student Helper – Virtual TA for IIT Madras Online BSc

A FastAPI-powered AI assistant that answers student questions from the IIT Madras Online BSc in Data Science. It uses semantic search over scraped course materials and Discourse forum posts, with optional image understanding via Gemini Vision API.

---

## ✨ Features

* ✅ Semantic search using OpenAI embeddings (`text-embedding-3-small`)
* 🧾 Gemini Vision integration for images in questions
* 🗂️ Scrapes relevant Discourse posts and TDS content
* 🧠 Uses Gemini models (`gemini-2.0-flash-lite`) to answer questions
* 📆 Returns relevant context chunks and preview URLs

---

## 📚 TDS Notes Source

> 📌 The TDS content used in this project is sourced from:
>
> [https://github.com/sanand0/tools-in-data-science-public](https://github.com/sanand0/tools-in-data-science-public)
>
> This includes markdown notes and visuals from the *Tools in Data Science* course by [S Anand](https://github.com/sanand0).

---

## 📁 Project Structure

```
tds-student-helper/
├── README.md
├── LICENSE
├── cookie.txt
├── vercel.json
├── system_prompt.txt
├── requirements.txt
├── prompt_discourse.txt
├── prompt_tds.txt
├── content_embeddings.npz
├── Markdowns/
│   ├── discourse_data/             # Processed Discourse threads
│   └── tds_data/              # TDS notes from GitHub repo
├── index.py                   # FastAPI backend
├── create_embeddings.py       # Create vector embeddings
├── scrape_discourse_topics.py # Scrape post slugs from Discourse
├── generate_image_captions.py # Describe images using Gemini
├── process_scraped_posts.py   # Convert Discourse threads to Markdown
├── remove_image_links.py      # Clean up image markdown
├── rate_limiter.py            # Helper to manage API rate limits
```

---

## ⚙️ Installation

```bash
git clone https://github.com/KalyanDath/tds-student-helper.git
cd tds-student-helper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export GOOGLE_API_KEY="your-google-api-key"
```

---

## 📊 Usage Steps

### 1. Scrape Discourse Topic IDs

```bash
python scrape_discourse_topics.py
```

Generates `topic_ids_and_slugs.json`

### 2. Process Topics into Markdown

```bash
python process_scraped_posts.py
```

Outputs files in `Markdowns/discourse/`

### 3. Add TDS Notes

```bash
git clone https://github.com/sanand0/tools-in-data-science-public tds-notes
cp -r tds-notes/Markdowns/* Markdowns/tds/
```

### 4. Replace Images with Captions for TDS Content

```bash
python generate_image_captions.py
```

### 5. Create Embeddings

```bash
python create_embeddings.py
```

Creates `embeddings_final.npz` with chunked content + vectors

### 6. Run the FastAPI Server

```bash
uvicorn index:app --reload
```

Test API via:

```bash
curl -X POST http://localhost:8000/api -H "Content-Type: application/json" \
    -d '{"question": "Explain histogram equalization"}'
```

---

## 🚀 Vercel Deployment

### 1. Install Vercel CLI

```bash
npm i -g vercel
```

### 2. Deploy

```bash
vercel --prod
```

### 3. Add Environment Variables in Vercel Dashboard

Go to your deployed project in [Vercel](https://vercel.com/dashboard), click **Settings → Environment Variables** and add:

```
OPENAI_API_KEY = your-openai-key
GOOGLE_API_KEY = your-gemini-api-key
```
 or  set directly from cli
```bash
vercel env add GOOGLE_API_KEY
vercel env add OPENAI_API_KEY
```

Then redeploy the project.

---

## 🖋️ Example Request

```json
POST /api
{
  "question": "What is the formula for entropy?",
  "image": "Base64 Image Content Here"
}
```

Response:

```json
{
  "answer": "Entropy is calculated as ...",
  "links": [
    {
      "url": "https://discourse.onlinedegree.iitm.ac.in/t/...",
      "text": "Entropy measures randomness ..."
    }
  ]
}
```
## 🛠️ Design & Highlights

### 🧠 Semantic QA Pipeline (FastAPI + Gemini + Embeddings)

The backend (`index.py`) uses the following pipeline to answer student queries:

1. **Text+Image Input Support**  
   Accepts a question and optionally a base64-encoded image (e.g., a screenshot of a Discourse post or course slide).

2. **Gemini Vision Integration**  
   If an image is provided, it's passed to Google Gemini (`gemini-2.0-flash-lite`) for detailed captioning (describing objects, text, charts, etc.), which is then appended to the question before semantic search.

3. **Embeddings + Semantic Search**  
   - Loads `text-embedding-3-small` vectors (from `embeddings_final.npz`) generated from TDS course content and Discourse threads.
   - Computes cosine similarity between the user’s query and all stored chunks to retrieve the top 10 most relevant passages.

4. **LLM-Powered Answer Generation**  
   Uses Gemini to synthesize a clear and helpful answer using the top chunks as context, controlled via a prompt in `system_prompt.txt`.

5. **Smart Link Extraction**  
   - Every chunk includes a `[Source](url)` or `[View Original Thread](url)` link.
   - If a Discourse URL is missing a slug (`/t/176077`), it auto-corrects it using the cached `topic_ids_and_slugs.json`, transforming it into:  
     `https://discourse.onlinedegree.iitm.ac.in/t/{slug}/176077`

6. **Returns Clean JSON Output**  
   ```json
   {
     "answer": "Here’s what entropy means...",
     "links": [
       { "url": "...", "text": "entropy measures the uncertainty..." }
     ]
   }
   ```

7. **Extras**  
   - `debug_top_chunks.txt` logs the actual context used for each answer (for transparent debugging).
   - `rate_limiter.py` applies safe exponential backoff and throttling for embedding/API limits.

---

### 🌐 Discourse Scraper (`scrape_discourse_post.py`)

To enable clickable URLs in answers and search-friendly URLs:

- **Discourse API Querying**  
  Scrapes pages of Discourse posts using a rich query:  
  `#courses:tds-kb before:2025-04-14 after:2025-01-01 order:latest`

- **Session Management**  
  Reads and updates the `_forum_session` from `Set-Cookie` headers to keep scraping even if the session expires.

- **Output: `topic_ids_and_slugs.json`**  
  A dictionary that maps `topic_id` to its Discourse slug (like `"164277": "project-1-llm-based-automation-agent-discussion-thread-tds-jan-2025"`).

- **Used Later To Fix Incomplete URLs**  
  Ensures that thread links shown in answers are always in the correct format:
  ```
  https://discourse.onlinedegree.iitm.ac.in/t/{slug}/{topic_id}
  ```

---

## 📦 Chunking Strategy

The app implements a robust strategy to chunk Markdown files (from TDS notes and Discourse posts) for semantic search:

### ✅ Highlights

- **🧠 Semantic Markdown Splitting**  
  Uses [`semantic_text_splitter`](https://pypi.org/project/semantic-text-splitter/) to split Markdown into coherent chunks of ~10,000 characters, preserving context better than naive splitting.

- **🔗 Source URL Included in Every Chunk**  
  Each chunk ends with a `[Source](...)` link that points to:
  - The **original Discourse thread** (with topic slug and ID)
  - The **TDS GitHub notebook** based on file name

- **🔄 Discourse Slug Fixing Logic**  
  Some Discourse links may only contain the thread ID (e.g., `/t/163247`). These are corrected to full URLs using a `topic_ids_and_slugs.json` map:
  ```
  https://discourse.onlinedegree.iitm.ac.in/t/163247
     ⬇️
  https://discourse.onlinedegree.iitm.ac.in/t/ga3-large-language-models-discussion-thread-tds-jan-2025/163247
  ```

- **📄 Chunk-Level Metadata**  
  Each chunk stores its origin, allowing relevant preview links in the final API response.

- **📈 Vector Embedding with OpenAI**  
  - Chunks are vectorized using the `text-embedding-3-small` model from OpenAI.
  - Embedding requests are rate-limited via a `RateLimiter` helper and retried on failure.

- **💾 Output Format**  
  Chunks and embeddings are stored as NumPy arrays in `content_embeddings.npz`:
  ```python
  np.savez("content_embeddings.npz", chunks=[...], embeddings=[...])
  ```
---

## 📢 Credits

* TDS content: [S Anand](https://github.com/sanand0/tools-in-data-science-public)
* Discourse data: IITM Online BSc Forum
* Built by: [Kalyan Dath](https://github.com/KalyanDath)

---
