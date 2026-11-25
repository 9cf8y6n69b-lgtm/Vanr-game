"""💣 بومب — القنبلة تنعطى للاعب عشوائي مع سؤال.
جاوب صح قبل ما ينتهي الوقت (10 ثواني افتراضياً) → القنبلة تروح للاعب ثاني.
جاوب غلط أو خلص الوقت → تنفجر وتطلع من اللعبة. آخر لاعب يبقى يفوز."""
from common import *
from data_ar import WORDS as _W, PLURALS as _P, OPPOSITES as _O, CAPITALS as _CA, COMPANIES as _CO
from data_bomb import BOMB_QA, FALLBACK_PAIRS

BOOM_IMG = os.path.join(IMG_DIR, "shop", "boom.png")


def _strip_al(s):
    return s[2:] if s.startswith("ال") and len(s) > 3 else s


def accepts(answers):
    """يقبل الجواب مع أو بدون 'ال' التعريف"""
    acc = set()
    for a in answers:
        n = norm(a)
        acc.add(n)
        acc.add(_strip_al(n))

    def chk(c):
        n = norm(c)
        return n in acc or _strip_al(n) in acc

    return chk


def custom_bomb():
    return [tuple(x) for x in DB.d.get("custom", {}).get("bomb", []) if len(x) >= 2]


def _words():
    return _W + [x[0] for x in DB.d.get("custom", {}).get("words", []) if x]


# ---------------------------------------------------------------- مولّدات الأسئلة -> (caption, text, check, reveal)
def q_general():
    pool = list(BOMB_QA) + [("سؤال عام",) + x for x in custom_bomb()]
    c = random.choice(pool)
    return c[0], c[1], accepts(c[2:]), c[2]


def q_math():
    k = random.choice("+-×")
    if k == "+":
        a, b = random.randint(10, 99), random.randint(10, 99)
        r = a + b
    elif k == "-":
        a = random.randint(30, 99)
        b = random.randint(5, a - 1)
        r = a - b
    else:
        a, b = random.randint(3, 12), random.randint(3, 12)
        r = a * b
    return "حساب", f"{ar_digits(a)} {k} {ar_digits(b)} = ؟", accepts([str(r)]), str(r)


def q_opposite():
    q = random.choice(_O)
    return "عكس", f"ما عكس كلمة: {q[0]}", accepts(q[1:]), q[1]


def q_plural():
    q = random.choice(_P)
    return "جمع", f"ما جمع كلمة: {q[0]}", accepts(q[1:]), q[1]


def q_singular():
    q = random.choice(_P)
    return "مفرد", f"ما مفرد كلمة: {q[1]}", accepts([q[0]]), q[0]


def q_capital():
    q = random.choice(_CA)
    return "عواصم", f"ما عاصمة: {q[0]}", accepts(q[1:]), q[1]


def q_company():
    q = random.choice(_CO)
    return "شركات", q[0], accepts(q[1:]), q[1]


def q_letters():
    """نفس قالب الصورة الأصلي: كلمة تبدأ بالحرف الأول وتنتهي بالثاني (الحل مضمون لأن الحرفين من كلمة حقيقية)"""
    ws = [norm(w) for w in _words() if len(w) >= 4]
    if ws:
        w = random.choice(ws)
        a, b = w[0], w[-1]
    else:
        a, b = random.choice(FALLBACK_PAIRS)
    na, nb = norm(a), norm(b)

    def chk(c):
        n = norm(c)
        return len(n.split()) == 1 and len(n) >= 3 and n[0] == na and n[-1] == nb and n not in reserved()

    shown = f"{a}  ...  {b}"
    return None, shown, chk, f"مثال: {w if ws else '—'}"


MAKERS = [(q_general, 5), (q_math, 2), (q_opposite, 1), (q_plural, 1), (q_singular, 1), (q_capital, 1),
          (q_company, 1), (q_letters, 2)]


def make_question(seen):
    for _ in range(12):
        fn = random.choices([m for m, _ in MAKERS], [w for _, w in MAKERS])[0]
        cap, text, chk, reveal = fn()
        if text not in seen:
            seen.add(text)
            return cap, text, chk, reveal
    return cap, text, chk, reveal


# ---------------------------------------------------------------- انتظار جواب اللاعب الحامل
async def wait_holder(g, holder, chk, timeout):
    """'ok' | 'wrong' | 'timeout' ، مع رسالة الجواب"""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    res = reserved()
    while True:
        left = end - loop.time()
        if left <= 0:
            return "timeout", None

        def f(m):
            return m.channel == g.channel and m.author.id == holder.id

        try:
            m = await bot.wait_for("message", check=f, timeout=left)
        except asyncio.TimeoutError:
            return "timeout", None
        if norm(m.content) in res:  # أمر للبوت مو جواب
            continue
        return ("ok" if chk(m.content) else "wrong"), m


async def send_q(g, holder, cap, text, end, left_n):
    q = text if cap else f"اكتب كلمة تبدأ بالحرف الأول وتنتهي بالثاني:  {text}"
    e = mk("💣 القنبلة معك!", f"{holder.mention} جاوب قبل لا تنفجر ⏳ <t:{end}:R>\n\n**{q}**\n\n👥 المتبقين: {left_n}")
    kw = {}
    try:
        buf = await asyncio.to_thread(cards.bomb_card, text, cap)
        kw["file"] = discord.File(buf, "bomb.png")
        e.set_image(url="attachment://bomb.png")
    except Exception:
        traceback.print_exc()
    await g.channel.send(content=holder.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=[holder]), **kw)


@game("بومب", "bomb", "💣 بومب", "group", 10)
async def g_bomb(g):
    pl = await lobby(g, "", 2, 20, 30)
    if not pl:
        return
    alive = pl[:]
    random.shuffle(alive)
    seen, rnd = set(), 1
    T = g.T()
    await say(g, "💣 بدأ بومب!", f"القنبلة تنتقل بين اللاعبين، عندك **{T} ثواني** لكل سؤال.\nجاوب صح تنتقل، جاوب غلط أو تأخرت تنفجر 💥")
    await asyncio.sleep(2)
    while len(alive) > 1:
        holder = random.choice(alive)
        while True:
            cap, text, chk, reveal = make_question(seen)
            end = int(time.time()) + T
            await send_q(g, holder, cap, text, end, len(alive))
            res, msg = await wait_holder(g, holder, chk, T)
            if res == "ok":
                try:
                    await msg.add_reaction("✅")
                except discord.HTTPException:
                    pass
                nxt = random.choice([p for p in alive if p != holder])
                await say(g, "✅ إجابة صحيحة", f"{holder.mention} نجا! القنبلة انتقلت إلى {nxt.mention} 🔥")
                holder = nxt
                await asyncio.sleep(1.5)
                continue
            why = "جاوب غلط ❌" if res == "wrong" else "انتهى الوقت ⏰"
            break
        alive.remove(holder)
        file = None
        if os.path.exists(BOOM_IMG):
            file = discord.File(BOOM_IMG, "boom.png")
        await say(g, "💥 بووم!", f"انفجرت القنبلة في {holder.mention} — {why}\n✔️ الجواب: **{reveal}**\n👥 المتبقين: {len(alive)}", file=file)
        rnd += 1
        await asyncio.sleep(2.5)
    await finish(g, [alive[0]], 1, 3)
