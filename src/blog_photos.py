"""Center-crop blog photos to 4:3 and save as JPEG.

Usage: python3 src/blog_photos.py   (blog/<id>/<n>.png -> blog/<id>/<n>.jpg 1440x1080, png 삭제)
Make ⑧ uploads OpenAI images (1536x1024) as PNG, then ready.txt; GitHub Actions runs this on that push.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
W, H = 1440, 1080


def crop43(im):
    w, h = im.size
    if w / h > 4 / 3:
        nw = round(h * 4 / 3)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w * 3 / 4)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((W, H), Image.LANCZOS)


def main():
    for png in sorted((ROOT / "blog").glob("*/*.png")):
        crop43(Image.open(png).convert("RGB")).save(png.with_suffix(".jpg"), quality=88, optimize=True, progressive=True)
        png.unlink()
        print("4:3", png.with_suffix(".jpg").relative_to(ROOT))
    for ready in (ROOT / "blog").glob("*/ready.txt"):
        ready.unlink()


if __name__ == "__main__":
    main()
