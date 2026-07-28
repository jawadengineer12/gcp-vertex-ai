"""Approved InDesign font loading."""

import csv
from pathlib import Path


class FontConfigurationError(RuntimeError):
    pass


def load_allowed_fonts(path: Path) -> list[str]:
    """Load literal ``\\t`` InDesign names from column C of Font List.csv."""
    if not path.is_file():
        raise FontConfigurationError(
            f"Font List.csv was not found at {path}. Set FONT_LIST_PATH to the file."
        )

    fonts: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header or len(header) < 3:
            raise FontConfigurationError("Font List.csv must contain at least three columns")
        for row_number, row in enumerate(reader, start=2):
            if len(row) < 3 or not row[2].strip():
                continue
            value = row[2].strip()
            if "\t" in value or "\\t" not in value:
                raise FontConfigurationError(
                    f"Invalid exact InDesign font name on CSV row {row_number}: {value!r}"
                )
            fonts.append(value)

    unique_fonts = list(dict.fromkeys(fonts))
    if not unique_fonts:
        raise FontConfigurationError("Font List.csv column C contains no font names")
    return unique_fonts
