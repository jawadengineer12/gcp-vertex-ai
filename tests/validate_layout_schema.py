from schemas.layout_schema import LayoutProject

# Minimal test dataset mimicking your real json files
sample_data = {
    "projectInfo": {"projectName": "Day 1 Test", "templateID": ""},
    "documentSettings": {"pageWidth": 8.5, "pageHeight": 11},
    "pages": []
}

# Load the dictionary into our Pydantic schema model
project = LayoutProject(**sample_data)
print(
    f"Success! Enforced layout validation for project: '{project.projectInfo.projectName}'")
