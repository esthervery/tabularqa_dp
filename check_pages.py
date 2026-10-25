"""페이지 파일 자가 점검.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PAGES = ROOT / "ui" / "pages"

EXPECT = [
    "ui/pages/console.py",
    "ui/pages/history.py",
    "ui/pages/budget_request.py",
    "ui/pages/budget_admin.py",
    "ui/pages/privacy_analysis.py",
    "ui/design.py",
    "ui/fields.py",
    "ui/hints.py",
    "ui/hints.json",
]

print(f"python  : {sys.version.split()[0]}")
print(f"cwd     : {Path.cwd()}")
print(f"repo    : {ROOT}")
print(f"ui/pages: {PAGES}  (exists={PAGES.is_dir()})")
print()

print("ui/pages 실제 파일 (repr — 숨은 문자 확인용):")
if PAGES.is_dir():
    for p in sorted(PAGES.iterdir()):
        kind = "dir " if p.is_dir() else "file"
        size = "" if p.is_dir() else f"{p.stat().st_size:>8} bytes"
        print(f"  {kind} {p.name!r:42} {size}")
else:
    print("  (폴더가 없습니다 — zip 을 저장소 루트에서 푸셨는지 확인하세요)")

print()
print("기대 파일:")
miss = 0
for rel in EXPECT:
    ok = (ROOT / rel).exists()
    miss += 0 if ok else 1
    print(f"  {'OK  ' if ok else 'MISS'}  {rel}")

print()
if miss:
    print(f"{miss}개가 없습니다.")
    print("· zip 을 풀 때 'ui' 폴더가 아니라 저장소 루트에서 풀었는지 확인하세요.")
    print("  (압축 안에 app.py 와 ui/ 가 들어 있어, 루트에서 풀면 그대로 덮입니다)")
    print("· 위 repr 목록에 이름이 비슷한 파일이 있으면 그게 원인입니다.")
    print("· 파일명을 직접 고칠 때는 탐색기의 '파일 확장명' 표시를 켜고 하세요.")
    sys.exit(1)
print("전부 정상입니다 — `streamlit run app.py` 로 실행하세요.")
