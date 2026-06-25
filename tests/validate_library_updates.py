import json

# Paths
original_json_file = "normalized_data/layout_prompt_library.json"  # original library
updated_json_file = "normalized_data/layout_prompt_library_updated.json"  # after appending Excel

# Load files
with open(original_json_file, "r") as f:
    original_library = json.load(f)

with open(updated_json_file, "r") as f:
    updated_library = json.load(f)

# Compare lengths
original_len = len(original_library)
updated_len = len(updated_library)

print(f"Original library entries: {original_len}")
print(f"Updated library entries: {updated_len}")

if updated_len > original_len:
    print(f"New entries appended: {updated_len - original_len}")
else:
    print("No new entries were appended.")

# Optional: inspect last few entries to see actual appended records
print("\nLast 2 entries in the updated library:")
for entry in updated_library[-2:]:
    print(json.dumps(entry, indent=2))
