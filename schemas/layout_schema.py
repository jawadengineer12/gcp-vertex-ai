"""Strict converter-facing schema for a complete layout project."""

from typing import Annotated, Literal, Union
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ProjectInfo(StrictModel):
    projectName: NonEmptyString


class DocumentSettings(StrictModel):
    pageWidth: float = Field(gt=0)
    pageHeight: float = Field(gt=0)


class Position(StrictModel):
    startX: float
    startY: float


class Size(StrictModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Margins(StrictModel):
    top: float = Field(ge=0)
    left: float = Field(ge=0)
    bottom: float = Field(ge=0)
    right: float = Field(ge=0)


class TextStyle(StrictModel):
    fontFamily: NonEmptyString
    fontSize: float = Field(gt=0)
    bold: bool
    italic: bool
    underline: bool
    color: NonEmptyString
    autoFit: bool

    @field_validator("fontFamily")
    @classmethod
    def require_literal_font_separator(cls, value: str) -> str:
        if "\t" in value:
            raise ValueError("fontFamily must use literal \\t, not an actual tab")
        if "\\t" not in value:
            raise ValueError(
                "fontFamily must be an exact InDesign name containing literal \\t"
            )
        return value


class ArticleContent(StrictModel):
    textBody: str
    articleDocumentLink: NonEmptyString | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class ImageContent(StrictModel):
    imageUrl: NonEmptyString

    @field_validator("imageUrl")
    @classmethod
    def validate_image_reference(cls, value: str) -> str:
        parsed = urlparse(value)
        is_https = parsed.scheme == "https" and bool(parsed.netloc)
        is_placeholder = (
            value.startswith("[")
            and value.endswith("_url]")
            and value[1:-1].replace("_", "").isalnum()
        )
        if not (is_https or is_placeholder):
            raise ValueError(
                "imageUrl must be an https:// URL or a [field_name_url] placeholder"
            )
        return value


class ArticleAsset(StrictModel):
    assetType: Literal["Article"]
    expand: bool | None = Field(default=None, exclude_if=lambda value: value is None)
    position: Position
    size: Size
    content: ArticleContent
    columns: int = Field(ge=1)
    gutterSize: float = Field(ge=0)
    margins: Margins
    textStyle: TextStyle


class ImageAsset(StrictModel):
    assetType: Literal["Image"]
    position: Position
    size: Size
    content: ImageContent


class AdAsset(StrictModel):
    assetType: Literal["Ad"]
    position: Position
    size: Size
    content: ImageContent


Asset = Annotated[
    Union[ArticleAsset, ImageAsset, AdAsset], Field(discriminator="assetType")
]


class Page(StrictModel):
    pageIndex: int = Field(ge=1)
    assets: list[Asset]


class LayoutProject(StrictModel):
    pageIndex: Literal[0]
    documentSettings: DocumentSettings
    projectInfo: ProjectInfo
    pages: list[Page] = Field(min_length=1)

    @model_validator(mode="after")
    def require_sequential_page_indexes(self) -> "LayoutProject":
        actual = [page.pageIndex for page in self.pages]
        expected = list(range(1, len(self.pages) + 1))
        if actual != expected:
            raise ValueError(
                f"pages must use sequential pageIndex values starting at 1; got {actual}"
            )
        return self
