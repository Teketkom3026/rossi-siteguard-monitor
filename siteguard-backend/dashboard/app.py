"""
Web dashboard for site monitoring.
- Visualization by sitemap structure
- Green/red highlighting
- Red items float to the top with issue descriptions
"""
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
from typing import Dict, List
from functools import wraps
import json
import os
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('DASHBOARD_SECRET_KEY', 'siteguard-secret-key-change-me')
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple authentication credentials (override via environment)
DASHBOARD_USERNAME = os.environ.get('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'siteguard')


def login_required(f):
    """Decorator to require authentication for dashboard routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


class DashboardData:
    """In-memory data store for the dashboard."""

    def __init__(self):
        self.sites_status: Dict[str, dict] = {}
        self.alerts_history: List[dict] = []
        self.sitemap_trees: Dict[str, dict] = {}

    def update_site_status(self, domain: str, status: dict):
        """Update site status and push via WebSocket."""
        self.sites_status[domain] = {
            **status,
            'last_updated': datetime.now().isoformat()
        }
        socketio.emit('site_update', {
            'domain': domain,
            'status': self.sites_status[domain]
        })

    def add_alert(self, alert: dict):
        """Add an alert to the history."""
        alert['timestamp'] = datetime.now().isoformat()
        self.alerts_history.insert(0, alert)
        if len(self.alerts_history) > 1000:
            self.alerts_history = self.alerts_history[:1000]
        socketio.emit('new_alert', alert)

    def update_sitemap_tree(self, domain: str, tree: dict):
        """Update sitemap tree data."""
        self.sitemap_trees[domain] = tree
        socketio.emit('sitemap_update', {
            'domain': domain,
            'tree': tree
        })

    def get_sorted_sites(self) -> List[dict]:
        """Get sites sorted by severity: problematic sites first."""
        sites = []
        for domain, status in self.sites_status.items():
            sites.append({
                'domain': domain,
                **status
            })
        severity_order = {
            'critical': 0, 'high': 1, 'medium': 2,
            'low': 3, 'ok': 4
        }
        sites.sort(key=lambda s: (
            severity_order.get(s.get('overall_severity', 'ok'), 4),
            s.get('domain', '')
        ))
        return sites


# Global dashboard data instance
dashboard_data = DashboardData()


# ========================
# Authentication routes
# ========================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for dashboard authentication."""
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            session['username'] = username
            next_url = request.args.get('next', url_for('dashboard'))
            return redirect(next_url)
        error = 'Invalid credentials'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('login'))


# ========================
# Dashboard routes
# ========================

@app.route('/')
def index():
    """Redirect root to dashboard."""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page."""
    sites = dashboard_data.get_sorted_sites()
    return render_template('dashboard.html', sites=sites)


# ========================
# API routes
# ========================

@app.route('/api/sites')
@login_required
def api_sites():
    """API: list of sites with statuses."""
    return jsonify(dashboard_data.get_sorted_sites())


@app.route('/api/site/<domain>')
@login_required
def api_site_detail(domain):
    """API: detailed site status."""
    status = dashboard_data.sites_status.get(domain)
    tree = dashboard_data.sitemap_trees.get(domain)
    if not status:
        return jsonify({'error': 'Site not found'}), 404
    return jsonify({
        'domain': domain,
        'status': status,
        'sitemap_tree': tree
    })


@app.route('/api/alerts')
@login_required
def api_alerts():
    """API: alert history."""
    limit = request.args.get('limit', 50, type=int)
    domain = request.args.get('domain', None)
    alerts = dashboard_data.alerts_history
    if domain:
        alerts = [a for a in alerts if a.get('domain') == domain]
    return jsonify(alerts[:limit])


@app.route('/api/sitemap/<domain>')
@login_required
def api_sitemap(domain):
    """API: sitemap tree for visualization."""
    tree = dashboard_data.sitemap_trees.get(domain)
    if not tree:
        return jsonify({'error': 'Sitemap not found'}), 404
    return jsonify(tree)


# ========================
# WebSocket handlers
# ========================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection - send initial data."""
    emit('initial_data', {
        'sites': dashboard_data.get_sorted_sites(),
        'alerts': dashboard_data.alerts_history[:20]
    })


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """Start the dashboard server."""
    socketio.run(app, host=host, port=port, debug=debug)
