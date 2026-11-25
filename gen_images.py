"""Vanr Games — يولّد كل الصور من القوالب (تشغيله اختياري، الصور جاهزة داخل المشروع).

  python gen_images.py

يسوي:
  1) templates/*.png      : القوالب (templates_src/) بعد تحويل ألوانها لألوان Vanr الزرقاء
  2) images/<slug>.png    : صور اللوبي (قالب البداية فوق خلفية Vanr الشتوية)
  3) images/shop/*.png    : صور متجر الإقصاء بنفس الألوان
  4) games_preview.png    : معاينة كل الصور

لو غيّرت صورة السيرفر: حط الصورة الجديدة باسم vanr_banner.jpg ثم شغّل `python gen_images.py --rebuild-bg`
(يحتاج opencv-python + numpy لإزالة الشعار من الخلفية).
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

import cards
from cards import DEEP, GOLD, HAT, ICE, PERI, WHITE, ar, bg_crop, font, tpl

DIR = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(DIR, "templates_src")
OUT_TPL = os.path.join(DIR, "templates")
OUT = os.path.join(DIR, "images")
for p in (OUT_TPL, OUT, os.path.join(OUT, "shop"), os.path.join(OUT, "custom"), os.path.join(OUT, "extra")):
    os.makedirs(p, exist_ok=True)


# ---------------------------------------------------------------- 0) خلفية Vanr نظيفة (بدون شعار)
def rebuild_bg():
    import cv2
    import numpy as np

    im = cv2.imread(os.path.join(DIR, "vanr_banner.jpg"))
    h, w = im.shape[:2]
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    box = np.zeros((h, w), np.uint8)
    box[int(h * .35):int(h * .795), int(w * .24):int(w * .76)] = 255
    m = ((hsv[..., 2] > 205) & (hsv[..., 1] < 70)).astype(np.uint8) * 255
    m = cv2.bitwise_and(m, box)
    m = cv2.dilate(cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)), np.ones((25, 25), np.uint8))
    out = cv2.inpaint(im, cv2.bitwise_and(m, box), 25, cv2.INPAINT_TELEA)
    soft = np.zeros((h, w), np.float32)
    soft[int(h * .33):int(h * .81), int(w * .22):int(w * .79)] = 1
    soft = cv2.GaussianBlur(soft, (0, 0), 28)[..., None]
    out = (out * (1 - soft) + cv2.GaussianBlur(out, (0, 0), 34) * soft).astype(np.uint8)
    cv2.imwrite(os.path.join(DIR, "vanr_bg.png"), out)
    cards._CACHE.clear()


# ---------------------------------------------------------------- 1) تلوين القوالب
STOPS = [(0.0, (34, 44, 92)), (0.30, (84, 100, 160)), (0.75, (190, 201, 236)), (1.0, (255, 255, 255))]


def _lut(ch):
    lut = []
    for v in range(256):
        L = v / 255
        for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
            if L <= b:
                k = (L - a) / (b - a)
                lut.append(int(ca[ch] + (cb[ch] - ca[ch]) * k))
                break
    return lut


LUTS = [_lut(i) for i in range(3)]


def recolor(img, boost=1.5):
    """يحوّل رمادي/أسود القالب لتدرج أزرق Vanr، ويقوّي شفافية اللوحات الداكنة شوي"""
    img = img.convert("RGBA")
    a = img.split()[3]
    L = img.convert("RGB").convert("L")
    r, g, b = (L.point(lut) for lut in LUTS)
    dark = L.point(lambda v: 255 if v < 70 else 0)
    boosted = a.point(lambda v: min(255, int(v * boost)) if v < 200 else v)
    a2 = Image.composite(boosted, a, dark)
    return Image.merge("RGBA", (r, g, b, a2))


def build_templates():
    n = 0
    for f in sorted(os.listdir(SRC)):
        if f.endswith(".png"):
            recolor(Image.open(os.path.join(SRC, f)), 1.0 if f.startswith('start_') else 1.5).save(os.path.join(OUT_TPL, f), optimize=True)
            n += 1
    cards._CACHE.clear()
    return n


# ---------------------------------------------------------------- 2) صور اللوبي
# slug اللعبة -> قالب البداية
START = {
    "roulette": "roulette", "mafia": "mafia", "mine": "mine", "chairs": "chairs", "rps": "rps",
    "hide": "hide", "connect": "connect", "xo": "xo", "bomb": "bomb",
}
# قوالب جاهزة لألعاب مستقبلية (ما فيها لعبة بالبوت للحين) تنحفظ في images/extra
EXTRA = ["scatt", "roulettez", "guess", "buttons", "dice", "reverse"]


def start_image(tname, w=1280):
    t = tpl("start_" + tname)
    bg = bg_crop(t.width, t.height, 0.95, 0.04, fixed=(0.5, 0.42, 0.98)).convert("RGBA")
    bg.alpha_composite(t)
    img = bg.convert("RGB")
    return img.resize((w, int(img.height * w / img.width)), Image.LANCZOS)


def build_start():
    ims = []
    for slug, t in START.items():
        im = start_image(t)
        im.save(os.path.join(OUT, slug + ".png"), optimize=True)
        ims.append(im)
    for t in EXTRA:
        start_image(t).save(os.path.join(OUT, "extra", t + ".png"), optimize=True)
    return ims


# ---------------------------------------------------------------- 3) صور المتجر
def rot(pts, ang, cx, cy):
    a = math.radians(ang)
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def starpoly(cx, cy, r1, r2, n):
    pts = []
    for k in range(n * 2):
        a = -math.pi / 2 + k * math.pi / n
        r = r1 if k % 2 == 0 else r2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


ORANGE = (255, 150, 90)


def boom(d, cx, cy):
    d.polygon(starpoly(cx, cy, 115, 58, 9), fill=ORANGE)
    d.polygon(starpoly(cx, cy, 70, 36, 9), fill=GOLD)


def bomb(d, cx, cy):
    d.line((cx + 25, cy - 55, cx + 55, cy - 95, cx + 90, cy - 95), fill=WHITE, width=9)
    d.polygon(starpoly(cx + 100, cy - 95, 28, 11, 6), fill=GOLD)
    d.ellipse((cx - 85, cy - 65, cx + 85, cy + 105), fill=DEEP, outline=WHITE, width=7)
    d.ellipse((cx - 55, cy - 38, cx - 25, cy - 8), fill=PERI)
    d.rectangle((cx - 12, cy - 78, cx + 38, cy - 55), fill=HAT)


def skull(d, cx, cy):
    d.ellipse((cx - 82, cy - 100, cx + 82, cy + 50), fill=WHITE)
    d.rounded_rectangle((cx - 48, cy + 25, cx + 48, cy + 95), 14, fill=WHITE)
    for sx in (-34, 34):
        d.ellipse((cx + sx - 22, cy - 40, cx + sx + 22, cy + 4), fill=DEEP)
    d.polygon([(cx, cy + 6), (cx - 11, cy + 28), (cx + 11, cy + 28)], fill=DEEP)
    for k in range(-2, 3):
        d.line((cx + k * 18, cy + 62, cx + k * 18, cy + 95), fill=DEEP, width=4)


def bolt(d, cx, cy):
    d.polygon([(cx + 15, cy - 115), (cx - 62, cy + 10), (cx - 5, cy + 10), (cx - 28, cy + 115),
               (cx + 68, cy - 30), (cx + 10, cy - 30)], fill=GOLD, outline=WHITE)


def sword(d, cx, cy):
    blade = [(-115, -13), (55, -13), (100, 0), (55, 13), (-115, 13)]
    d.polygon(rot(blade, -45, cx, cy), fill=(225, 232, 248), outline=WHITE)
    d.polygon(rot([(55, -42), (72, -42), (72, 42), (55, 42)], -45, cx, cy), fill=HAT)
    d.polygon(rot([(72, -10), (120, -10), (120, 10), (72, 10)], -45, cx, cy), fill=(150, 110, 90))


def crown(d, cx, cy):
    d.polygon([(cx - 100, cy + 60), (cx - 100, cy - 50), (cx - 50, cy), (cx, cy - 75), (cx + 50, cy),
               (cx + 100, cy - 50), (cx + 100, cy + 60)], fill=GOLD, outline=WHITE)
    for x, col in ((-60, HAT), (0, (90, 130, 230)), (60, (120, 210, 190))):
        d.ellipse((cx + x - 14, cy + 22, cx + x + 14, cy + 50), fill=col)


def fire(d, cx, cy):
    d.polygon([(cx, cy - 108), (cx + 44, cy - 35), (cx + 24, cy - 40), (cx + 58, cy + 20), (cx + 30, cy + 90),
               (cx - 30, cy + 90), (cx - 58, cy + 20), (cx - 24, cy - 40), (cx - 44, cy - 35)], fill=ORANGE)
    d.polygon([(cx, cy - 30), (cx + 28, cy + 25), (cx + 18, cy + 82), (cx - 18, cy + 82), (cx - 28, cy + 25)], fill=GOLD)


def star(d, cx, cy):
    d.polygon(starpoly(cx, cy, 112, 46, 5), fill=GOLD, outline=WHITE)


SHOP = [("boom", "الانفجار", boom), ("bomb", "القنبلة", bomb), ("skull", "الجمجمة", skull), ("bolt", "الصاعقة", bolt),
        ("sword", "السيف", sword), ("crown", "التاج", crown), ("fire", "النار", fire), ("star", "النجمة", star)]


def build_shop():
    for j, (slug, title, fn) in enumerate(SHOP):
        W, H = 600, 340
        img = bg_crop(W, H, 0.62, 0.2, rnd=random.Random(100 + j)).convert("RGBA")
        cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(cv)
        fn(d, W // 2, int(H * 0.40))
        a = cv.split()[3].filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * .55))
        sh = Image.merge("RGBA", (Image.new("L", cv.size, 20), Image.new("L", cv.size, 28), Image.new("L", cv.size, 70), a))
        img.alpha_composite(sh, (6, 8))
        img.alpha_composite(cv)
        d = ImageDraw.Draw(img)
        d.rectangle((0, H - 10, W, H), fill=PERI)
        cards.shadow_text(d, (W // 2, int(H * 0.86)), ar(title), font(52), off=2)
        d.text((W - 16, H - 24), "VANR GAMES", font=font(16), fill=ICE, anchor="rb")
        img.convert("RGB").save(os.path.join(OUT, "shop", slug + ".png"), optimize=True)
    return len(SHOP)


# ---------------------------------------------------------------- 4) معاينة
def preview(imgs):
    tw, th = 400, 147
    cols = 3
    rows = math.ceil(len(imgs) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 10, rows * th + (rows + 1) * 10), DEEP)
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (10 + (k % cols) * (tw + 10), 10 + (k // cols) * (th + 10)))
    sheet.save(os.path.join(DIR, "games_preview.png"), optimize=True)


if __name__ == "__main__":
    if "--rebuild-bg" in sys.argv:
        rebuild_bg()
    nt = build_templates()
    ims = build_start()
    ns = build_shop()
    preview(ims)
    print(f"templates={nt} lobby={len(ims)}+{len(EXTRA)} shop={ns}")
