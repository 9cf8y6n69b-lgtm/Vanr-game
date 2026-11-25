"""Vanr Games — بطاقات الصور (تعتمد على القوالب الجاهزة داخل templates/ + خلفية Vanr الشتوية).
لا تحتاج discord، فقط Pillow."""
import io
import os
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, features

DIR = os.path.dirname(os.path.abspath(__file__))
TPL_DIR = os.path.join(DIR, "templates")
BG_PATH = os.path.join(DIR, "vanr_bg.png")
FONT_PATH = os.path.join(DIR, "fonts", "DejaVuSans-Bold.ttf")

# ---------------------------------------------------------------- ألوان Vanr (مأخوذة من صورة السيرفر)
ICE = (198, 209, 241)      # #c6d1f1
SKY = (171, 187, 235)      # #abbbeb
PERI = (146, 161, 208)     # #92a1d0
BLUE = (121, 138, 190)     # #798abe
STEEL = (101, 120, 172)    # #6578ac
NAVY = (52, 66, 120)       # #344278
DEEP = (34, 44, 92)        # #222c5c
SNOW = (237, 237, 243)     # #ededf3
HAT = (193, 75, 112)       # #c14b70  (قبعة الرجل الثلجي)
GOLD = (255, 214, 102)
WHITE = (255, 255, 255)
EMBED_COLOR = 0x798ABE

# ---------------------------------------------------------------- النص العربي
RAQM = features.check("raqm")
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    _SHAPER = True
except Exception:  # pragma: no cover
    _SHAPER = False


def ar(t):
    """تجهيز النص العربي للرسم بـ Pillow (لو raqm موجود ما يحتاج)"""
    if RAQM or not _SHAPER:
        return t
    return get_display(arabic_reshaper.reshape(t))


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def to_buf(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, fmt, optimize=True)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------- القوالب والخلفية
_CACHE = {}


def tpl(name):
    if name not in _CACHE:
        _CACHE[name] = Image.open(os.path.join(TPL_DIR, name + ".png")).convert("RGBA")
    return _CACHE[name].copy()


def _bg_src():
    if "bg" not in _CACHE:
        _CACHE["bg"] = Image.open(BG_PATH).convert("RGB")
    return _CACHE["bg"]


def dusk(img, bright=0.66, tint=0.18):
    """يغمّق الخلفية شوي ويميلها للأزرق عشان يبان النص الأبيض"""
    img = ImageEnhance.Brightness(img).enhance(bright)
    return Image.blend(img, Image.new("RGB", img.size, STEEL), tint)


def bg_crop(w, h, bright=0.66, tint=0.18, rnd=None, fixed=None):
    """قص من خلفية Vanr بنسبة الصورة المطلوبة. fixed=(x,y,scale) يثبّت القص"""
    src = _bg_src()
    sw, sh = src.size
    r = rnd or random
    if fixed:
        cw = int(sw * fixed[2])
        ch = int(cw * h / w)
        x, y = int((sw - cw) * fixed[0]), int((sh - ch) * fixed[1])
    else:
        cw = int(sw * r.uniform(0.62, 1.0))
        ch = int(cw * h / w)
        if ch > sh:
            ch = sh
            cw = int(ch * w / h)
        x, y = r.randint(0, sw - cw), r.randint(0, sh - ch)
    img = src.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)
    return dusk(img, bright, tint)


def compose(name, bg=None, bright=0.66, tint=0.18):
    t = tpl(name)
    bg = (bg or bg_crop(t.width, t.height, bright, tint)).convert("RGBA")
    bg.alpha_composite(t)
    return bg


def fit_text(d, text, max_w, size, min_size=26, step=4):
    f = font(size)
    t = ar(text)
    while d.textlength(t, font=f) > max_w and size > min_size:
        size -= step
        f = font(size)
    return f, t, size


def wrap_lines(d, text, max_w, size, min_size=30, max_lines=2):
    """يحاول يحط النص بسطر، وإذا طويل يقسمه سطرين ويصغّر الخط لين يركب"""
    f, t, s = fit_text(d, text, max_w, size, min_size)
    if d.textlength(t, font=f) <= max_w:
        return f, [t], s
    words = text.split()
    for s in range(size, min_size - 1, -3):
        f = font(s)
        best = None
        for k in range(1, len(words)):
            a, b = " ".join(words[:k]), " ".join(words[k:])
            wa, wb = d.textlength(ar(a), font=f), d.textlength(ar(b), font=f)
            m = max(wa, wb)
            if m <= max_w and (best is None or m < best[0]):
                best = (m, [ar(a), ar(b)])
        if best and max_lines >= 2:
            return f, best[1], s
    f, t, s = fit_text(d, text, max_w, min_size, 14, 2)
    return f, [t], s


def blank_top(img, h):
    """يمسح عنوان القالب (الجزء العلوي) عشان نكتب عنوان ثاني"""
    px = img.load()
    for y in range(h):
        for x in range(img.width):
            px[x, y] = (0, 0, 0, 0)


def shadow_text(d, xy, text, f, fill=WHITE, anchor="mm", shadow=(20, 28, 70), off=3, stroke=0, stroke_fill=None):
    x, y = xy
    d.text((x + off, y + off), text, font=f, fill=shadow, anchor=anchor, stroke_width=stroke, stroke_fill=shadow)
    d.text((x, y), text, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)


# ---------------------------------------------------------------- بطاقات الألعاب الفردية (القوالب mini_*)
# slug اللعبة -> (قالب, عنوان مخصص أو None لو نبي عنوان القالب نفسه)
MINI = {
    "fast": ("mini_fast", None),
    "fakk": ("mini_fkk", None),
    "asbk": ("mini_clasp", None),
    "reverse": ("mini_reverse", None),
    "opposite": ("mini_finish", "ضد"),
    "plural": ("mini_plural", None),
    "singular": ("mini_single", None),
    "capitals": ("mini_capitals", None),
    "flags": ("mini_flags", None),
    "mul": ("mini_calc", None),
    "sub": ("mini_calc", None),
    "fix": ("mini_finish", "صحح"),
    "company": ("mini_finish", "شركة"),
    "dmj": ("mini_finish", "ادمج"),
    "harf": ("mini_finish", "حرف"),
    "bomb": ("mini_finish", "بومب"),
}
BAR = (177, 181, 1127, 294)      # مكان السؤال في القوالب
FLAG_BOX = (458, 217, 859, 413)  # مكان العلم في قالب الأعلام


def mini_card(slug, text="", flag_bytes=None, out_w=1000):
    name, title = MINI.get(slug, ("mini_finish", None))
    t = tpl(name)
    if title:
        blank_top(t, 172)
    bg = bg_crop(t.width, t.height).convert("RGBA")
    bg.alpha_composite(t)
    d = ImageDraw.Draw(bg)
    if title:
        shadow_text(d, (t.width // 2, 98), ar(title), font(86), off=3)
    if name == "mini_flags" and flag_bytes:
        fl = Image.open(io.BytesIO(flag_bytes)).convert("RGBA")
        bx0, by0, bx1, by1 = FLAG_BOX
        pad = 12
        s = min((bx1 - bx0 - 2 * pad) / fl.width, (by1 - by0 - 2 * pad) / fl.height)
        fl = fl.resize((max(1, int(fl.width * s)), max(1, int(fl.height * s))), Image.LANCZOS)
        bg.alpha_composite(fl, ((bx0 + bx1 - fl.width) // 2, (by0 + by1 - fl.height) // 2))
    elif text:
        x0, y0, x1, y1 = BAR
        f, lines, s = wrap_lines(d, text, x1 - x0 - 70, 74, 30)
        cy = (y0 + y1) // 2
        gap = int(s * 1.05)
        for k, ln in enumerate(lines):
            y = cy + (k - (len(lines) - 1) / 2) * gap
            d.text(((x0 + x1) // 2, y), ln, font=f, fill=WHITE, anchor="mm")
    img = bg.convert("RGB")
    return to_buf(img.resize((out_w, int(img.height * out_w / img.width)), Image.LANCZOS))


# ---------------------------------------------------------------- بطاقة سؤال البومب (قالب bomb_round)
PILL = (316, 206, 1017, 292)


def bomb_card(text, caption=None, out_w=1000):
    """caption=None يبقي نص القالب الأصلي (كلمة تبدأ بالحرف الأول وتنتهي بالثاني)، غير كذا نكتب عنوان جديد"""
    t = tpl("bomb_round")
    if caption:
        blank_top(t, 190)
    bg = bg_crop(t.width, t.height, rnd=random).convert("RGBA")
    bg.alpha_composite(t)
    d = ImageDraw.Draw(bg)
    if caption:
        shadow_text(d, (t.width // 2, 118), ar(caption), font(58), off=2)
    x0, y0, x1, y1 = PILL
    f, lines, s = wrap_lines(d, text, x1 - x0 - 50, 56, 26)
    cy = (y0 + y1) // 2
    gap = int(s * 1.02)
    for k, ln in enumerate(lines):
        d.text(((x0 + x1) // 2, cy + (k - (len(lines) - 1) / 2) * gap), ln, font=f, fill=WHITE, anchor="mm")
    img = bg.convert("RGB")
    return to_buf(img.resize((out_w, int(img.height * out_w / img.width)), Image.LANCZOS))


# ---------------------------------------------------------------- أفاتار دائري
def circle_avatar(avatar_bytes, size):
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            av = Image.new("RGBA", (size, size), PERI + (255,))
    else:
        av = Image.new("RGBA", (size, size), PERI + (255,))
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    return av, mask.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- VS (قالب vs)
VS_CIRCLES = ((92, 173, 360, 441), (1304, 173, 1572, 441))


def vs_card(av1, av2, out_w=1000):
    t = tpl("vs")
    bg = bg_crop(t.width, t.height, 0.7, 0.16, fixed=(0.5, 0.35, 0.9)).convert("RGBA")
    for (x0, y0, x1, y1), avb in zip(VS_CIRCLES, (av1, av2)):
        av, mask = circle_avatar(avb, x1 - x0)
        bg.paste(av, (x0, y0), mask)
    bg.alpha_composite(t)
    img = bg.convert("RGB")
    return to_buf(img.resize((out_w, int(img.height * out_w / img.width)), Image.LANCZOS))


# ---------------------------------------------------------------- فوز (قوالب win_single / win_multi)
WIN_CIRCLE = (675, 108, 1179, 612)
WIN_NAME = (520, 657, 1333, 792)


def win_card(avatar_bytes, name, out_w=1000):
    t = tpl("win_single")
    bg = bg_crop(t.width, t.height, 0.7, 0.16, fixed=(0.4, 0.3, 0.95)).convert("RGBA")
    x0, y0, x1, y1 = WIN_CIRCLE
    av, mask = circle_avatar(avatar_bytes, x1 - x0)
    bg.paste(av, (x0, y0), mask)
    bg.alpha_composite(t)
    d = ImageDraw.Draw(bg)
    nx0, ny0, nx1, ny1 = WIN_NAME
    f, txt, _ = fit_text(d, name, nx1 - nx0 - 60, 84, 30)
    d.text(((nx0 + nx1) // 2, (ny0 + ny1) // 2), txt, font=f, fill=WHITE, anchor="mm")
    # تاج فوق الأفاتار
    cx, base = (x0 + x1) // 2, y0 + 14
    d.polygon([(cx - 95, base), (cx - 110, base - 78), (cx - 48, base - 38), (cx, base - 100),
               (cx + 48, base - 38), (cx + 110, base - 78), (cx + 95, base)], fill=GOLD, outline=WHITE)
    img = bg.convert("RGB")
    return to_buf(img.resize((out_w, int(img.height * out_w / img.width)), Image.LANCZOS))


def multi_win_card(avatars, out_w=900):
    """avatars: [(bytes, name)] — فائزين متعددين داخل قالب multi-win"""
    t = tpl("win_multi")
    bg = bg_crop(t.width, t.height, 0.7, 0.16, fixed=(0.5, 0.5, 0.9)).convert("RGBA")
    bg.alpha_composite(t)
    d = ImageDraw.Draw(bg)
    n = max(1, min(len(avatars), 8))
    cols = min(n, 4)
    rows = (n + cols - 1) // cols
    size = 130 if rows == 1 else 112
    area = (60, 70, t.width - 60, t.height - 60)
    cw, ch = (area[2] - area[0]) / cols, (area[3] - area[1]) / rows
    for k, (avb, nm) in enumerate(avatars[:n]):
        r, c = divmod(k, cols)
        in_row = min(cols, n - r * cols)  # توسيط آخر صف
        cx = area[0] + (area[2] - area[0]) / 2 + (c - (in_row - 1) / 2) * cw
        cy = area[1] + ch * (r + 0.5) - 14
        av, mask = circle_avatar(avb, size)
        bg.paste(av, (int(cx - size / 2), int(cy - size / 2)), mask)
        f, txt, _ = fit_text(d, nm, int(cw) - 16, 26, 14, 2)
        d.text((cx, cy + size / 2 + 26), txt, font=f, fill=WHITE, anchor="mm")
    img = bg.convert("RGB")
    return to_buf(img.resize((out_w, int(img.height * out_w / img.width)), Image.LANCZOS))


# ---------------------------------------------------------------- توب 5 (قالب top5)
TOP_ROWS = ((36, 198, 447, 245), (36, 255, 447, 302), (36, 314, 447, 361), (36, 376, 447, 423), (36, 435, 447, 482))


def top5_card(rows, scale=2):
    """rows: [(rank, name, points, best_seconds|None, avatar_bytes)]"""
    t = tpl("top5")
    t = t.resize((t.width * scale, t.height * scale), Image.LANCZOS)
    img = t.copy()
    d = ImageDraw.Draw(img)
    s = scale
    for (x0, y0, x1, y1), row in zip(TOP_ROWS, rows):
        rank, name, pts, best, avb = row
        cy = (y0 + y1) / 2 * s
        d.text((60 * s, cy), f"{rank}", font=font(22 * s), fill=DEEP, anchor="mm")
        av, mask = circle_avatar(avb, 34 * s)
        img.paste(av, (int(86 * s), int(cy - 17 * s)), mask)
        f, txt, _ = fit_text(d, name, 130 * s, 19 * s, 11 * s, 2)
        d.text((128 * s, cy), txt, font=f, fill=DEEP, anchor="lm")
        d.text((310 * s, cy), str(pts), font=font(21 * s), fill=DEEP, anchor="mm")
        d.text((408 * s, cy), (f"{best:.1f}" if best else "—"), font=font(19 * s), fill=DEEP, anchor="mm")
    return to_buf(img)


# ---------------------------------------------------------------- بطاقة نقاطي
def stats_card(name, avatar_bytes, points, best):
    W, H = 760, 300
    img = bg_crop(W, H, 0.62, 0.2)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle((8, 8, W - 8, H - 8), 34, fill=DEEP + (170,), outline=SNOW + (255,), width=4)
    img = Image.alpha_composite(img.convert("RGBA"), ov)
    d = ImageDraw.Draw(img)
    av, mask = circle_avatar(avatar_bytes, 190)
    d.ellipse((50, 52, 262, 264), outline=SNOW, width=4)
    img.paste(av, (61, 63), mask)
    d.line((320, 40, 320, 260), fill=SNOW, width=3)
    d.text((350, 62), ar(name)[:22], font=font(34), fill=WHITE, anchor="lm")
    d.line((350, 92, 540, 92), fill=ICE, width=3)
    rows = [("النقاط", str(points)), ("أسرع زمن", f"{best:.2f}ث" if best else "—")]
    for k, (lab, val) in enumerate(rows):
        y = 118 + k * 74
        d.rounded_rectangle((350, y, 725, y + 56), 22, outline=ICE, width=3)
        d.text((372, y + 28), ar(lab), font=font(26), fill=ICE, anchor="lm")
        d.text((705, y + 28), ar(val), font=font(26), fill=WHITE, anchor="rm")
    return to_buf(img.convert("RGB"))
