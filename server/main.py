from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timezone
from pathlib import Path
import csv, io, json
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import LRUCache

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / 'data' / 'swarm.json'
AGENTS_FILE = BASE / 'server' / 'agents.json'
REPORTS_DIR = BASE / 'server' / 'reports'

app = FastAPI(title='Halo Dashboard API')

class _SafeJinjaEnv(Environment):
    def __init__(self, **kwargs):
        kwargs.setdefault('cache_size', 0)
        super().__init__(**kwargs)

    def _load_template(self, name, globals=None):
        if self.loader is None:
            raise TypeError('no loader for this environment specified')
        return self.loader.load(self, name, self.make_globals(globals))

_loader = FileSystemLoader(str(BASE / 'server' / 'templates'))
_env = _SafeJinjaEnv(loader=_loader)

def _render(name, context):
    tpl = _env.get_template(name)
    return HTMLResponse(tpl.render(context))

app.add_middleware(
    SessionMiddleware,
    secret_key='halo-local-dev-secret-change-me',
    max_age=3600 * 24 * 7,
)

for d in [AGENTS_FILE.parent, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

if not AGENTS_FILE.exists():
    AGENTS_FILE.write_text(json.dumps({
        'moo': {'password': None, 'role': 'orchestrator', 'active': True},
        'veles': {'password': None, 'role': 'research', 'active': True},
        'cmok': {'password': None, 'role': 'build', 'active': True},
        'bagnik': {'password': None, 'role': 'qa', 'active': True},
        'zlydni': {'password': None, 'role': 'commit', 'active': True},
        'mokash': {'password': None, 'role': 'docs', 'active': True},
    }, indent=2) + '\n')


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2) + '\n')


def is_admin(request: Request) -> bool:
    state = request.session.get('auth')
    return bool(state and state.get('role') == 'admin')


def is_agent(request: Request) -> bool:
    state = request.session.get('auth')
    return bool(state and state.get('role') in {'admin', 'agent'})


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return _render('dashboard.html', {
        'request': request,
        'title': 'Halo',
        'api_prefix': '/api',
        'auth': request.session.get('auth'),
    })


@app.get('/admin', response_class=HTMLResponse)
async def admin(request: Request):
    return _render('admin.html', {
        'request': request,
        'title': 'Halo Admin',
        'api_prefix': '/api',
        'auth': request.session.get('auth'),
    })


# Auth
@app.post('/api/auth/login')
async def login(request: Request):
    body = await request.json()
    username = (body.get('username') or '').strip()
    password = (body.get('password') or '').strip()
    agents = json.loads(AGENTS_FILE.read_text())
    record = agents.get(username)
    if not record:
        return JSONResponse({'ok': False, 'error': 'not_found'}, status_code=404)
    if record.get('password') and record['password'] != password:
        return JSONResponse({'ok': False, 'error': 'invalid_password'}, status_code=401)
    role = record.get('role', 'agent')
    active = record.get('active', True)
    request.session['auth'] = {'username': username, 'role': role, 'active': active}
    return {'ok': True, 'username': username, 'role': role, 'active': active}


@app.post('/api/auth/logout')
async def logout(request: Request):
    request.session.pop('auth', None)
    return {'ok': True}


@app.get('/api/auth/whoami')
async def whoami(request: Request):
    state = request.session.get('auth')
    if not state:
        return JSONResponse({'ok': False}, status_code=401)
    return {'ok': True, **state}


# Admin agents CRUD
@app.get('/api/admin/agents')
async def list_agents(request: Request):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    agents = json.loads(AGENTS_FILE.read_text())
    items = []
    for name, record in agents.items():
        items.append({
            'username': name,
            'role': record.get('role', 'agent'),
            'active': record.get('active', True),
            'has_password': bool(record.get('password')),
        })
    return {'ok': True, 'agents': sorted(items, key=lambda x: x['username'])}


@app.post('/api/admin/agents')
async def upsert_agent(request: Request):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    payload = await request.json()
    username = (payload.get('username') or '').strip().lower()
    if not username:
        return JSONResponse({'ok': False, 'error': 'username_required'}, status_code=400)
    role = (payload.get('role') or 'agent').strip() or 'agent'
    password = payload.get('password')
    active = payload.get('active')
    agents = json.loads(AGENTS_FILE.read_text())
    record = agents.setdefault(username, {})
    if isinstance(password, str) and password:
        record['password'] = password
    if role:
        record['role'] = role
    if active is not None:
        record['active'] = bool(active)
    AGENTS_FILE.write_text(json.dumps(agents, indent=2) + '\n')
    return {'ok': True}


@app.delete('/api/admin/agents/{username}')
async def delete_agent(request: Request, username: str):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    agents = json.loads(AGENTS_FILE.read_text())
    removed = agents.pop(username, None) is not None
    AGENTS_FILE.write_text(json.dumps(agents, indent=2) + '\n')
    return {'ok': True, 'removed': removed}


# Lock status
@app.get('/api/admin/lock')
async def lock_status(request: Request):
    if not is_agent(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    data = load_data()
    lock = (data.get('system') or {}).get('lock')
    return {'ok': True, 'lock': lock}


@app.post('/api/admin/lock')
async def set_lock(request: Request):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    payload = await request.json()
    value = payload.get('lock')
    data = load_data()
    data.setdefault('system', {})['lock'] = value if value in {True, False} else bool(value)
    save_data(data)
    return {'ok': True, 'lock': data['system']['lock']}


# Per-agent report
@app.post('/api/agents/{username}/report')
async def submit_report(request: Request, username: str):
    payload = await request.json()
    state = request.session.get('auth')
    if not state or state.get('username') != username:
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    if not is_agent(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    ts = datetime.now(timezone.utc).isoformat()
    report = {
        'reported_at': ts,
        'agent': username,
        'text': (payload.get('text') or '').strip(),
        'attachments': payload.get('attachments') or [],
        'extra': payload.get('extra') or {},
    }
    if not report['text']:
        return JSONResponse({'ok': False, 'error': 'text_required'}, status_code=400)
    path = REPORTS_DIR / f'{username}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as file:
        file.write(json.dumps(report, ensure_ascii=False) + '\n')
    data = load_data()
    agents = data.get('agents', [])
    match = [a for a in agents if a.get('name') == username]
    if match:
        match[0]['last_active'] = ts
        match[0]['status'] = 'active'
    else:
        agents.append({
            'name': username, 'emoji': '🤖', 'role': state.get('role') or 'agent',
            'status': 'active', 'last_active': ts, 'sessions_24h': 0, 'tokens_24h': 0,
        })
    data['agents'] = agents
    save_data(data)
    return {'ok': True}


@app.get('/api/admin/reports')
async def list_reports(request: Request):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    items = []
    for path in sorted(REPORTS_DIR.glob('*.jsonl')):
        try:
            with path.open('r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        except Exception:
            pass
    items = sorted(items, key=lambda x: x.get('reported_at', ''), reverse=True)
    return {'ok': True, 'reports': items}


@app.get('/api/admin/reports.csv')
async def export_reports_csv(request: Request):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    items = []
    for path in sorted(REPORTS_DIR.glob('*.jsonl')):
        try:
            with path.open('r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line:
                        items.append(json.loads(line))
        except Exception:
            pass
    items = sorted(items, key=lambda x: x.get('reported_at', ''), reverse=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=['reported_at', 'agent', 'text'])
    writer.writeheader()
    for item in items:
        writer.writerow({k: item.get(k, '') for k in ['reported_at', 'agent', 'text']})
    from fastapi.responses import Response
    return Response(content=buffer.getvalue(), media_type='text/csv')


@app.get('/api/admin/reports/{username}')
async def list_agent_reports(request: Request, username: str):
    if not is_admin(request):
        return JSONResponse({'ok': False, 'error': 'forbidden'}, status_code=403)
    path = REPORTS_DIR / f'{username}.jsonl'
    items = []
    if path.exists():
        with path.open('r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
    items = sorted(items, key=lambda x: x.get('reported_at', ''), reverse=True)
    return {'ok': True, 'reports': items}
