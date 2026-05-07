#!/usr/bin/env python3
"""
Bundesliga Tippspiel - Web App

Verwendet Python's eingebauten HTTP-Server (keine externen Dependencies).
Startet einen lokalen Webserver und oeffnet den Browser.

Verwendung: python3 webapp.py
"""

import http.server
import socketserver
import json
import webbrowser
import threading
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime

# Projektpfad
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tippspiel.app import TippspielApp

# Globale Tippspiel-Instanz
tippspiel = None

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bundesliga Tippspiel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            padding: 30px 0;
            margin-bottom: 30px;
        }

        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .subtitle {
            color: #888;
            font-size: 1.1em;
        }

        .update-info {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }

        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        button.secondary {
            background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }

        .tab {
            background: transparent;
            border: 2px solid #444;
            color: #888;
            padding: 10px 25px;
            border-radius: 20px;
        }

        .tab.active {
            background: linear-gradient(135deg, #00d4ff 0%, #00ff88 100%);
            border-color: transparent;
            color: #1a1a2e;
            font-weight: bold;
        }

        .content {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
        }

        .prediction-card {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .prediction-card.high { border-left-color: #00ff88; }
        .prediction-card.medium { border-left-color: #ffd700; }
        .prediction-card.low { border-left-color: #ff6b6b; }

        .match-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .teams {
            font-size: 1.2em;
            font-weight: 600;
        }

        .tip-badge {
            background: linear-gradient(135deg, #00d4ff 0%, #00ff88 100%);
            color: #1a1a2e;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.3em;
        }

        .probabilities {
            display: flex;
            gap: 20px;
            margin: 15px 0;
            flex-wrap: wrap;
        }

        .prob {
            text-align: center;
            min-width: 60px;
        }

        .prob-label {
            color: #888;
            font-size: 0.85em;
        }

        .prob-value {
            font-size: 1.4em;
            font-weight: bold;
        }

        .prob-value.highlight {
            color: #00ff88;
        }

        .explanation {
            background: rgba(0,0,0,0.2);
            padding: 12px;
            border-radius: 8px;
            font-size: 0.9em;
            color: #aaa;
            white-space: pre-line;
            margin-top: 10px;
        }

        .confidence {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-top: 10px;
        }

        .confidence.high { background: #00ff88; color: #1a1a2e; }
        .confidence.medium { background: #ffd700; color: #1a1a2e; }
        .confidence.low { background: #ff6b6b; color: #fff; }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid #333;
        }

        th {
            color: #888;
            font-weight: 500;
            font-size: 0.9em;
        }

        tr:hover {
            background: rgba(255,255,255,0.05);
        }

        .pos-1, .pos-2, .pos-3 { color: #00ff88; font-weight: bold; }
        .pos-16, .pos-17, .pos-18 { color: #ff6b6b; }

        .loading {
            text-align: center;
            padding: 50px;
            color: #888;
        }

        .spinner {
            border: 3px solid #333;
            border-top: 3px solid #00d4ff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .news-item {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }

        .news-source {
            color: #00d4ff;
            font-size: 0.8em;
            margin-bottom: 5px;
        }

        .news-team {
            background: #333;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            margin-left: 10px;
        }

        .sentiment-positive { color: #00ff88; }
        .sentiment-negative { color: #ff6b6b; }

        .error-msg {
            color: #ff6b6b;
            text-align: center;
            padding: 20px;
        }

        @media (max-width: 768px) {
            h1 { font-size: 1.8em; }
            .teams { font-size: 1em; }
            th, td { padding: 8px 4px; font-size: 0.85em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Bundesliga Tippspiel</h1>
            <p class="subtitle">Prognosen mit Elo + xG + Sentiment</p>
            <p class="update-info" id="updateInfo">Lade...</p>
        </header>

        <div class="controls">
            <button onclick="updateData()" id="updateBtn">Daten aktualisieren</button>
            <button onclick="loadPredictions()" class="secondary">Neu laden</button>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('predictions', this)">Prognosen</button>
            <button class="tab" onclick="showTab('table', this)">Tabelle</button>
            <button class="tab" onclick="showTab('news', this)">News</button>
        </div>

        <div id="predictions" class="content">
            <div class="loading">
                <div class="spinner"></div>
                <p>Lade Prognosen...</p>
            </div>
        </div>

        <div id="table" class="content" style="display:none;">
        </div>

        <div id="news" class="content" style="display:none;">
        </div>
    </div>

    <script>
        let currentTab = 'predictions';

        function showTab(tab, btn) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.content').forEach(c => c.style.display = 'none');

            btn.classList.add('active');
            document.getElementById(tab).style.display = 'block';
            currentTab = tab;

            if (tab === 'predictions') loadPredictions();
            else if (tab === 'table') loadTable();
            else if (tab === 'news') loadNews();
        }

        async function updateData() {
            const btn = document.getElementById('updateBtn');
            btn.disabled = true;
            btn.textContent = 'Aktualisiere...';

            try {
                const resp = await fetch('/api/update', {method: 'POST'});
                const data = await resp.json();

                if (data.success) {
                    btn.textContent = 'Fertig!';
                    document.getElementById('updateInfo').textContent =
                        'Letzte Aktualisierung: ' + new Date().toLocaleString('de-DE');
                    loadPredictions();

                    setTimeout(() => {
                        btn.textContent = 'Daten aktualisieren';
                        btn.disabled = false;
                    }, 2000);
                } else {
                    throw new Error(data.error || 'Unbekannter Fehler');
                }
            } catch (e) {
                btn.textContent = 'Fehler!';
                console.error(e);
                setTimeout(() => {
                    btn.textContent = 'Daten aktualisieren';
                    btn.disabled = false;
                }, 2000);
            }
        }

        async function loadPredictions() {
            const container = document.getElementById('predictions');
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Lade Prognosen...</p></div>';

            try {
                const resp = await fetch('/api/predictions');
                const data = await resp.json();

                if (!data.predictions || data.predictions.length === 0) {
                    container.innerHTML = '<p class="error-msg">Keine anstehenden Spiele gefunden. Klicke auf "Daten aktualisieren".</p>';
                    return;
                }

                let html = '';
                for (const p of data.predictions) {
                    const maxProb = Math.max(p.prob_home, p.prob_draw, p.prob_away);
                    html += '<div class="prediction-card ' + p.confidence + '">' +
                        '<div class="match-header">' +
                            '<span class="teams">' + p.home_team + ' vs ' + p.away_team + '</span>' +
                            '<span class="tip-badge">' + p.score + '</span>' +
                        '</div>' +
                        '<div class="probabilities">' +
                            '<div class="prob">' +
                                '<div class="prob-label">Heim</div>' +
                                '<div class="prob-value ' + (p.prob_home >= maxProb - 0.01 ? 'highlight' : '') + '">' + Math.round(p.prob_home * 100) + '%</div>' +
                            '</div>' +
                            '<div class="prob">' +
                                '<div class="prob-label">Remis</div>' +
                                '<div class="prob-value ' + (p.prob_draw >= maxProb - 0.01 ? 'highlight' : '') + '">' + Math.round(p.prob_draw * 100) + '%</div>' +
                            '</div>' +
                            '<div class="prob">' +
                                '<div class="prob-label">Ausw.</div>' +
                                '<div class="prob-value ' + (p.prob_away >= maxProb - 0.01 ? 'highlight' : '') + '">' + Math.round(p.prob_away * 100) + '%</div>' +
                            '</div>' +
                        '</div>' +
                        '<div class="explanation">' + p.explanation + '</div>' +
                        '<span class="confidence ' + p.confidence + '">Konfidenz: ' + p.confidence + '</span>' +
                    '</div>';
                }
                container.innerHTML = html;

            } catch (e) {
                container.innerHTML = '<p class="error-msg">Fehler beim Laden: ' + e.message + '</p>';
                console.error(e);
            }
        }

        async function loadTable() {
            const container = document.getElementById('table');
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Lade Tabelle...</p></div>';

            try {
                const resp = await fetch('/api/table');
                const data = await resp.json();

                let html = '<table><thead><tr>' +
                    '<th>#</th><th>Team</th><th>Sp</th><th>S</th><th>U</th><th>N</th><th>Diff</th><th>Pkt</th><th>Elo</th>' +
                    '</tr></thead><tbody>';

                for (const t of data.table) {
                    const posClass = t.position <= 3 ? 'pos-' + t.position : (t.position >= 16 ? 'pos-' + t.position : '');
                    const diff = t.goal_diff > 0 ? '+' + t.goal_diff : t.goal_diff;
                    html += '<tr class="' + posClass + '">' +
                        '<td>' + t.position + '</td>' +
                        '<td>' + t.team_name + '</td>' +
                        '<td>' + t.played + '</td>' +
                        '<td>' + t.won + '</td>' +
                        '<td>' + t.drawn + '</td>' +
                        '<td>' + t.lost + '</td>' +
                        '<td>' + diff + '</td>' +
                        '<td><strong>' + t.points + '</strong></td>' +
                        '<td>' + Math.round(t.elo) + '</td>' +
                    '</tr>';
                }

                html += '</tbody></table>';
                container.innerHTML = html;

            } catch (e) {
                container.innerHTML = '<p class="error-msg">Fehler beim Laden der Tabelle.</p>';
                console.error(e);
            }
        }

        async function loadNews() {
            const container = document.getElementById('news');
            container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Lade News...</p></div>';

            try {
                const resp = await fetch('/api/news');
                const data = await resp.json();

                if (!data.news || data.news.length === 0) {
                    container.innerHTML = '<p class="error-msg">Keine aktuellen News.</p>';
                    return;
                }

                let html = '';
                for (const n of data.news.slice(0, 20)) {
                    const sentimentClass = n.sentiment > 0.1 ? 'sentiment-positive' : (n.sentiment < -0.1 ? 'sentiment-negative' : '');
                    html += '<div class="news-item">' +
                        '<div class="news-source">' + n.source.toUpperCase() + '</div>' +
                        '<div class="' + sentimentClass + '">' + n.title + '</div>' +
                    '</div>';
                }
                container.innerHTML = html;

            } catch (e) {
                container.innerHTML = '<p class="error-msg">Fehler beim Laden der News.</p>';
                console.error(e);
            }
        }

        // Initial laden
        window.onload = function() {
            loadPredictions();
            document.getElementById('updateInfo').textContent = 'Bereit - ' + new Date().toLocaleString('de-DE');
        };
    </script>
</body>
</html>
"""


class TippspielHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP Request Handler fuer die Tippspiel Web-App."""

    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/index.html':
            self._send_html(HTML_TEMPLATE)

        elif path == '/api/predictions':
            self._send_json(self._get_predictions())

        elif path == '/api/table':
            self._send_json(self._get_table())

        elif path == '/api/news':
            self._send_json(self._get_news())

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/update':
            self._send_json(self._do_update())
        else:
            self.send_error(404, "Not Found")

    def _send_html(self, content):
        """Send HTML response."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _send_json(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _get_predictions(self):
        """Get predictions as JSON."""
        global tippspiel
        try:
            predictions = tippspiel.get_predictions()
            return {
                'predictions': [
                    {
                        'home_team': p.home_team,
                        'away_team': p.away_team,
                        'prob_home': p.prob_home,
                        'prob_draw': p.prob_draw,
                        'prob_away': p.prob_away,
                        'tip': p.tip,
                        'score': str(p.score),
                        'confidence': p.confidence,
                        'explanation': p.explanation,
                    }
                    for p in predictions
                ]
            }
        except Exception as e:
            return {'error': str(e), 'predictions': []}

    def _get_table(self):
        """Get table as JSON."""
        global tippspiel
        try:
            table = tippspiel.get_table()
            return {'table': table}
        except Exception as e:
            return {'error': str(e), 'table': []}

    def _get_news(self):
        """Get news as JSON."""
        global tippspiel
        try:
            news = tippspiel.db.get_recent_news(limit=30)
            return {
                'news': [
                    {
                        'title': n.title,
                        'source': n.source,
                        'sentiment': n.sentiment_score,
                    }
                    for n in news
                ]
            }
        except Exception as e:
            return {'error': str(e), 'news': []}

    def _do_update(self):
        """Update data."""
        global tippspiel
        try:
            tippspiel.update_all(verbose=False)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def open_browser():
    """Open browser after delay."""
    import time
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:8080')


def main():
    global tippspiel

    # Argumente parsen
    no_browser = '--no-browser' in sys.argv

    print()
    print("=" * 50)
    print("  BUNDESLIGA TIPPSPIEL - Web App")
    print("=" * 50)
    print()

    # Datenbank-Pfad
    db_path = Path(__file__).parent / "tippspiel.db"
    print(f"Datenbank: {db_path}")

    # Tippspiel initialisieren
    print("Initialisiere...")
    tippspiel = TippspielApp(db_path=str(db_path), season="2025")

    # Pruefen ob DB existiert, sonst initialisieren
    if not db_path.exists() or db_path.stat().st_size < 1000:
        print("Erstmalige Einrichtung...")
        tippspiel.initialize()
        print("Lade initiale Daten (kann 30 Sekunden dauern)...")
        tippspiel.update_all(verbose=True)

    print()
    print("Starte Webserver auf http://127.0.0.1:8080")
    print()
    print("Zum Beenden: Ctrl+C")
    print()

    # Browser oeffnen (nur wenn nicht --no-browser)
    if not no_browser:
        print("Browser wird geoeffnet...")
        threading.Thread(target=open_browser, daemon=True).start()

    # Server starten
    PORT = 8080
    with socketserver.TCPServer(("127.0.0.1", PORT), TippspielHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer beendet.")


if __name__ == '__main__':
    main()
