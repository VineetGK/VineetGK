#!/usr/bin/env python3
"""
ascii_svg.py
------------
Turns an image into an animated "typing" ASCII-art SVG using Pillow only.

USAGE
    python3 ascii_svg.py
        Looks inside  ~/Downloads/ascii/  for an image, auto-picks the most
        recently modified one, and writes an .svg with the same base name
        right next to it.

    python3 ascii_svg.py /path/to/image.png
        Optional: process a specific image instead of auto-detecting.

The output SVG:
    - dark background, light monospace characters (~100 chars wide)
    - bright pixels map toward blank space, dark pixels map to dense glyphs
    - types itself in line by line (left -> right) with a block cursor
      sweeping across each row
    - built with pure SMIL (<animate>/<set>), so it animates in browsers,
      image viewers that support SMIL, and GitHub README previews
    - freezes in place once the last line finishes
"""

import os
import sys
import glob

from PIL import Image, ImageOps

# --------------------------------------------------------------------------
# Tweakable settings
# --------------------------------------------------------------------------
FOLDER_NAME = os.path.join(os.path.expanduser("~"), "Downloads", "ascii")

COLS = 100                 # target width in characters
FONT_SIZE = 14              # px
CHAR_W = round(FONT_SIZE * 0.6, 2)    # approx width of one monospace glyph
LINE_H = round(FONT_SIZE * 1.2, 2)    # line height (row pitch)
PADDING = 12

ROW_DURATION = 0.35         # seconds it takes each line to type across

BG_COLOR = "#0d1117"        # dark background (GitHub-dark friendly)
FG_COLOR = "#e6edf3"        # light monospace text
CURSOR_COLOR = "#39d353"    # block cursor accent

# Density ramp: index 0 = darkest pixel (densest glyph), last = brightest
# pixel (blank space) so bright areas wash out clean.
RAMP = "@%#*+=-:. "

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff")


# --------------------------------------------------------------------------
# Image -> ASCII rows
# --------------------------------------------------------------------------
def find_input_image(explicit_path=None):
    if explicit_path:
        if not os.path.isfile(explicit_path):
            sys.exit(f"File not found: {explicit_path}")
        return explicit_path

    os.makedirs(FOLDER_NAME, exist_ok=True)

    candidates = []
    for entry in os.listdir(FOLDER_NAME):
        full = os.path.join(FOLDER_NAME, entry)
        if not os.path.isfile(full):
            continue
        if entry.lower().endswith(IMAGE_EXTS):
            candidates.append(full)

    if not candidates:
        sys.exit(
            f"No image found in {FOLDER_NAME}\n"
            f"Drop a .png/.jpg/.jpeg/.bmp/.gif/.webp/.tiff file in there and "
            f"run this script again with no arguments."
        )

    # most recently modified wins
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def image_to_ascii_rows(img_path, cols=COLS):
    img = Image.open(img_path).convert("L")

    try:
        img = ImageOps.autocontrast(img, cutoff=1)
    except Exception:
        pass  # flat/solid images can upset autocontrast; fall back silently

    w, h = img.size
    if w == 0 or h == 0:
        sys.exit("Image has zero width or height.")

    # character cells are taller than they are wide, so correct the
    # row count using the cell's width/height ratio
    char_aspect = CHAR_W / LINE_H
    rows = max(1, round(cols * (h / w) * char_aspect))

    small = img.resize((cols, rows), Image.LANCZOS)
    pixels = small.load()

    n = len(RAMP) - 1
    ascii_rows = []
    for y in range(rows):
        line = []
        for x in range(cols):
            brightness = pixels[x, y]
            idx = int(brightness / 255 * n)
            line.append(RAMP[idx])
        ascii_rows.append("".join(line))

    return ascii_rows, cols, rows


# --------------------------------------------------------------------------
# ASCII rows -> animated SVG
# --------------------------------------------------------------------------
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(ascii_rows, cols, rows):
    full_text_w = round(cols * CHAR_W, 2)
    width = round(full_text_w + 2 * PADDING, 2)
    height = round(rows * LINE_H + 2 * PADDING, 2)

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, \'Courier New\', monospace" '
        f'font-size="{FONT_SIZE}">'
    )
    parts.append(f'<rect width="100%" height="100%" fill="{BG_COLOR}"/>')

    # --- clip paths (one per row) that reveal text left -> right ---
    parts.append("<defs>")
    for i in range(rows):
        row_y = round(PADDING + LINE_H * i, 2)
        t = round(i * ROW_DURATION, 3)
        parts.append(
            f'<clipPath id="clip{i}">'
            f'<rect x="{PADDING}" y="{row_y}" width="0" height="{LINE_H}">'
            f'<animate attributeName="width" from="0" to="{full_text_w}" '
            f'begin="{t}s" dur="{ROW_DURATION}s" fill="freeze"/>'
            f"</rect></clipPath>"
        )
    parts.append("</defs>")

    # --- text rows ---
    for i, row_text in enumerate(ascii_rows):
        baseline_y = round(PADDING + LINE_H * (i + 0.8), 2)
        parts.append(
            f'<text x="{PADDING}" y="{baseline_y}" fill="{FG_COLOR}" '
            f'xml:space="preserve" textLength="{full_text_w}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#clip{i})">{esc(row_text)}</text>'
        )

    # --- block cursor that sweeps each row, then jumps to the next ---
    cursor_w = round(CHAR_W * 0.9, 2)
    cursor_h = round(LINE_H * 0.85, 2)
    first_row_y = round(PADDING + LINE_H * 0 + (LINE_H - cursor_h) / 2, 2)

    parts.append(
        f'<rect x="{PADDING}" y="{first_row_y}" width="{cursor_w}" height="{cursor_h}" '
        f'fill="{CURSOR_COLOR}" opacity="0.85">'
    )
    for i in range(rows):
        row_y = round(PADDING + LINE_H * i + (LINE_H - cursor_h) / 2, 2)
        t = round(i * ROW_DURATION, 3)
        parts.append(f'<set attributeName="y" to="{row_y}" begin="{t}s"/>')
        parts.append(
            f'<animate attributeName="x" from="{PADDING}" to="{round(PADDING + full_text_w, 2)}" '
            f'begin="{t}s" dur="{ROW_DURATION}s" fill="freeze"/>'
        )
    parts.append("</rect>")

    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
def main():
    explicit_path = sys.argv[1] if len(sys.argv) > 1 else None
    img_path = find_input_image(explicit_path)

    ascii_rows, cols, rows = image_to_ascii_rows(img_path, COLS)
    svg = build_svg(ascii_rows, cols, rows)

    base, _ = os.path.splitext(img_path)
    out_path = base + ".svg"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

    total_dur = round(rows * ROW_DURATION, 2)
    print(f"Source image : {img_path}")
    print(f"Grid size    : {cols} cols x {rows} rows")
    print(f"Saved SVG    : {out_path}")
    print(f"Animation    : ~{total_dur}s, then freezes")


if __name__ == "__main__":
    main()
