"""Turn a rendered card-news set into a 9:16 Instagram Reel (MP4).

Usage: python3 src/reel.py out/<id>
Reads out/<id>/01.jpg ... and content/<id>.json (for the line colour),
writes out/<id>/reel.mp4: 1080x1920, 30 fps, H.264 + silent AAC, faststart.
"""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, FADE = 1080, 1920, 30, 0.4
SLIDE_W, SLIDE_H, RADIUS = 1000, 1250, 36


def hold(n, total):
    if n == 1:
        return 3.0          # 표지
    if n == total:
        return 2.5          # 사인오프
    return 3.8              # 본문 장은 읽을 시간


def frame(slide, bg, bg2):
    canvas = Image.new("RGB", (W, H), bg)
    grad = Image.linear_gradient("L").resize((W, H))
    canvas = Image.composite(Image.new("RGB", (W, H), bg2), canvas, grad)
    im = Image.open(slide).convert("RGB").resize((SLIDE_W, SLIDE_H), Image.LANCZOS)
    x, y = (W - SLIDE_W) // 2, (H - SLIDE_H) // 2
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([x, y + 14, x + SLIDE_W, y + SLIDE_H + 14], RADIUS, fill=70)
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.composite(Image.new("RGB", (W, H), "#000000"), canvas, shadow)
    mask = Image.new("L", (SLIDE_W, SLIDE_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SLIDE_W - 1, SLIDE_H - 1], RADIUS, fill=255)
    canvas.paste(im, (x, y), mask)
    return canvas


def main():
    out = Path(sys.argv[1]).resolve()
    pid = out.name
    script = json.loads((ROOT / "content" / f"{pid}.json").read_text(encoding="utf-8"))
    theme = json.loads((ROOT / "src/themes.json").read_text(encoding="utf-8"))[script["line"]]
    slides = sorted(out.glob("[0-9][0-9].jpg"))
    if not slides:
        sys.exit(f"슬라이드 없음: {out}")
    fdir = out / "_reel"
    fdir.mkdir(exist_ok=True)
    frames = []
    for s in slides:
        p = fdir / f"{s.stem}.jpg"
        frame(s, theme["bg"], theme["bg2"]).save(p, quality=95)
        frames.append(p)

    total = len(frames)
    durs = [hold(n, total) for n in range(1, total + 1)]
    # 각 장을 (보유 시간 + 페이드)만큼 늘이고 xfade로 이어 붙인다 → 한 번만 인코딩
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for p, d in zip(frames, durs):
        args += ["-framerate", str(FPS), "-loop", "1", "-t", f"{d + FADE:.2f}", "-i", str(p)]
    length = sum(durs) + FADE
    music = ROOT / "assets" / "music" / f"{script['line']}.m4a"  # src/make_music.py로 만든 오리지널 음원
    if music.exists():
        args += ["-i", str(music)]
    else:
        args += ["-f", "lavfi", "-t", f"{length:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    parts, prev, offset = [], "[0:v]", 0.0
    if music.exists():
        # 길이에 맞춰 자르고 끝 2초 페이드아웃, 배경음 수준(-16 LUFS 근처)으로
        parts.append(f"[{total}:a]atrim=0:{length:.2f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.3,afade=t=out:st={length - 2:.2f}:d=2,"
                     f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    for i in range(1, total):
        offset += durs[i - 1]
        lab = f"[v{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.2f}{lab}")
        prev = lab
    parts.append(f"{prev}format=yuv420p,fps={FPS}[vout]")
    tmp = out / "reel.tmp.mp4"
    args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-map", "[aout]" if music.exists() else f"{total}:a",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", "4500k", "-bufsize", "9000k",
             "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", str(FPS * 2),
             "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(tmp)]
    subprocess.run(args, check=True)
    final = out / "reel.mp4"
    tmp.rename(final)
    print("reel", final, f"{length:.1f}s")


if __name__ == "__main__":
    main()
