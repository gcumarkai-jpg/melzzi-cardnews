"""Copy a rendered set into posts/<id>/, push to GitHub, print image URLs and caption as JSON.

Usage: python3 src/publish.py <id>
Run after: python3 src/render.py content/<id>.json [--cover covers/<id>.png]
           python3 src/reel.py out/<id>   (있으면 reel.mp4도 함께 올림)
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout.strip()


REPO = "gcumarkai-jpg/melzzi-cardnews"  # 공개 이미지 주소의 기준. 원격 주소가 프록시 형태여도 이 값을 쓴다


def raw_base():
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    return f"https://raw.githubusercontent.com/{REPO}/{branch}"


def main():
    pid = sys.argv[1]
    src = ROOT / "out" / pid
    imgs = sorted(src.glob("[0-9][0-9].jpg"))
    if not imgs:
        sys.exit(f"렌더 결과 없음: {src}")
    dst = ROOT / "posts" / pid
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.glob("[0-9][0-9].jpg"):
        old.unlink()
    for f in imgs:
        shutil.copy(f, dst / f.name)
    if (src / "sq_cover.jpg").exists():  # 블로거용 정사각형 표지 (render.py가 함께 만듦)
        shutil.copy(src / "sq_cover.jpg", dst / "sq_cover.jpg")
    shutil.copy(src / "caption.txt", dst / "caption.txt")
    reel = src / "reel.mp4"
    if reel.exists():
        shutil.copy(reel, dst / "reel.mp4")
    git("add", f"posts/{pid}", f"content/{pid}.json")
    if git("status", "--porcelain", f"posts/{pid}", f"content/{pid}.json"):
        git("-c", "user.name=MELZZI bot", "-c", "user.email=noreply@anthropic.com", "commit", "-m", f"카드뉴스 {pid} 렌더링")
    git("pull", "--rebase", "--autostash", "origin", git("rev-parse", "--abbrev-ref", "HEAD"))
    git("push", "origin", "HEAD")
    sha = git("rev-parse", "--short", "HEAD")
    base = raw_base()
    urls = [f"{base}/posts/{pid}/{f.name}" for f in imgs]
    reel_url = f"{base}/posts/{pid}/reel.mp4" if (dst / "reel.mp4").exists() else ""
    square_cover_url = f"{base}/posts/{pid}/sq_cover.jpg" if (dst / "sq_cover.jpg").exists() else ""
    print(json.dumps({"id": pid, "commit": sha, "urls": urls, "reel_url": reel_url, "square_cover_url": square_cover_url,
                      "caption": (dst / "caption.txt").read_text(encoding="utf-8")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
