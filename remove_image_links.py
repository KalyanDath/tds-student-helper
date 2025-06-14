import re
from pathlib import Path
from tqdm import tqdm

# Path to your markdown folder
MD_DIR = Path("./Markdowns/tds_data")

# Regex pattern to match image markdown using .webp/.jpg/.jpeg/.png
image_substitution_pattern = re.compile(
    r"\[\!\[(.*?)\]\(https?:\/\/.*?\.(?:webp|jpg|jpeg|png)\)\]\((.*?)\)",
    re.IGNORECASE
)

# Get all markdown files
md_files = list(MD_DIR.glob("*.md"))

for md_file in tqdm(md_files, desc="Replacing image links with alt text only"):
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace image markdown with just alt text wrapped in link
    new_content = image_substitution_pattern.sub(r"[!\[\1](\2)", content)

    if new_content != content:
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(new_content)

print("✅ Image links replaced with alt text pointing to video.")
