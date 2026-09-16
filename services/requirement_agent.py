"""Deterministic pre-generation requirement extraction."""

import re
from dataclasses import dataclass, replace
from typing import Literal

from services.layout_plan_service import LayoutFeaturePlan, LayoutPlanService


FieldType = Literal["text", "image"]

# Terms that indicate the layout needs a raster/vector visual supplied by URL.
# Keep the surrounding word boundaries so short aliases such as "pic" do not
# match unrelated words such as "topic" or "picturebook".
IMAGE_TERM = (
    r"(?:photos?|photographs?|photography|images?|pictures?|pics?|snapshots?|"
    r"graphics?|illustrations?|artworks?|cover\s+art|logos?|portraits?|"
    r"headshots?|product\s+shots?|screenshots?|scans?|thumbnails?|avatars?|"
    r"icons?|banners?|posters?|drawings?|sketch(?:es)?|paintings?|collages?|"
    r"visuals?|diagrams?|infographics?|charts?|maps?|qr\s+codes?|jpe?gs?|"
    r"pngs?|gifs?|webps?|svgs?)"
)
IMAGE_PATTERN = rf"\b{IMAGE_TERM}\b"


@dataclass(frozen=True)
class RequiredField:
    name: str
    question: str
    field_type: FieldType = "text"
    required: bool = True

    @property
    def placeholder(self) -> str:
        return f"[{self.name}]"


class RequirementAgent:
    """Combines template fields with conservative custom-prompt rules."""

    CUSTOM_RULES = (
        (r"\b(?:author|writer)\b", RequiredField("author_name", "Author/writer name")),
        (
            rf"\b(?:author|writer)\b.{{0,20}}{IMAGE_PATTERN}|"
            rf"{IMAGE_PATTERN}.{{0,20}}\b(?:author|writer)\b",
            RequiredField(
                "author_photo_url", "Author/writer photo URL", "image"
            ),
        ),
        (r"\bpublisher\b", RequiredField("publisher_name", "Publisher name", required=False)),
        (r"\bpublication\b", RequiredField("publication_name", "Publication name", required=False)),
        (rf"\bhero\s+{IMAGE_TERM}\b", RequiredField("hero_image_url", "Hero image URL", "image")),
        (rf"\bcover\s+{IMAGE_TERM}\b", RequiredField("cover_image_url", "Cover image URL", "image")),
        (r"\bpublication date\b|\bissue date\b", RequiredField("publication_date", "Publication/issue date", required=False)),
    )

    def resolve(
        self,
        prompt: str,
        template: dict | None = None,
        layout_plan: LayoutFeaturePlan | None = None,
    ) -> list[RequiredField]:
        fields: list[RequiredField] = []
        if template:
            fields.extend(
                RequiredField(
                    name=item["name"],
                    question=item.get("question", item["name"].replace("_", " ").title()),
                    field_type=item.get("type", "text"),
                    required=item.get("required", True),
                )
                for item in template.get("requiredFields", [])
            )
        lowered = prompt.casefold()
        is_guest_writer = bool(re.search(r"\bguest writer\b", lowered))
        if is_guest_writer:
            fields.append(RequiredField("guest_writer_name", "Guest writer name"))
            if re.search(IMAGE_PATTERN, lowered):
                fields.append(
                    RequiredField(
                        "guest_writer_photo_url",
                        "Guest writer photo URL",
                        "image",
                    )
                )
        for pattern, field in self.CUSTOM_RULES:
            if is_guest_writer and field.name in {"author_name", "author_photo_url"}:
                continue
            if re.search(pattern, lowered):
                fields.append(replace(field, required=True))

        plan = layout_plan or LayoutPlanService().plan(prompt)
        count_match = re.search(rf"\b(two|2)\s+{IMAGE_TERM}\b", lowered)
        if count_match:
            fields.extend(
                (
                    RequiredField("image_url", "Image 1 HTTPS URL", "image"),
                    RequiredField("image_2_url", "Image 2 HTTPS URL", "image"),
                )
            )
        elif re.search(IMAGE_PATTERN, lowered) and not plan.image_spread:
            image_index = next(
                (index for index, field in enumerate(fields) if field.field_type == "image"),
                None,
            )
            if image_index is None:
                fields.append(RequiredField("image_url", "Image HTTPS URL", "image"))
            elif not fields[image_index].required:
                fields[image_index] = replace(fields[image_index], required=True)
        if plan.image_spread:
            fields.append(
                RequiredField("spread_image_url", "Spread image HTTPS URL", "image")
            )

        for name in re.findall(r"\[([a-zA-Z0-9_]+)\]", prompt):
            field_type: FieldType = "image" if name.endswith("_url") else "text"
            fields.append(
                RequiredField(name, name.replace("_", " ").title(), field_type)
            )
        return list({field.name: field for field in fields}.values())

    @staticmethod
    def extract_known_values(prompt: str, fields: list[RequiredField]) -> dict[str, str]:
        known: dict[str, str] = {}
        urls = re.findall(r"https://[^\s\]\[\)\}\>,]+", prompt)
        image_fields = [field for field in fields if field.field_type == "image"]
        if len(urls) == 1 and len(image_fields) == 1:
            known[image_fields[0].name] = urls[0]

        for field in fields:
            label = field.name.replace("_", r"[ _-]")
            match = re.search(
                rf"\b{label}\s*(?:is|:|=)\s*([^\n,;]+)", prompt, re.IGNORECASE
            )
            if match and not match.group(1).strip().startswith("["):
                known[field.name] = match.group(1).strip()
            if field.name in {"author_name", "guest_writer_name"}:
                byline = re.search(
                    r"\b(?:written by|guest writer|author|writer)\s+(?:is\s+)?"
                    r"([A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){1,3})",
                    prompt,
                )
                if byline:
                    known[field.name] = byline.group(1).strip()
        return known
