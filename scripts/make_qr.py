"""Makes qr.png, qr_poster.png and qr_poster.pdf for a live URL.

Usage: python scripts/make_qr.py https://recycleagent.onrender.com
"""
import math
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

ROOT = Path(__file__).resolve().parent.parent

# A4 at 150 dpi.
WIDTH, HEIGHT = 1240, 1754
DPI = 150
MARGIN = 70

GREEN = "#15803D"
DARK = "#111827"
GRAY = "#4B5563"
SMOOTH = 4  # Shapes are drawn this many times larger, then shrunk for smooth edges.

TITLE = "AI Recycling Guide Lab"
SUBTITLE_EN = "Scan & ask how to recycle"
SUBTITLE_KO = "스캔하고 분리배출 방법을 물어보세요"
STEPS = ["Scan", "Ask about any item", "Get sorting steps"]
FOOTER = "Based on official Korean waste disposal guidelines · AI can make mistakes — check local rules"

QR_CODE_SIZE = 800  # Size of the black pattern itself; the white border adds to this.
QR_MAX_SIZE = 1000  # Largest total size, including the border, that fits the layout.
QR_BORDER = 4


def stop(message: str) -> None:
    sys.exit(f"Error: {message}")


def find_fonts() -> tuple[tuple[str, int], tuple[str, int]]:
    """Returns (path, index) for a regular and a bold Korean font, found with fc-list."""
    install_help = "Install one, e.g. on Ubuntu: sudo apt install fonts-noto-cjk (or fonts-nanum)."
    if not shutil.which("fc-list"):
        stop(f"fc-list was not found, so no Korean font can be located. {install_help}")

    output = subprocess.run(
        ["fc-list", ":lang=ko", "--format", "%{family}|%{style}|%{index}|%{file}\n"],
        capture_output=True,
        text=True,
    ).stdout

    for wanted in ("Noto Sans CJK KR", "NanumGothic"):
        found = {}
        for line in output.splitlines():
            family, style, index, path = line.split("|", 3)
            if wanted not in family:
                continue
            for weight in ("Regular", "Bold"):
                if weight in style.split(",") and weight not in found:
                    # The upper bits of a font index mark variable-font instances.
                    found[weight] = (path, int(index) & 0xFFFF)
        if len(found) == 2:
            return found["Regular"], found["Bold"]

    stop(f"no Noto Sans CJK KR or NanumGothic font (regular and bold) was found. {install_help}")


def make_qr_image(url: str, box_size: int) -> Image.Image:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=box_size, border=QR_BORDER)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def qr_box_size_for_poster(url: str) -> int:
    """Whole pixels per module, so the printed QR stays perfectly sharp."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, border=QR_BORDER)
    qr.add_data(url)
    qr.make(fit=True)
    total_modules = qr.modules_count + 2 * QR_BORDER
    return min(round(QR_CODE_SIZE / qr.modules_count), QR_MAX_SIZE // total_modules)


def make_logo(size: int) -> Image.Image:
    """Green rounded square with a white recycle icon: three arrows chasing in a circle."""
    big = size * SMOOTH
    logo = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 0.27, fill=GREEN)

    center = big / 2
    radius = big * 0.27
    thickness = int(big * 0.085)
    head = big * 0.125
    box = (center - radius, center - radius, center + radius, center + radius)
    for start in (-90, 30, 150):
        end = start + 78
        draw.arc(box, start, end, fill="white", width=thickness)
        # Arrowhead at the end of the arc, pointing along the circle.
        angle = math.radians(end)
        middle = radius - thickness / 2
        tip_x = center + middle * math.cos(angle)
        tip_y = center + middle * math.sin(angle)
        along = (-math.sin(angle), math.cos(angle))
        out = (math.cos(angle), math.sin(angle))
        draw.polygon(
            [
                (tip_x + along[0] * head * 1.15, tip_y + along[1] * head * 1.15),
                (tip_x + out[0] * head, tip_y + out[1] * head),
                (tip_x - out[0] * head, tip_y - out[1] * head),
            ],
            fill="white",
        )
    return logo.resize((size, size), Image.LANCZOS)


def make_frame(size: int, radius: int, line: int) -> Image.Image:
    big = size * SMOOTH
    frame = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle(
        (0, 0, big - 1, big - 1), radius=radius * SMOOTH, outline=GREEN, width=line * SMOOTH
    )
    return frame.resize((size, size), Image.LANCZOS)


def fitted_font(font: tuple[str, int], size: int, text: str, max_width: int) -> ImageFont.FreeTypeFont:
    """The font at this size, or smaller if the text would not fit."""
    path, index = font
    while size > 8:
        loaded = ImageFont.truetype(path, size, index=index)
        if loaded.getlength(text) <= max_width:
            return loaded
        size -= 1
    return ImageFont.truetype(path, size, index=index)


def centered_text(draw, y: int, text: str, font, fill: str) -> None:
    draw.text((WIDTH / 2, y), text, font=font, fill=fill, anchor="mt")


def make_poster(url: str, regular, bold) -> Image.Image:
    poster = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(poster)
    usable = WIDTH - 2 * MARGIN

    # Logo and title, centered together.
    logo_size = 112
    gap = 28
    title_font = fitted_font(bold, 76, TITLE, usable - logo_size - gap)
    title_width = title_font.getlength(TITLE)
    left = int((WIDTH - logo_size - gap - title_width) / 2)
    top = 70
    logo = make_logo(logo_size)
    poster.paste(logo, (left, top), logo)
    draw.text(
        (left + logo_size + gap, top + logo_size / 2), TITLE, font=title_font, fill=DARK, anchor="lm"
    )

    # Subtitles.
    centered_text(draw, 212, SUBTITLE_EN, fitted_font(regular, 46, SUBTITLE_EN, usable), DARK)
    centered_text(draw, 274, SUBTITLE_KO, fitted_font(regular, 40, SUBTITLE_KO, usable), GRAY)

    # QR code in a thin rounded frame. Its white border already separates it from the frame.
    qr_image = make_qr_image(url, qr_box_size_for_poster(url))
    frame_size = qr_image.width
    frame_left = (WIDTH - frame_size) // 2
    frame_top = 345
    poster.paste(qr_image, (frame_left, frame_top))
    frame = make_frame(frame_size, radius=28, line=4)
    poster.paste(frame, (frame_left, frame_top), frame)
    frame_bottom = frame_top + frame_size

    # Short URL for people who can't scan.
    parsed = urlparse(url)
    short_url = parsed.netloc + parsed.path.rstrip("/")
    centered_text(draw, frame_bottom + 24, short_url, fitted_font(regular, 30, short_url, usable), GRAY)

    # Three steps in a row.
    steps = [f"{number}. {step}" for number, step in enumerate(STEPS, start=1)]
    step_gap = 64
    room = usable - step_gap * (len(steps) - 1)
    step_font = fitted_font(bold, 34, "".join(steps), room)
    x = (WIDTH - sum(step_font.getlength(step) for step in steps) - step_gap * (len(steps) - 1)) / 2
    steps_y = frame_bottom + 120
    for step in steps:
        draw.text((x, steps_y), step, font=step_font, fill=GREEN, anchor="ls")
        x += step_font.getlength(step) + step_gap

    # Footer.
    footer_font = fitted_font(regular, 24, FOOTER, usable)
    draw.text((WIDTH / 2, HEIGHT - 70), FOOTER, font=footer_font, fill=GRAY, anchor="mb")
    return poster


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/make_qr.py <live URL>")
    url = sys.argv[1].strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        stop(f"'{url}' is not a full URL. It should look like https://recycleagent.onrender.com")

    regular, bold = find_fonts()

    make_qr_image(url, box_size=20).save(ROOT / "qr.png")

    poster = make_poster(url, regular, bold)
    poster.save(ROOT / "qr_poster.png", dpi=(DPI, DPI))
    # High JPEG quality inside the PDF keeps the QR edges clean.
    poster.save(ROOT / "qr_poster.pdf", "PDF", resolution=DPI, quality=95)

    print(f"QR link: {url}")
    print(f"Font: {Path(regular[0]).name}")
    for name in ("qr.png", "qr_poster.png", "qr_poster.pdf"):
        print(f"Saved: {ROOT / name}")


if __name__ == "__main__":
    main()
