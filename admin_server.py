"""
Rossi SiteGuard Monitor — Admin Panel
Панель управления лицензиями. Лицензии хранятся в PostgreSQL.
Ключи генерируются с той же HMAC-логикой, что и валидатор в десктоп-приложении.
"""
from flask import Flask, request, redirect, session, jsonify
import os, json, datetime, hashlib, hmac, string, random
import psycopg2, psycopg2.extras

app = Flask(__name__)
app.secret_key = os.urandom(24)

ADMIN_USER = "admin"
ADMIN_PASS = "SiteGuard2024Admin!"

# ─── Тот же секрет, что и в core/license_validator.py ────────────────────────
LICENSE_HMAC_SECRET = b"RossiSiteGuard_2024_PROD_SECRET_KEY_v1"

PLAN_CHARS   = {"T": "trial", "S": "starter", "P": "professional", "B": "business", "E": "enterprise"}
PLAN_REVERSE = {v: k for k, v in PLAN_CHARS.items()}
PLAN_CONFIG  = {
    "trial":        {"max_sites": 3,      "days": 14,  "label": "Trial"},
    "starter":      {"max_sites": 5,      "days": 365, "label": "Starter"},
    "professional": {"max_sites": 25,     "days": 365, "label": "Professional"},
    "business":     {"max_sites": 100,    "days": 365, "label": "Business"},
    "enterprise":   {"max_sites": 999999, "days": 365, "label": "Enterprise"},
}
_CHARS = string.ascii_uppercase + string.digits

DB = dict(host="localhost", port=5432, dbname="siteguard_db",
          user="siteguard", password="siteguard_pass_2024")


# ─── Генерация и валидация ────────────────────────────────────────────────────

def _checksum(body: str) -> str:
    return hmac.new(LICENSE_HMAC_SECRET, body.encode(), hashlib.sha256).hexdigest().upper()[:5]

def gen_key(plan: str) -> str:
    pc = PLAN_REVERSE[plan]
    g1 = pc + "".join(random.choices(_CHARS, k=4))
    body = "SG-" + "-".join([g1] + ["".join(random.choices(_CHARS, k=5)) for _ in range(3)])
    return f"{body}-{_checksum(body)}"

def validate_key_local(key: str) -> tuple:
    """Валидация ключа без БД — только HMAC."""
    parts = key.strip().upper().split("-")
    if len(parts) != 6 or parts[0] != "SG":
        return False, "Неверный формат"
    for p in parts[1:]:
        if len(p) != 5:
            return False, "Неверная длина группы"
    body = "-".join(parts[:5])
    if parts[5] != _checksum(body):
        return False, "Контрольная сумма не совпадает"
    plan = PLAN_CHARS.get(parts[1][0])
    if not plan:
        return False, "Неизвестный тип плана"
    return True, plan


# ─── База данных ─────────────────────────────────────────────────────────────

def db():
    return psycopg2.connect(**DB)

def get_licenses(limit=500):
    try:
        with db() as c:
            with c.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT id,license_key,organization,plan,max_sites,"
                    "is_active,activated_at,expires_at,created_at,features "
                    "FROM licenses ORDER BY created_at DESC LIMIT %s", (limit,)
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return []

def create_license(email, plan, days, max_sites):
    key = gen_key(plan)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=days)
    features = {
        "availability_check": True, "ssl_check": True,
        "ui_tests": plan in ("professional","business","enterprise"),
        "security_scan": plan in ("business","enterprise"),
        "api_access": plan in ("professional","business","enterprise"),
    }
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO licenses(license_key,organization,plan,max_sites,"
                    "is_active,activated_at,expires_at,features) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (key, email, plan, max_sites, True, now, expires, json.dumps(features))
                )
            c.commit()
        return key, None
    except Exception as e:
        return None, str(e)

def revoke(key):
    try:
        with db() as c:
            with c.cursor() as cur:
                cur.execute("UPDATE licenses SET is_active=FALSE WHERE license_key=%s", (key,))
            c.commit()
    except Exception:
        pass

def lookup_key(key):
    """Поиск ключа в БД + локальная HMAC-проверка."""
    ok, plan_or_err = validate_key_local(key)
    if not ok:
        return None, plan_or_err
    try:
        with db() as c:
            with c.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM licenses WHERE license_key=%s", (key,)
                )
                row = cur.fetchone()
        if not row:
            return None, "Ключ не найден в базе данных"
        row = dict(row)
        if not row["is_active"]:
            return None, "Лицензия отозвана"
        if row["expires_at"] and row["expires_at"].replace(tzinfo=None) < datetime.datetime.utcnow():
            return None, "Лицензия истекла"
        return row, None
    except Exception as e:
        return None, f"Ошибка БД: {e}"


# ─── Общие HTML-компоненты ────────────────────────────────────────────────────

CSS = """<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f23;color:#e0e0ff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;min-height:100vh}
.sb{width:240px;background:#1a1a2e;border-right:1px solid #2a2a4a;padding:24px 0;flex-shrink:0;display:flex;flex-direction:column}
.logo{padding:0 24px 28px;border-bottom:1px solid #2a2a4a;margin-bottom:16px}
.logo h2{font-size:1.05rem;background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:700}
.logo span{font-size:.72rem;color:#555}
a.ni{display:flex;align-items:center;gap:10px;padding:11px 24px;border-left:3px solid transparent;color:#888;text-decoration:none;font-size:.88rem}
a.ni:hover,a.ni.on{background:rgba(108,99,255,.1);border-left-color:#6c63ff;color:#e0e0ff}
.sb-bot{margin-top:auto;padding:16px 24px;border-top:1px solid #2a2a4a}
.main{flex:1;overflow-y:auto;padding:32px}
.ph{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}
.ph h1{font-size:1.5rem;font-weight:700}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:28px}
.st{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:12px;padding:22px}
.st .v{font-size:1.9rem;font-weight:700;background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.st .l{color:#888;font-size:.82rem;margin-top:4px}
.card{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:12px;padding:24px;margin-bottom:22px}
.btn{padding:9px 18px;border:none;border-radius:8px;cursor:pointer;font-size:.87rem;font-weight:600;text-decoration:none;display:inline-block}
.bp{background:linear-gradient(135deg,#6c63ff,#e040fb);color:#fff}
.bs{padding:5px 12px;font-size:.78rem}
.bd{background:#ff4757;color:#fff}
.bg{background:#252540;color:#aaa}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:10px 14px;border-bottom:2px solid #2a2a4a;color:#555;font-size:.77rem;text-transform:uppercase}
td{padding:11px 14px;border-bottom:1px solid #1e1e3a;font-size:.87rem}
tr:hover td{background:rgba(108,99,255,.04)}
.ba{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.72rem;font-weight:700;background:rgba(46,213,115,.12);color:#2ed573}
.bi{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.72rem;font-weight:700;background:rgba(255,71,87,.12);color:#ff4757}
.k{font-family:monospace;font-size:.82rem;color:#6c63ff;background:rgba(108,99,255,.08);padding:2px 7px;border-radius:4px;user-select:all;cursor:pointer}
.k:hover{background:rgba(108,99,255,.2)}
.fc{width:100%;padding:9px 12px;background:#252540;border:1px solid #333;border-radius:7px;color:#fff;font-size:.88rem;outline:none}
.fc:focus{border-color:#6c63ff}
.fr{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.fg{margin-bottom:14px}
.fg label{display:block;margin-bottom:5px;font-size:.82rem;color:#aaa}
.mb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;align-items:center;justify-content:center}
.mb.show{display:flex}
.mc{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:30px;width:500px;max-width:94vw}
.mh{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.mh h2{font-size:1.1rem;font-weight:700}
.xb{background:none;border:none;color:#555;font-size:1.5rem;cursor:pointer}
</style>"""

MODAL = """<div class=mb id=cm>
<div class=mc>
<div class=mh><h2>Создать лицензию</h2><button class=xb onclick="document.getElementById('cm').classList.remove('show')">&#x2715;</button></div>
<form method=POST action=/admin/create>
<div class=fr>
  <div class=fg><label>Email / Организация</label><input class=fc name=email placeholder="user@example.com" required></div>
  <div class=fg><label>Тариф</label><select class=fc name=plan>
    <option value=trial>Trial — 14 дней</option>
    <option value=starter>Starter</option>
    <option value=professional selected>Professional</option>
    <option value=business>Business</option>
    <option value=enterprise>Enterprise</option>
  </select></div>
</div>
<div class=fr>
  <div class=fg><label>Срок (дней)</label><input class=fc name=days type=number value=365 min=1></div>
  <div class=fg><label>Макс. сайтов</label><input class=fc name=max_sites type=number value=25></div>
</div>
<div style="display:flex;gap:10px;justify-content:flex-end">
  <button type=button class="btn bg" onclick="document.getElementById('cm').classList.remove('show')">Отмена</button>
  <button type=submit class="btn bp">Создать ключ</button>
</div>
</form></div></div>"""

def nav(active):
    items = [("dash","/admin","📊","Дашборд"),("lic","/admin/licenses","🔑","Лицензии"),
             ("stats","/admin/stats","📈","Статистика"),("set","/admin/settings","⚙️","Настройки")]
    html = ""
    for key, url, ic, label in items:
        cls = "ni on" if key == active else "ni"
        html += f'<a class="{cls}" href="{url}">{ic} {label}</a>'
    return (f'<nav class=sb><div class=logo><h2>🛡 SiteGuard</h2><span>Admin Panel v1.0</span></div>'
            f'{html}<a class="ni" href="/" target=_blank>🌐 Сайт</a>'
            f'<div class=sb-bot><a class=ni href="/admin/logout" style="padding:0;color:#555">🚪 Выйти</a></div></nav>')

def page(title, active, body, modal=True):
    m = MODAL if modal else ""
    return (f'<!DOCTYPE html><html><head><title>{title} — SiteGuard</title>{CSS}</head>'
            f'<body>{nav(active)}<main class=main>{body}</main>{m}'
            f'<script>document.querySelectorAll(".k").forEach(e=>e.onclick=()=>{{navigator.clipboard.writeText(e.textContent);e.style.color="#2ed573";setTimeout(()=>e.style.color="",1200)}})</script>'
            f'</body></html>')

def auth(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **kw):
        if not session.get("ok"): return redirect("/admin/login")
        return f(*a, **kw)
    return w


# ─── Маршруты ─────────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET","POST"])
def login():
    err = ""
    if request.method == "POST":
        if request.form.get("u") == ADMIN_USER and request.form.get("p") == ADMIN_PASS:
            session["ok"] = True
            return redirect("/admin/")
        err = "<p style='color:#ff4757;margin-top:10px'>Неверный логин или пароль</p>"
    return (f'<!DOCTYPE html><html><head><title>Вход</title>{CSS}</head>'
            f'<body style="display:block"><div style="display:flex;align-items:center;justify-content:center;min-height:100vh">'
            f'<div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:44px;width:380px;text-align:center">'
            f'<h1 style="background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:1.6rem;margin-bottom:24px">🛡 SiteGuard Admin</h1>'
            f'<form method=POST><input class=fc name=u placeholder="Логин" required style="margin-bottom:12px"><br>'
            f'<input class=fc type=password name=p placeholder="Пароль" required style="margin-bottom:16px"><br>'
            f'<button type=submit class="btn bp" style="width:100%;padding:13px">Войти</button>{err}</form>'
            f'</div></div></body></html>')

@app.route("/admin")
@app.route("/admin/")
@auth
def dashboard():
    rows = get_licenses()
    total  = len(rows)
    active = sum(1 for r in rows if r["is_active"])
    trial  = sum(1 for r in rows if r["plan"] == "trial")
    dead   = total - active
    tbl = "".join(
        f'<tr><td><span class=k>{r["license_key"]}</span></td>'
        f'<td>{r["organization"]}</td><td>{r["plan"].title()}</td>'
        f'<td><span class={"ba" if r["is_active"] else "bi"}>{"ACTIVE" if r["is_active"] else "REVOKED"}</span></td>'
        f'<td>{r["expires_at"].strftime("%Y-%m-%d") if r["expires_at"] else "—"}</td>'
        f'<td><form method=POST action=/admin/revoke style=display:inline>'
        f'<input type=hidden name=key value="{r["license_key"]}">'
        f'<button class="btn bs bd">Отозвать</button></form></td></tr>'
        for r in rows[:20]
    ) or "<tr><td colspan=6 style='text-align:center;color:#444;padding:28px'>Нет лицензий — создайте первую</td></tr>"

    body = (
        f'<div class=ph><h1>Обзор</h1><button class="btn bp" onclick="document.getElementById(\'cm\').classList.add(\'show\')">+ Создать лицензию</button></div>'
        f'<div class=stats>'
        f'<div class=st><div class=v>{total}</div><div class=l>Всего лицензий</div></div>'
        f'<div class=st><div class=v style="background:linear-gradient(135deg,#2ed573,#00b894);-webkit-background-clip:text">{active}</div><div class=l>Активных</div></div>'
        f'<div class=st><div class=v style="background:linear-gradient(135deg,#ffc107,#ff9800);-webkit-background-clip:text">{trial}</div><div class=l>Пробных</div></div>'
        f'<div class=st><div class=v style="background:linear-gradient(135deg,#ff4757,#e84393);-webkit-background-clip:text">{dead}</div><div class=l>Отозванных</div></div>'
        f'</div>'
        f'<div class=card>'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">'
        f'<span style="font-size:1.05rem;font-weight:700">Последние лицензии</span>'
        f'<a href=/admin/licenses class="btn bg bs">Все →</a></div>'
        f'<table><thead><tr><th>Ключ (кликните — скопировать)</th><th>Email</th><th>Тариф</th><th>Статус</th><th>Истекает</th><th>Действия</th></tr></thead>'
        f'<tbody>{tbl}</tbody></table></div>'
    )
    return page("Дашборд", "dash", body)

@app.route("/admin/licenses")
@auth
def licenses():
    rows = get_licenses()
    tbl = "".join(
        f'<tr><td><span class=k>{r["license_key"]}</span></td>'
        f'<td>{r["organization"]}</td><td>{r["plan"].title()}</td>'
        f'<td><span class={"ba" if r["is_active"] else "bi"}>{"ACTIVE" if r["is_active"] else "REVOKED"}</span></td>'
        f'<td>{r["max_sites"]}</td>'
        f'<td>{r["expires_at"].strftime("%Y-%m-%d") if r["expires_at"] else "—"}</td>'
        f'<td>{r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "—"}</td>'
        f'<td><form method=POST action=/admin/revoke style=display:inline>'
        f'<input type=hidden name=key value="{r["license_key"]}">'
        f'<button class="btn bs bd">Отозвать</button></form></td></tr>'
        for r in rows
    ) or "<tr><td colspan=8 style='text-align:center;color:#444;padding:28px'>Нет лицензий</td></tr>"

    body = (
        f'<div class=ph><h1>Лицензии</h1><button class="btn bp" onclick="document.getElementById(\'cm\').classList.add(\'show\')">+ Новая лицензия</button></div>'
        f'<div class=card>'
        f'<table><thead><tr><th>Ключ</th><th>Email</th><th>Тариф</th><th>Статус</th><th>Сайтов</th><th>Истекает</th><th>Создана</th><th>Действия</th></tr></thead>'
        f'<tbody>{tbl}</tbody></table></div>'
    )
    return page("Лицензии", "lic", body)

@app.route("/admin/create", methods=["POST"])
@auth
def create():
    email     = request.form.get("email", "")
    plan      = request.form.get("plan", "professional")
    days      = int(request.form.get("days", 365))
    max_sites = int(request.form.get("max_sites", 25))
    key, err  = create_license(email, plan, days, max_sites)
    if err:
        return f'<p style="color:#ff4757;padding:24px">Ошибка: {err} <a href=/admin/licenses style="color:#6c63ff">← Назад</a></p>'
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    return (f'<!DOCTYPE html><html><head><title>Ключ создан</title>{CSS}</head>'
            f'<body style="display:block"><div style="display:flex;align-items:center;justify-content:center;min-height:100vh">'
            f'<div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:40px;text-align:center;max-width:540px">'
            f'<div style="font-size:3rem">✅</div>'
            f'<h2 style="margin:16px 0 8px">Лицензия создана!</h2>'
            f'<p style="color:#888">Тариф: <b style="color:#e0e0ff">{plan.title()}</b> &nbsp;|&nbsp; Истекает: <b style="color:#e0e0ff">{expires}</b></p>'
            f'<div style="font-family:monospace;font-size:1.15rem;color:#6c63ff;background:rgba(108,99,255,.08);'
            f'border:2px solid #6c63ff;padding:16px;border-radius:8px;margin:20px 0;letter-spacing:2px;cursor:pointer;'
            f'word-break:break-all" onclick="navigator.clipboard.writeText(\'{key}\');this.style.color=\'#2ed573\'">{key}</div>'
            f'<p style="color:#555;font-size:.82rem">Кликните на ключ чтобы скопировать.<br>Ключ сохранён в PostgreSQL и работает офлайн.</p>'
            f'<a href=/admin/licenses class="btn bp" style="margin-top:16px">← Все лицензии</a>'
            f'</div></div>'
            f'<script>document.querySelector("[onclick]").addEventListener("click",function(){{setTimeout(()=>this.style.color="",1500)}})</script>'
            f'</body></html>')

@app.route("/admin/revoke", methods=["POST"])
@auth
def do_revoke():
    revoke(request.form.get("key", ""))
    return redirect(request.referrer or "/admin/licenses")

@app.route("/admin/stats")
@auth
def stats():
    rows = get_licenses()
    by_plan = {}
    for r in rows:
        by_plan[r["plan"]] = by_plan.get(r["plan"], 0) + 1
    tbl = "".join(f'<tr><td>{p.title()}</td><td>{c}</td></tr>' for p,c in by_plan.items()) \
          or "<tr><td colspan=2 style='color:#444;padding:16px'>Нет данных</td></tr>"
    body = (f'<div class=ph><h1>Статистика</h1></div>'
            f'<div class=card style="max-width:400px">'
            f'<table><thead><tr><th>Тариф</th><th>Количество</th></tr></thead><tbody>{tbl}</tbody></table>'
            f'<p style="margin-top:16px;color:#666">Всего: <b style="color:#e0e0ff">{len(rows)}</b></p></div>')
    return page("Статистика", "stats", body, modal=False)

@app.route("/admin/settings")
@auth
def settings():
    body = (f'<div class=ph><h1>Настройки</h1></div>'
            f'<div class=card style="max-width:560px">'
            f'<table style="border:none"><tr><td style="color:#555;border:none;padding:8px 0">Admin URL</td>'
            f'<td style="border:none;padding:8px 0"><a href="http://87.228.29.55/admin" style="color:#6c63ff">http://87.228.29.55/admin</a></td></tr>'
            f'<tr><td style="color:#555;border:none;padding:8px 0">API</td>'
            f'<td style="border:none;padding:8px 0"><a href="http://87.228.29.55/api/docs" style="color:#6c63ff">http://87.228.29.55/api/docs</a></td></tr>'
            f'<tr><td style="color:#555;border:none;padding:8px 0">Dashboard</td>'
            f'<td style="border:none;padding:8px 0"><a href="http://87.228.29.55/dashboard" style="color:#6c63ff">http://87.228.29.55/dashboard</a></td></tr>'
            f'<tr><td style="color:#555;border:none;padding:8px 0">Версия</td><td style="border:none;padding:8px 0">1.0.0</td></tr></table>'
            f'<p style="margin-top:20px;color:#555;font-size:.82rem">Активация ключей работает офлайн — проверка HMAC без сети.</p>'
            f'</div>')
    return page("Настройки", "set", body, modal=False)

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect("/admin/login")


# ─── Публичный API для приложений ─────────────────────────────────────────────

@app.route("/api/v1/license/validate", methods=["POST"])
@app.route("/api/v1/license/activate", methods=["POST"])
def api_license():
    """
    Опциональная серверная валидация ключа.
    Приложение работает и без этого эндпоинта (офлайн-режим).
    """
    data = request.get_json(silent=True) or {}
    key  = (data.get("license_key") or data.get("key") or "").strip().upper()
    if not key:
        return jsonify({"is_valid": False, "message": "license_key required"}), 400

    ok, plan_or_err = validate_key_local(key)
    if not ok:
        return jsonify({"is_valid": False, "message": plan_or_err}), 403

    # Дополнительно смотрим в БД для проверки отзыва
    row, err = lookup_key(key)
    if not row:
        # Ключ валиден по HMAC, но отозван или не найден в БД
        return jsonify({"is_valid": False, "message": err or "Ключ не найден"}), 403

    cfg = PLAN_CONFIG.get(row["plan"], {})
    expires = row["expires_at"].isoformat() if row.get("expires_at") else None
    days_left = 0
    if row.get("expires_at"):
        days_left = max(0, (row["expires_at"].replace(tzinfo=None) - datetime.datetime.utcnow()).days)

    return jsonify({
        "is_valid": True,
        "message": "License is valid",
        "plan": row["plan"],
        "label": cfg.get("label", row["plan"].title()),
        "max_sites": row["max_sites"],
        "expires_at": expires,
        "days_remaining": days_left,
        "features": row.get("features") or {},
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False)
