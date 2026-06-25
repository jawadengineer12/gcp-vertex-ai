import pandas as pd
import json

# Paths to your files
excel_file = "raw_data/trainingData_Local.xlsx"  # Path to your Excel
json_library_file = "normalized_data/layout_prompt_library.json"  # Your current JSON library
output_file = "normalized_data/layout_prompt_library_updated.json"

# Load existing JSON library
with open(json_library_file, "r") as f:
    library = json.load(f)

# Load Excel file
df = pd.read_excel(excel_file)

# Iterate through Excel rows
for idx, row in df.iterrows():
    expected_json_str = row["Expected JSON Object (Output)"]

    try:
        expected_json = json.loads(expected_json_str)
    except Exception:
        # Skip row if Expected JSON column is not valid JSON
        continue

    # Skip row if assets are empty
    if expected_json.get("assets") == []:
        continue

    # Create a new entry in the same format as your JSON library
    new_entry = {
        "pageIndex": int(row["Page Number"]),
        "natural_language_intent": row["Generated Prompt (Input)"],
        "expected_layout_json": expected_json
    }

    library.append(new_entry)

# Save the updated library
with open(output_file, "w") as f:
    json.dump(library, f, indent=2)

print(f"Updated library saved to {output_file}")
