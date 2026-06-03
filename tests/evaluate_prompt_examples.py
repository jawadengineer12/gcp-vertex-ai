import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.retrieval_utils import load_library, find_top_matches


LIBRARY_PATH = Path("normalized_data/layout_prompt_library.json")
OUTPUT_PATH = Path("outputs/retrieval_eval_results.csv")
TOP_K = 3


TEST_PROMPTS = [
    "It contains one article with starting location of X=7.74225806451613 and Y=10.475 with width of 0.23274193548387 and height of 0.195 inches. textBody provides information on how this article is to be formatted and styled. Margins are set as 0 for top,left,bottom and right. Style instructions for this text body includes type of font as Helvetica Neue LT Std, font size of 9, no bold not italic, no underlan with text color code of #000000, text does not have to be autofitted. This page also contains 2 images. The first image is positioned startint at X=0 and Y=-0.125. The Size of this image has a width of 8.5 inches and height of 11.125 inches. This first image can be fount at the URL: :\"C:\\\\Users\\\\pt\\\\Downloads\\\\New folder (99)\\\\LAS 4_V8_links._Export\\\\Images\\\\Peachtree Pediatric Dentistry Magazine Ad Print.pdf. The second image has a starting location of X= 6.72 and Y= 0.17525390094338},The size of this second image has a width of 1.255 inches and height of 0.22474609905662 inches. This second image can be found at the URL: C:\\\\Users\\\\pt\\\\Downloads\\\\New folder (99)\\\\LAS 4_V8_links._Export\\\\Images\\\\Life Around Senoia_MASTHEAD BLACK.png",
    "create a full page advertisement with bleed on all sides",
    "create an image-only page using a PDF advertisement",
    "create a page with one article and two images",
    "create a page with a full page image and a small masthead logo at the top right",
    "create a simple article page with text styling font size 9 black color",
    "create a pet of the month feature page with images and article columns",
    "create a page with three columns of article text and one large image",
    "create a page with image overlay on top of another image",
    "create a full bleed cover image starting at negative x and y coordinates",
]


def format_match(match):
    if not match:
        return ""
    return f"page {match['pageIndex']} (score {match['score']})"


def main():
    library = load_library(LIBRARY_PATH)
    rows = []

    for prompt in TEST_PROMPTS:
        matches = find_top_matches(prompt, library, top_k=TOP_K)

        rows.append({
            "prompt": prompt,
            "rank_1": format_match(matches[0]) if len(matches) > 0 else "",
            "rank_2": format_match(matches[1]) if len(matches) > 1 else "",
            "rank_3": format_match(matches[2]) if len(matches) > 2 else "",
        })

    print("\nRETRIEVAL EVALUATION RESULTS\n")
    print(f"{'PROMPT':75} | {'RANK 1':20} | {'RANK 2':20} | {'RANK 3':20}")
    print("-" * 145)

    for row in rows:
        print(
            f"{row['prompt'][:75]:75} | "
            f"{row['rank_1'][:20]:20} | "
            f"{row['rank_2'][:20]:20} | "
            f"{row['rank_3'][:20]:20}"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["prompt", "rank_1", "rank_2", "rank_3"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved CSV to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()