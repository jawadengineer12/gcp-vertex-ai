"""Load and select lightweight document templates."""

import json
from pathlib import Path


class TemplateRegistry:
    def __init__(self, template_dir: Path) -> None:
        self.template_dir = template_dir
        self.templates = self._load()

    def _load(self) -> list[dict]:
        templates: list[dict] = []
        for path in sorted(self.template_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                template = json.load(handle)
            template["_source"] = str(path)
            templates.append(template)
        return templates

    def choose(self, input_fn=input, output_fn=print) -> dict | None:
        output_fn("Choose document type:\n")
        for index, template in enumerate(self.templates, start=1):
            output_fn(f"{index}. {template['name']}")
        output_fn(f"{len(self.templates) + 1}. Custom Layout")
        try:
            raw = input_fn("> ").strip()
        except EOFError:
            raw = ""
        if not raw:
            return None
        try:
            selected = int(raw)
        except ValueError:
            output_fn("Unknown selection; continuing with Custom Layout.")
            return None
        if 1 <= selected <= len(self.templates):
            return self.templates[selected - 1]
        return None
