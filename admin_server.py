"""
Rossi SiteGuard Monitor — Admin Panel
Управление лицензиями с персистентным хранением в PostgreSQL.
"""
from flask import Flask, render_template_string, request, redirect, session, jsonify
import os, json, secrets, datetime, string, random, hashlib, hmac
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = 'siteguard_admin_secret_2024_SECURE_KEY'

ADMIN_USER = 'admin'
ADMIN_PASS = 'SiteGuard2024Admin!'

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'siteguard_db',
    'user': 'siteguard',
    'password': 'siteguard_pass_2024',
}

LICENSE_SECRET = os.getenv('LICENSE_SECRET', 'siteguard_license_secret_key_2024')

# ─── License key generation (format: SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM) ───────

def _calculate_checksum(key_without_check: str) -> str:
    """HMAC-based 5-char checksum — same algorithm as FastAPI LicenseKeyGenerator."""
    sig = hmac.new(
        LICENSE_SECRET.encode(),
        key_without_check.encode(),
        hashlib.sha256
    ).hexdigest().upper()
    return sig[:5]

def gen_key(plan: str) -> str:
    """Generate a key in SG-XXXXX-XXXXX-XXXXX-XXXXX-CHKSUM format."""
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(random.choices(chars, k=5)) for _ in range(4)]
    base = 'SG-' + '-'.join(parts)
    checksum = _calculate_checksum(base)
    return f'{base}-{checksum}'

# ─── DB helpers ───────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_licenses(limit=100):
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute('''
                    SELECT id, license_key, organization, plan, max_sites,
                           is_active, activated_at, expires_at, created_at, features
                    FROM licenses ORDER BY created_at DESC LIMIT %s
                ''', (limit,))
                return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f'DB error get_licenses: {e}')
        return []

def create_license_db(email, plan, days, max_sites):
    key = gen_key(plan)
    now = datetime.datetime.utcnow()
    expires = now + datetime.timedelta(days=days)
    features_map = {
        'trial':        {'availability_check': True,  'ssl_check': True,  'ui_tests': False, 'security_scan': False, 'api_access': False},
        'starter':      {'availability_check': True,  'ssl_check': True,  'ui_tests': True,  'security_scan': False, 'api_access': False},
        'professional': {'availability_check': True,  'ssl_check': True,  'ui_tests': True,  'security_scan': True,  'api_access': True},
        'business':     {'availability_check': True,  'ssl_check': True,  'ui_tests': True,  'security_scan': True,  'api_access': True},
        'enterprise':   {'availability_check': True,  'ssl_check': True,  'ui_tests': True,  'security_scan': True,  'api_access': True},
    }
    features = features_map.get(plan, {})
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO licenses (license_key, organization, plan, max_sites,
                                         is_active, activated_at, expires_at, features)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (key, email, plan, max_sites, True, now, expires, json.dumps(features)))
                row_id = cur.fetchone()[0]
            conn.commit()
        return key, None
    except Exception as e:
        return None, str(e)

def revoke_license_db(key):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE licenses SET is_active=FALSE WHERE license_key=%s', (key,))
            conn.commit()
        return True
    except Exception as e:
        print(f'DB error revoke: {e}')
        return False

def validate_key_db(key):
    """Used by /api/v1/license/validate — returns license info if valid."""
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute('''
                    SELECT license_key, organization, plan, max_sites,
                           is_active, expires_at, features
                    FROM licenses WHERE license_key = %s
                ''', (key,))
                row = cur.fetchone()
        if not row:
            return None, 'Key not found'
        row = dict(row)
        if not row['is_active']:
            return None, 'License revoked'
        if row['expires_at'] and row['expires_at'].replace(tzinfo=None) < datetime.datetime.utcnow():
            return None, 'License expired'
        return row, None
    except Exception as e:
        print(f'DB error validate: {e}')
        return None, str(e)

# ─── CSS shared ───────────────────────────────────────────────────────────────

CSS = """
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f0f23;color:#e0e0ff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:flex;min-height:100vh}
.sidebar{width:240px;background:#1a1a2e;border-right:1px solid #2a2a4a;padding:24px 0;flex-shrink:0;display:flex;flex-direction:column}
.logo{padding:0 24px 28px;border-bottom:1px solid #2a2a4a;margin-bottom:16px}
.logo h2{font-size:1.05rem;background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:700}
.logo span{font-size:.72rem;color:#555}
.nav-item{display:flex;align-items:center;gap:12px;padding:11px 24px;border-left:3px solid transparent;color:#888;text-decoration:none;font-size:.88rem;transition:.15s}
.nav-item:hover,.nav-item.active{background:rgba(108,99,255,.1);border-left-color:#6c63ff;color:#e0e0ff}
.sidebar-bottom{margin-top:auto;padding:16px 24px;border-top:1px solid #2a2a4a}
.main{flex:1;overflow-y:auto;padding:32px}
.ph{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}
.ph h1{font-size:1.55rem;font-weight:700}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:28px}
.stat{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:12px;padding:22px}
.stat .val{font-size:1.9rem;font-weight:700;background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat .lbl{color:#888;font-size:.82rem;margin-top:4px}
.card{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:12px;padding:24px;margin-bottom:22px}
.ch{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.ct{font-size:1.05rem;font-weight:600}
.btn{padding:9px 18px;border:none;border-radius:8px;cursor:pointer;font-size:.87rem;font-weight:600;text-decoration:none;display:inline-block}
.btn-p{background:linear-gradient(135deg,#6c63ff,#e040fb);color:#fff}
.btn-sm{padding:5px 12px;font-size:.78rem}
.btn-d{background:#ff4757;color:#fff}
.btn-g{background:#252540;color:#aaa}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:10px 14px;border-bottom:2px solid #2a2a4a;color:#666;font-size:.77rem;text-transform:uppercase;letter-spacing:.05em}
td{padding:11px 14px;border-bottom:1px solid #1e1e3a;font-size:.87rem}
tr:hover td{background:rgba(108,99,255,.04)}
.ba{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.72rem;font-weight:700;background:rgba(46,213,115,.12);color:#2ed573}
.bi{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.72rem;font-weight:700;background:rgba(255,71,87,.12);color:#ff4757}
.k{font-family:monospace;font-size:.82rem;color:#6c63ff;background:rgba(108,99,255,.08);padding:2px 7px;border-radius:4px}
input.fc,select.fc{width:100%;padding:9px 12px;background:#252540;border:1px solid #333;border-radius:7px;color:#fff;font-size:.88rem;outline:none}
input.fc:focus,select.fc:focus{border-color:#6c63ff}
.fr{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.fg{margin-bottom:14px}
.fg label{display:block;margin-bottom:5px;font-size:.82rem;color:#aaa}
.mb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;align-items:center;justify-content:center}
.mb.show{display:flex}
.mc{background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:30px;width:500px;max-width:94vw}
.mh{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}
.xb{background:none;border:none;color:#666;font-size:1.4rem;cursor:pointer;line-height:1}
</style>
"""

def sidebar(active):
    items = [
        ('dash',  '/admin',          '📊', 'Дашборд'),
        ('lic',   '/admin/licenses', '🔑', 'Лицензии'),
        ('stats', '/admin/stats',    '📈', 'Статистика'),
        ('set',   '/admin/settings', '⚙️',  'Настройки'),
    ]
    links = ''
    for key, url, icon, label in items:
        cls = 'nav-item active' if key == active else 'nav-item'
        links += f'<a class="{cls}" href="{url}">{icon} {label}</a>'
    return f'''<nav class=sidebar>
  <div class=logo><h2>🛡 SiteGuard</h2><span>Admin Panel v1.0</span></div>
  {links}
  <a class="nav-item" href="/" target=_blank>🌐 Сайт</a>
  <div class=sidebar-bottom><a class=nav-item href="/admin/logout" style="padding:0;color:#666">🚪 Выйти</a></div>
</nav>'''

def create_modal():
    return '''<div class=mb id=cm>
  <div class=mc>
    <div class=mh><h2>Создать лицензию</h2><button class=xb onclick="document.getElementById('cm').classList.remove('show')">&#x2715;</button></div>
    <form method=POST action=/admin/create-license>
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
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px">
        <button type=button class="btn btn-g" onclick="document.getElementById('cm').classList.remove('show')">Отмена</button>
        <button type=submit class="btn btn-p">Создать ключ</button>
      </div>
    </form>
  </div>
</div>'''

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('ok'):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return wrapper

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET','POST'])
def login():
    err = ''
    if request.method == 'POST':
        if request.form.get('u') == ADMIN_USER and request.form.get('p') == ADMIN_PASS:
            session['ok'] = True
            return redirect('/admin/')
        err = 'Неверный логин или пароль'
    return (
        '<!DOCTYPE html><html><head><title>SiteGuard Admin</title>' + CSS + '</head>'
        '<body style="display:block"><div style="display:flex;align-items:center;justify-content:center;min-height:100vh">'
        '<div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:44px;width:380px;text-align:center">'
        '<h1 style="font-size:1.7rem;margin-bottom:6px;background:linear-gradient(135deg,#6c63ff,#e040fb);-webkit-background-clip:text;-webkit-text-fill-color:transparent">🛡 SiteGuard Admin</h1>'
        '<p style="color:#666;margin-bottom:28px;font-size:.9rem">Rossi SiteGuard Monitor</p>'
        '<form method=POST>'
        '<input class=fc name=u placeholder="Логин" required style="margin-bottom:13px"><br>'
        '<input class=fc type=password name=p placeholder="Пароль" required style="margin-bottom:13px"><br>'
        '<button type=submit class="btn btn-p" style="width:100%;padding:13px;font-size:1rem">Войти</button>'
        + (f'<div style="color:#ff4757;margin-top:10px;font-size:.85rem">{err}</div>' if err else '') +
        '</form></div></div></body></html>'
    )

@app.route('/admin')
@app.route('/admin/')
@login_required
def dashboard():
    rows = get_licenses(500)
    total   = len(rows)
    active  = sum(1 for r in rows if r['is_active'])
    trial   = sum(1 for r in rows if r['plan'] == 'trial')
    expired = sum(1 for r in rows if not r['is_active'])

    tbl_rows = []
    for r in rows[:15]:
        badge_cls = 'ba' if r['is_active'] else 'bi'
        status_txt = 'ACTIVE' if r['is_active'] else 'REVOKED'
        exp = r['expires_at'].strftime('%Y-%m-%d') if r['expires_at'] else '—'
        tbl_rows.append(
            '<tr>'
            f'<td><span class=k>{r["license_key"]}</span></td>'
            f'<td>{r["organization"]}</td>'
            f'<td>{r["plan"].title()}</td>'
            f'<td><span class={badge_cls}>{status_txt}</span></td>'
            f'<td>{exp}</td>'
            '<td><form method=POST action=/admin/revoke style="display:inline">'
            f'<input type=hidden name=key value="{r["license_key"]}">'
            '<button class="btn btn-sm btn-d" type=submit>Отозвать</button>'
            '</form></td>'
            '</tr>'
        )
    tbl = ''.join(tbl_rows) or '<tr><td colspan=6 style="text-align:center;color:#444;padding:28px">Лицензий пока нет. Создайте первую!</td></tr>'

    return (
        '<!DOCTYPE html><html><head><title>SiteGuard Admin</title>' + CSS + '</head><body>'
        + sidebar('dash') +
        '<main class=main>'
        '<div class=ph><h1>Обзор</h1>'
        '<button class="btn btn-p" onclick="document.getElementById(\'cm\').classList.add(\'show\')">+ Создать лицензию</button>'
        '</div>'
        '<div class=stats>'
        f'<div class=stat><div class=val>{total}</div><div class=lbl>Всего лицензий</div></div>'
        f'<div class=stat><div class=val style="background:linear-gradient(135deg,#2ed573,#00b894);-webkit-background-clip:text">{active}</div><div class=lbl>Активных</div></div>'
        f'<div class=stat><div class=val style="background:linear-gradient(135deg,#ffc107,#ff9800);-webkit-background-clip:text">{trial}</div><div class=lbl>Пробных</div></div>'
        f'<div class=stat><div class=val style="background:linear-gradient(135deg,#ff4757,#e84393);-webkit-background-clip:text">{expired}</div><div class=lbl>Отозванных</div></div>'
        '</div>'
        '<div class=card>'
        '<div class=ch><span class=ct>Последние лицензии</span><a href=/admin/licenses class="btn btn-g btn-sm">Все →</a></div>'
        '<table><thead><tr><th>Ключ</th><th>Email</th><th>Тариф</th><th>Статус</th><th>Истекает</th><th>Действия</th></tr></thead>'
        f'<tbody>{tbl}</tbody></table></div>'
        '</main>'
        + create_modal() +
        '</body></html>'
    )

@app.route('/admin/licenses')
@login_required
def licenses_page():
    rows = get_licenses(500)
    tbl_rows = []
    for r in rows:
        badge_cls = 'ba' if r['is_active'] else 'bi'
        status_txt = 'ACTIVE' if r['is_active'] else 'REVOKED'
        exp = r['expires_at'].strftime('%Y-%m-%d') if r['expires_at'] else '—'
        created = r['created_at'].strftime('%Y-%m-%d') if r['created_at'] else '—'
        tbl_rows.append(
            '<tr>'
            f'<td><span class=k>{r["license_key"]}</span></td>'
            f'<td>{r["organization"]}</td>'
            f'<td>{r["plan"].title()}</td>'
            f'<td><span class={badge_cls}>{status_txt}</span></td>'
            f'<td>{r["max_sites"]}</td>'
            f'<td>{exp}</td>'
            f'<td>{created}</td>'
            '<td><form method=POST action=/admin/revoke style="display:inline">'
            f'<input type=hidden name=key value="{r["license_key"]}">'
            '<button class="btn btn-sm btn-d" type=submit>Отозвать</button>'
            '</form></td>'
            '</tr>'
        )
    tbl = ''.join(tbl_rows) or '<tr><td colspan=8 style="text-align:center;color:#444;padding:28px">Нет лицензий</td></tr>'

    return (
        '<!DOCTYPE html><html><head><title>Лицензии — SiteGuard</title>' + CSS + '</head><body>'
        + sidebar('lic') +
        '<main class=main>'
        '<div class=ph><h1>Управление лицензиями</h1>'
        '<button class="btn btn-p" onclick="document.getElementById(\'cm\').classList.add(\'show\')">+ Новая лицензия</button>'
        '</div>'
        '<div class=card>'
        '<table><thead><tr><th>Ключ</th><th>Email</th><th>Тариф</th><th>Статус</th><th>Сайтов</th><th>Истекает</th><th>Создана</th><th>Действия</th></tr></thead>'
        f'<tbody>{tbl}</tbody></table></div>'
        '</main>'
        + create_modal() +
        '</body></html>'
    )

@app.route('/admin/create-license', methods=['POST'])
@login_required
def create_license():
    email     = request.form.get('email', 'admin@siteguard.local')
    plan      = request.form.get('plan', 'professional')
    days      = int(request.form.get('days', 365))
    max_sites = int(request.form.get('max_sites', 25))
    key, err  = create_license_db(email, plan, days, max_sites)
    if err:
        return f'<p style="color:red;padding:20px">Ошибка: {err} <a href=/admin/licenses style="color:#6c63ff">Назад</a></p>'
    expires = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    return (
        '<!DOCTYPE html><html><head><title>Лицензия создана</title>' + CSS + '</head>'
        '<body style="display:block"><div style="display:flex;align-items:center;justify-content:center;min-height:100vh">'
        '<div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:14px;padding:40px;text-align:center;max-width:520px">'
        '<div style="font-size:2.5rem">&#x2705;</div>'
        '<h2 style="margin:12px 0">Лицензия создана!</h2>'
        f'<p>Email: <b>{email}</b> &nbsp;|&nbsp; Тариф: <b>{plan.title()}</b> &nbsp;|&nbsp; Истекает: <b>{expires}</b></p>'
        f'<div style="font-family:monospace;font-size:1.15rem;color:#6c63ff;background:rgba(108,99,255,.1);border:2px solid #6c63ff;padding:14px 20px;border-radius:8px;margin:18px 0;letter-spacing:3px;word-break:break-all">{key}</div>'
        '<p style="color:#666;font-size:.82rem">Скопируйте ключ и передайте пользователю.<br>Он сохранён в базе данных PostgreSQL.</p>'
        '<a href=/admin/licenses class="btn btn-p" style="margin-top:14px">&#x2190; Все лицензии</a>'
        '</div></div></body></html>'
    )

@app.route('/admin/revoke', methods=['POST'])
@login_required
def revoke():
    key = request.form.get('key')
    if key:
        revoke_license_db(key)
    return redirect(request.referrer or '/admin/licenses')

@app.route('/admin/stats')
@login_required
def stats():
    rows = get_licenses(500)
    by_plan = {}
    for r in rows:
        by_plan[r['plan']] = by_plan.get(r['plan'], 0) + 1
    tbl_rows = ''.join(f'<tr><td>{p.title()}</td><td>{c}</td></tr>' for p, c in by_plan.items())
    tbl = tbl_rows or '<tr><td colspan=2 style="color:#444;padding:20px">Нет данных</td></tr>'
    return (
        '<!DOCTYPE html><html><head><title>Статистика</title>' + CSS + '</head><body>'
        + sidebar('stats') +
        '<main class=main>'
        '<div class=ph><h1>Статистика</h1></div>'
        '<div class=card><div class=ct style="margin-bottom:16px">Лицензии по тарифам</div>'
        '<table><thead><tr><th>Тариф</th><th>Количество</th></tr></thead>'
        f'<tbody>{tbl}</tbody></table>'
        f'<p style="margin-top:16px;color:#666">Всего лицензий: <b>{len(rows)}</b></p>'
        '</div></main></body></html>'
    )

@app.route('/admin/settings')
@login_required
def settings_page():
    return (
        '<!DOCTYPE html><html><head><title>Настройки</title>' + CSS + '</head><body>'
        + sidebar('set') +
        '<main class=main>'
        '<div class=ph><h1>Настройки</h1></div>'
        '<div class=card style="max-width:560px">'
        '<p><b>Версия:</b> 1.0.0</p>'
        '<p style="margin-top:12px"><b>Admin URL:</b> <a href="http://87.228.29.55/admin" style="color:#6c63ff">http://87.228.29.55/admin</a></p>'
        '<p style="margin-top:12px"><b>API URL:</b> <a href="http://87.228.29.55/api/docs" style="color:#6c63ff">http://87.228.29.55/api/docs</a></p>'
        '<p style="margin-top:12px"><b>Dashboard:</b> <a href="http://87.228.29.55/dashboard" style="color:#6c63ff">http://87.228.29.55/dashboard</a></p>'
        '<p style="margin-top:16px;color:#666;font-size:.85rem">Для смены пароля отредактируйте ADMIN_PASS в /opt/siteguard/admin_server.py</p>'
        '</div></main></body></html>'
    )

@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect('/admin/login')

# ─── Public API: license validation (called by desktop & Android app) ─────────

@app.route('/api/v1/license/validate', methods=['POST'])
def api_validate():
    """
    Public endpoint for client apps to validate a license key.
    Accepts JSON with 'license_key' or 'key' field.
    """
    data = request.get_json(silent=True) or {}
    key = data.get('license_key') or data.get('key', '')
    if not key:
        return jsonify({'valid': False, 'error': 'license_key required'}), 400
    row, err = validate_key_db(key)
    if not row:
        return jsonify({'valid': False, 'error': err}), 403
    exp = row['expires_at'].isoformat() if row['expires_at'] else None
    days = (row['expires_at'].replace(tzinfo=None) - datetime.datetime.utcnow()).days if row['expires_at'] else 0
    return jsonify({
        'valid': True,
        'is_valid': True,
        'plan': row['plan'],
        'max_sites': row['max_sites'],
        'expires_at': exp,
        'days_remaining': max(0, days),
        'features': row['features'] or {},
    })

@app.route('/api/v1/license/activate', methods=['POST'])
def api_activate():
    """
    Desktop/Android activation call.
    Accepts JSON with 'license_key', optional 'device_id'.
    """
    data = request.get_json(silent=True) or {}
    key = data.get('license_key') or data.get('key', '')
    if not key:
        return jsonify({'is_valid': False, 'message': 'license_key required'}), 400
    row, err = validate_key_db(key)
    if not row:
        return jsonify({'is_valid': False, 'message': err}), 403
    exp = row['expires_at'].isoformat() if row['expires_at'] else None
    days = (row['expires_at'].replace(tzinfo=None) - datetime.datetime.utcnow()).days if row['expires_at'] else 0
    return jsonify({
        'is_valid': True,
        'message': 'License activated successfully',
        'plan': row['plan'],
        'max_sites': row['max_sites'],
        'expires_at': exp,
        'days_remaining': max(0, days),
        'features': row['features'] or {},
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=False)
