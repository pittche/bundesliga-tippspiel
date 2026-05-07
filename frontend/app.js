let currentTab = 'predictions';
let dataCache = {};

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

async function fetchJSON(name) {
    const resp = await fetch('./data/' + name + '.json?ts=' + Date.now());
    if (!resp.ok) throw new Error(resp.status + ' ' + resp.statusText);
    return await resp.json();
}

async function loadMeta() {
    try {
        const meta = await fetchJSON('meta');
        if (meta.generated_at) {
            const dt = new Date(meta.generated_at);
            document.getElementById('updateInfo').textContent =
                'Letzte Aktualisierung: ' + dt.toLocaleString('de-DE');
        }
    } catch (e) {
        document.getElementById('updateInfo').textContent = 'Update-Info nicht verfügbar.';
    }
}

async function loadPredictions() {
    const container = document.getElementById('predictions');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Lade Prognosen...</p></div>';

    try {
        const data = await fetchJSON('predictions');

        if (!data.predictions || data.predictions.length === 0) {
            container.innerHTML = '<p class="error-msg">Keine anstehenden Spiele gefunden.</p>';
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
        const data = await fetchJSON('table');

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
        const data = await fetchJSON('news');

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

window.onload = function() {
    loadMeta();
    loadPredictions();
};
