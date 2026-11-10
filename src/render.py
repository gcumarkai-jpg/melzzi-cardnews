"""MELZZI card-news renderer.

Usage: python3 src/render.py content/<file>.json [--out out]
Reads a slide-script JSON, checks it against the brand ad rules, and renders
each slide to a 1080x1350 JPEG with headless Chromium.
"""
import argparse, json, re, sys
from pathlib import Path
from markupsafe import Markup, escape
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# 브랜드 설정 문서 > 광고 표현 규칙의 "쓰지 않는 표현" (일반식품 기준)
BANNED = [
    "치료", "완화", "예방", "아토피", "여드름", "건조증", "불면", "처방", "복용", "약효",
    "먹는 보습", "이너뷰티", "피부 속부터", "속부터 촉촉", "촉촉하게 채워", "생기 있는 피부",
    "장 건강", "마음 안정", "긴장 완화", "숙면", "효과", "효능", "개선", "100%", "무조건", "최고",
    "히알루론산", "프리바이오틱", "마그네슘", "비타민",
]
# 영어 대본용 (단어 경계, 대소문자 무시). 일반식품: 질병·효능·의약품·최상급 표현 금지
BANNED_EN = [
    "treat", "treats", "treatment", "cure", "cures", "heal", "heals", "healing", "remedy", "prevent", "prevents",
    "prevention", "relieve", "relieves", "relief", "acne", "eczema", "atopic", "dermatitis", "insomnia",
    "prescription", "dose", "dosage", "medicine", "medicinal", "supplement", "efficacy", "effective",
    "effect", "effects", "improve", "improves", "improvement", "boost", "boosts", "detox", "inner beauty",
    "beauty from within", "from within", "from the inside", "drinkable", "edible skincare", "gut health",
    "deep sleep", "sound sleep", "anti-aging", "anti-ageing", "clinically", "proven", "guaranteed",
    "100%", "best", "#1", "number one", "miracle", "collagen", "hyaluronic", "prebiotic", "probiotic",
    "magnesium", "vitamin", "vitamins", "anxiety", "stress relief",
]
MAX_SLIDES = 10  # Instagram publishing API carousel limit


def all_text(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k != "photo_prompt":   # 이미지 생성용 지시문(게시되지 않음, "no medicine" 같은 부정문 포함)
                yield from all_text(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_text(v)


def check(script):
    errors = []
    slides = script["slides"]
    if len(slides) > MAX_SLIDES:
        errors.append(f"슬라이드 {len(slides)}장: 최대 {MAX_SLIDES}장")
    if script.get("format") == "info":
        for i, s in enumerate(slides, 1):
            if s.get("package"):
                errors.append(f"{i}번 슬라이드: 정보형 게시물에는 패키지를 넣을 수 없음")
    for i, s in enumerate(slides, 1):
        for prop in s.get("scene") or []:
            if not (ROOT / "assets/props" / f"{prop}.png").exists():
                errors.append(f"{i}번 슬라이드: 소품 '{prop}' 없음 (assets/props 확인)")
    for text in all_text(script):
        for w in BANNED:
            if w in text:
                errors.append(f"금지 표현 '{w}': {text[:40]}")
        for w in BANNED_EN:
            if re.search(r"(?<![\w#])" + re.escape(w) + r"(?!\w)", text, re.I):
                errors.append(f"금지 표현 '{w}': {text[:60]}")
    return errors


def hl(text):
    """Escape, turn [[word]] into a highlight span and newlines into <br>."""
    out = str(escape(text or ""))
    out = re.sub(r"\[\[(.+?)\]\]", r'<span class="hl">\1</span>', out)
    return Markup(out.replace("\n", "<br>"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--check-only", action="store_true", help="규칙 검사만 하고 렌더링하지 않음")
    ap.add_argument("--cover", help="표지 사진 파일 (Make가 만든 cover.jpg). 없으면 scene 소품으로 표지 제작")
    args = ap.parse_args()

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    errors = check(script)
    if errors:
        print("렌더링 중단 — 광고 표현 규칙 위반:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    if args.check_only:
        print("규칙 검사 통과"); return

    theme = json.loads((ROOT / "src/themes.json").read_text(encoding="utf-8"))[script["line"]]
    env = Environment(loader=FileSystemLoader(str(ROOT / "src")), autoescape=True)
    env.filters["hl"] = hl
    # 제목은 강제 줄바꿈을 무시하고, 폭이 넘칠 때만 균형 있게 자동 줄바꿈
    env.filters["title"] = lambda t: hl((t or "").replace("\n", " "))
    tpl = env.get_template("template.html")

    outdir = Path(args.out) / script["id"]
    (outdir / "_html").mkdir(parents=True, exist_ok=True)
    total = len(script["slides"])
    cover = script["slides"][0]
    if args.cover and Path(args.cover).exists():
        cover["photo_src"] = Path(args.cover).resolve().as_uri()
    elif cover.get("photo"):
        cover["photo_src"] = (ROOT / "assets" / cover["photo"]).as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for n, s in enumerate(script["slides"], 1):
            html = tpl.render(s=s, t=theme, n=n, total=total, line=script["line"], lang=script.get("lang", "ko"), root=ROOT.as_uri())
            hp = outdir / "_html" / f"{n:02d}.html"
            hp.write_text(html, encoding="utf-8")
            page.goto(hp.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_load_state("networkidle")
            jp = outdir / f"{n:02d}.jpg"
            page.screenshot(path=str(jp), type="jpeg", quality=92, full_page=False)
            print("rendered", jp)
        # 블로거용 정사각형 표지 (같은 표지를 1:1 레이아웃으로 다시 그림)
        sq = browser.new_page(viewport={"width": 1080, "height": 1080})
        html = tpl.render(s=cover, t=theme, n=1, total=total, line=script["line"], lang=script.get("lang", "ko"), root=ROOT.as_uri(), square=True)
        hp = outdir / "_html" / "sq_cover.html"
        hp.write_text(html, encoding="utf-8")
        sq.goto(hp.as_uri())
        sq.evaluate("document.fonts.ready")
        sq.wait_for_load_state("networkidle")
        sq.screenshot(path=str(outdir / "sq_cover.jpg"), type="jpeg", quality=92, full_page=False)
        print("rendered", outdir / "sq_cover.jpg")
        browser.close()

    if script.get("caption"):   # 영어 게시물: caption + cta + hashtags
        parts = [script["caption"], script["cta"], " ".join(script["hashtags"])]
    else:                         # 예전 한국어 게시물
        parts = [script["caption_ko"], script["caption_en"], script["cta"], " ".join(script["hashtags"])]
    caption = "\n\n".join(parts)
    (outdir / "caption.txt").write_text(caption, encoding="utf-8")
    print("caption", outdir / "caption.txt")


if __name__ == "__main__":
    main()
