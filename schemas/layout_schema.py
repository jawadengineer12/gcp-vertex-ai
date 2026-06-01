from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict


class ProjectInfo(BaseModel):
    projectName: str
    templateID: Optional[str] = None


class DocumentSettings(BaseModel):
    pageWidth: float
    pageHeight: float


class Position(BaseModel):
    startX: float
    startY: float


class Size(BaseModel):
    width: float
    height: float


class AssetContent(BaseModel):
    imageUrl: Optional[str] = None
    textBody: Optional[str] = None


class TextStyle(BaseModel):
    fontFamily: Optional[str] = "Arial"
    fontSize: Optional[float] = 12.0
    bold: Optional[bool] = False
    italic: Optional[bool] = False
    underline: Optional[bool] = False
    color: Optional[str] = "#000000"
    autoFit: Optional[bool] = False


class Asset(BaseModel):
    assetType: Literal["Article", "Image", "Ad"]
    position: Position
    size: Size
    content: AssetContent

    # Asset Specific Properties
    columns: Optional[int] = 1
    gutterSize: Optional[float] = 0.0
    margins: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {"top": 0.0,
                                 "left": 0.0, "bottom": 0.0, "right": 0.0}
    )
    textStyle: Optional[TextStyle] = None


class Page(BaseModel):
    pageIndex: int
    assets: List[Asset]


class LayoutProject(BaseModel):
    projectInfo: ProjectInfo
    documentSettings: DocumentSettings
    pages: List[Page]
