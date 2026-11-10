"""Make 1080x1080 square versions of a card-news set (for Blogger).

Usage: python3 src/square.py <dir-with-01.jpg...> <line>
Writes sq_01.jpg ... sq_07.jpg next to the slides. The 4:5 slide is centred on a
soft line-colour background so no text is cropped.
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S, SLIDE_H, RADIUS = 1080, 1000, 30
SLIDE_W = SLIDE_H * 4 // 5


def square(slide, bg, bg2):
    canvas = Image.new("RGB", (S, S), bg)
    grad = Image.linear_gradient("L").rotate(90).resize((S, S))
    canvas = Image.composite(Image.new("RGB", (S, S), bg2), canvas, grad)
    im = Image.open(slide).convert("RGB").resize((SLIDE_W, SLIDE_H), Image.LANCZOS)
    x, y = (S - SLIDE_W) // 2, (S - SLIDE_H) // 2
    shadow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([x, y + 10, x + SLIDE_W, y + SLIDE_H + 10], RADIUS, fill=60)
    canvas = Image.composite(Image.new("RGB", (S, S), "#000000"), canvas, shadow.filter(ImageFilter.GaussianBlur(18)))
    mask = Image.new("L", (SLIDE_W, SLIDE_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SLIDE_W - 1, SLIDE_H - 1], RADIUS, fill=255)
    canvas.paste(im, (x, y), mask)
    return canvas


def main():
    d, line = Path(sys.argv[1]), sys.argv[2]
    theme = json.loads((ROOT / "src/themes.json").read_text(encoding="utf-8"))[line]
    for s in sorted(d.glob("[0-9][0-9].jpg")):
        out = d / f"sq_{s.stem}.jpg"
        square(s, theme["bg"], theme["bg2"]).save(out, quality=90)
        print("square", out)


if __name__ == "__main__":
    main()
