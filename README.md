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
│   ├── discourse/             # Processed Discourse threads
│   └── tds_data/              # TDS notes from GitHub repo
|   └── discourse_data         # Discourse Data from IITM Discourse Fourm
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
    -d '{"question": "Explain histogram equalization", "image": null}'
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
  "image": null
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

---

## 📢 Credits

* TDS content: [S Anand](https://github.com/sanand0/tools-in-data-science-public)
* Discourse data: IITM Online BSc Forum
* Built by: [Kalyan Dath](https://github.com/KalyanDath)

---
