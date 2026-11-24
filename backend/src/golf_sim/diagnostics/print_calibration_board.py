"""Create an exact-scale, eight-sheet A4 calibration checkerboard PDF."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

MM_TO_PT = 72 / 25.4
PAGE_WIDTH_MM = 297.0
PAGE_HEIGHT_MM = 210.0
OVERLAP_MM = 10.0
TILE_STEP_X_MM = PAGE_WIDTH_MM - OVERLAP_MM
TILE_STEP_Y_MM = PAGE_HEIGHT_MM - OVERLAP_MM
PANEL_WIDTH_MM = PAGE_WIDTH_MM + TILE_STEP_X_MM
PANEL_HEIGHT_MM = PAGE_HEIGHT_MM + 3 * TILE_STEP_Y_MM
INNER_CORNERS = (4, 7)
SQUARES = (INNER_CORNERS[0] + 1, INNER_CORNERS[1] + 1)
SQUARE_SIZE_MM = 80.0
BOARD_WIDTH_MM = SQUARES[0] * SQUARE_SIZE_MM
BOARD_HEIGHT_MM = SQUARES[1] * SQUARE_SIZE_MM
BOARD_LEFT_MM = PAGE_WIDTH_MM - OVERLAP_MM - 2 * SQUARE_SIZE_MM
BOARD_TOP_MM = 50.0


def _number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _text(x_mm: float, y_top_mm: float, value: str, *, size: float = 6) -> str:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    x = x_mm * MM_TO_PT
    y = (PAGE_HEIGHT_MM - y_top_mm) * MM_TO_PT
    return f"BT /F1 {size} Tf 0 g 1 0 0 1 {_number(x)} {_number(y)} Tm ({escaped}) Tj ET\n"


def _page_content(row: int, column: int, square_mm: float) -> bytes:
    origin_x = column * TILE_STEP_X_MM
    origin_y = row * TILE_STEP_Y_MM
    board_left = PAGE_WIDTH_MM - 2 * square_mm
    board_top = PAGE_HEIGHT_MM - 2 * square_mm
    commands = ["q 1 1 1 rg 0 0 841.8898 595.2756 re f Q\n"]
    for square_row in range(SQUARES[1]):
        y1 = board_top + square_row * square_mm
        y2 = y1 + square_mm
        top, bottom = max(y1, origin_y), min(y2, origin_y + PAGE_HEIGHT_MM)
        if bottom <= top:
            continue
        for square_column in range(SQUARES[0]):
            if (square_row + square_column) % 2:
                continue
            x1 = board_left + square_column * square_mm
            x2 = x1 + square_mm
            left, right = max(x1, origin_x), min(x2, origin_x + PAGE_WIDTH_MM)
            if right <= left:
                continue
            x = (left - origin_x) * MM_TO_PT
            y = (PAGE_HEIGHT_MM - (bottom - origin_y)) * MM_TO_PT
            width, height = (right - left) * MM_TO_PT, (bottom - top) * MM_TO_PT
            commands.append(
                f"0 g {_number(x)} {_number(y)} {_number(width)} {_number(height)} re f\n"
            )

    if row == 0 and column == 0:
        commands.append(_text(8, 10, "CALIBRATION CHECKERBOARD - 4 x 7 INNER CORNERS", size=7))
        commands.append(
            _text(
                8,
                19,
                f"{square_mm:g} mm squares. Enter the measured size in the wizard.",
                size=6,
            )
        )
        commands.append(
            _text(8, 28, "Print landscape A4 at ACTUAL SIZE / 100%; disable fit-to-page.", size=6)
        )
        commands.append(
            _text(
                8,
                37,
                "Trim dashed TOP/LEFT guides; align overlaps, then tape flat to rigid backing.",
                size=5,
            )
        )
        x1, x2, y = 12 * MM_TO_PT, 112 * MM_TO_PT, (PAGE_HEIGHT_MM - 40) * MM_TO_PT
        commands.extend(
            [
                f"0 G 0.7 w {_number(x1)} {_number(y)} m {_number(x2)} {_number(y)} l S\n",
                f"0 G {_number(x1)} {_number(y-4)} m {_number(x1)} {_number(y+4)} l S\n",
                f"0 G {_number(x2)} {_number(y-4)} m {_number(x2)} {_number(y+4)} l S\n",
                _text(37, 44, "100 mm print-scale check", size=5),
            ]
        )

    if column == 1:
        x = OVERLAP_MM * MM_TO_PT
        commands.append(f"0.45 G 0.5 w [2 2] 0 d {_number(x)} 12 m {_number(x)} 584 l S [] 0 d\n")
    if row > 0:
        y = (PAGE_HEIGHT_MM - OVERLAP_MM) * MM_TO_PT
        commands.append(f"0.45 G 0.5 w [2 2] 0 d 12 {_number(y)} m 830 {_number(y)} l S [] 0 d\n")

    tile_number = row * 2 + column + 1
    label_x = 8 if column == 0 else 253
    label_y = 100 if row > 0 else 55
    commands.append(_text(label_x, label_y, f"TILE {tile_number} OF 8", size=6))
    commands.append(_text(label_x, label_y + 8, f"ROW {row + 1} / COLUMN {column + 1}", size=4.5))
    if row > 0 and column > 0:
        trim = "TRIM TOP + LEFT"
    elif row > 0:
        trim = "TRIM TOP"
    elif column > 0:
        trim = "TRIM LEFT"
    else:
        trim = "REFERENCE TILE"
    commands.append(_text(label_x, label_y + 16, trim, size=4.5))
    return "".join(commands).encode("ascii")


def build_pdf(path: Path, square_mm: float = SQUARE_SIZE_MM) -> None:
    board_width = SQUARES[0] * square_mm
    board_height = SQUARES[1] * square_mm
    board_left = PAGE_WIDTH_MM - 2 * square_mm
    board_top = PAGE_HEIGHT_MM - 2 * square_mm
    if (
        square_mm <= 0
        or board_left < 0
        or board_left + board_width > PANEL_WIDTH_MM
        or board_top < 0
        or board_top + board_height > PANEL_HEIGHT_MM
    ):
        raise ValueError("checkerboard does not fit the eight-sheet tiled layout")
    objects: list[bytes | None] = [None, None, None]
    page_ids = []
    for row in range(4):
        for column in range(2):
            stream = _page_content(row, column, square_mm)
            content_id = len(objects) + 1
            objects.append(
                f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream"
            )
            page_id = len(objects) + 1
            objects.append(
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                    f"{_number(PAGE_WIDTH_MM * MM_TO_PT)} {_number(PAGE_HEIGHT_MM * MM_TO_PT)}] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
                ).encode("ascii")
            )
            page_ids.append(page_id)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page} 0 R' for page in page_ids)}] /Count 8 >>"
    ).encode("ascii")
    objects[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as pdf:
        pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for identity, body in enumerate(objects, start=1):
            offsets.append(pdf.tell())
            pdf.write(f"{identity} 0 obj\n".encode("ascii"))
            pdf.write(body)
            pdf.write(b"\nendobj\n")
        xref = pdf.tell()
        pdf.write(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
        pdf.write(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.write(
            (
                f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n" f"startxref\n{xref}\n%%EOF\n"
            ).encode("ascii")
        )


def build_rigid_board_pdf(
    path: Path,
    square_mm: float = 78.4,
    border_mm: float = 20.0,
    bleed_mm: float = 3.0,
    panel_size_mm: tuple[float, float] | None = None,
) -> None:
    """Create a single-page, measured-scale checkerboard with an embedded TTF font."""
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas

    if (
        not all(math.isfinite(value) for value in (square_mm, border_mm, bleed_mm))
        or square_mm <= 0
        or border_mm < 15
        or bleed_mm < 0
    ):
        raise ValueError(
            "square size must be positive, border at least 15 mm, and bleed nonnegative"
        )

    board_width = SQUARES[0] * square_mm
    board_height = SQUARES[1] * square_mm
    if panel_size_mm is None:
        panel_width = board_width + 2 * border_mm
        panel_height = board_height + 2 * border_mm
    else:
        panel_width, panel_height = panel_size_mm
        if (
            not all(math.isfinite(value) for value in panel_size_mm)
            or panel_width - board_width < 2 * 15
            or panel_height - board_height < 2 * 15
        ):
            raise ValueError("panel must leave at least a 15 mm border around the checkerboard")

    border_x = (panel_width - board_width) / 2
    border_y = (panel_height - board_height) / 2
    page_width = panel_width + 2 * bleed_mm
    page_height = panel_height + 2 * bleed_mm
    pattern_left = bleed_mm + border_x
    pattern_top = bleed_mm + border_y

    font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    if not font_path.is_file():
        raise RuntimeError("ReportLab's bundled Vera font is unavailable for embedded PDF labels")
    font_name = "CalibrationVera"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(
        str(path),
        pagesize=(page_width * MM_TO_PT, page_height * MM_TO_PT),
        pageCompression=1,
        pdfVersion=(1, 4),
        initialFontName=font_name,
    )
    pdf.setTitle("Measured 78.4 mm calibration checkerboard")
    pdf.setAuthor("Golf Swing Analyzer calibration diagnostics")
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(0, 0, page_width * MM_TO_PT, page_height * MM_TO_PT, fill=1, stroke=0)
    pdf.setFillColorRGB(0, 0, 0)
    for row in range(SQUARES[1]):
        for column in range(SQUARES[0]):
            if (row + column) % 2:
                continue
            x = pattern_left + column * square_mm
            y = page_height - (pattern_top + (row + 1) * square_mm)
            pdf.rect(
                x * MM_TO_PT,
                y * MM_TO_PT,
                square_mm * MM_TO_PT,
                square_mm * MM_TO_PT,
                fill=1,
                stroke=0,
            )

    def draw_text(x_mm: float, y_top_mm: float, value: str, size: float) -> None:
        pdf.setFont(font_name, size)
        pdf.drawString(x_mm * MM_TO_PT, (page_height - y_top_mm) * MM_TO_PT, value)

    draw_text(bleed_mm + 7, bleed_mm + 8, "TARGET --->", 7)
    draw_text(bleed_mm + 7, bleed_mm + 17, f"5 x 8 squares; {square_mm:g} mm each", 6)
    draw_text(
        bleed_mm + 112,
        bleed_mm + 8,
        "FIRST INNER CORNER: one square in from top-left grid corner",
        5,
    )
    draw_text(bleed_mm + border_x + 7, bleed_mm + panel_height - 7, "GOLFER SIDE", 6)

    first_row_y = pattern_top + square_mm
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.6)
    pdf.line(
        (bleed_mm + 2) * MM_TO_PT,
        (page_height - first_row_y) * MM_TO_PT,
        pattern_left * MM_TO_PT,
        (page_height - first_row_y) * MM_TO_PT,
    )
    scale_length = 100.0
    scale_x = bleed_mm + (panel_width - scale_length) / 2
    scale_y = bleed_mm + panel_height - 12
    scale_bottom = page_height - scale_y
    scale_top = page_height - (scale_y - 3)
    pdf.setLineWidth(0.7)
    pdf.line(
        scale_x * MM_TO_PT,
        scale_bottom * MM_TO_PT,
        (scale_x + scale_length) * MM_TO_PT,
        scale_bottom * MM_TO_PT,
    )
    pdf.line(
        scale_x * MM_TO_PT,
        (scale_bottom - 3) * MM_TO_PT,
        scale_x * MM_TO_PT,
        scale_top * MM_TO_PT,
    )
    pdf.line(
        (scale_x + scale_length) * MM_TO_PT,
        (scale_bottom - 3) * MM_TO_PT,
        (scale_x + scale_length) * MM_TO_PT,
        scale_top * MM_TO_PT,
    )
    draw_text(scale_x, scale_y - 5, "100 mm scale check", 5)
    pdf.showPage()
    pdf.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--square-mm", type=float, default=SQUARE_SIZE_MM)
    parser.add_argument(
        "--rigid-panel",
        action="store_true",
        help="create a single-panel print file with measured origin, target and golfer-side marks",
    )
    parser.add_argument(
        "--panel-size-mm",
        type=float,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        help="exact rigid-panel trim dimensions; the checkerboard remains at measured scale",
    )
    args = parser.parse_args()
    if args.rigid_panel:
        panel_size = tuple(args.panel_size_mm) if args.panel_size_mm else None
        build_rigid_board_pdf(args.output, args.square_mm, panel_size_mm=panel_size)
        panel_width = panel_size[0] if panel_size else SQUARES[0] * args.square_mm + 40
        panel_height = panel_size[1] if panel_size else SQUARES[1] * args.square_mm + 40
        print(
            f"Created {args.output}: {panel_width:g}x{panel_height:g} mm trim size, "
            f"4x7 inner corners, {args.square_mm:g} mm squares. Print at 100% actual size."
        )
    else:
        build_pdf(args.output, args.square_mm)
        print(
            f"Created {args.output}: 8 A4 landscape pages, 4x7 inner corners, "
            f"{args.square_mm:g} mm squares. Print at 100% actual size."
        )


if __name__ == "__main__":
    main()
