const API_BASE = '';

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    setDefaultDates();
    loadLogs();
    addWelcomeMessage();
});

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        });
    });
}

function setDefaultDates() {
    const today = new Date();
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    const fmt = d => d.toISOString().split('T')[0];

    const dateInput = document.getElementById('log-date');
    if (dateInput) dateInput.value = fmt(today);

    const reportStart = document.getElementById('report-start');
    const reportEnd = document.getElementById('report-end');
    if (reportStart) reportStart.value = fmt(weekAgo);
    if (reportEnd) reportEnd.value = fmt(today);
}

async function loadLogs() {
    const container = document.getElementById('logs-list');
    container.innerHTML = '<div class="loading">加载中...</div>';

    const params = new URLSearchParams();
    const category = document.getElementById('filter-category').value;
    const dateFrom = document.getElementById('filter-date-from').value;
    const dateTo = document.getElementById('filter-date-to').value;

    if (category) params.set('category', category);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);

    try {
        const resp = await fetch(`${API_BASE}/api/work-logs?${params}`);
        const logs = await resp.json();

        if (logs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>暂无工作日志</p>
                    <small>点击右上角「+ 新增日志」开始记录</small>
                </div>`;
            return;
        }

        container.innerHTML = logs.map(log => renderLogCard(log)).join('');
    } catch (err) {
        container.innerHTML = '<div class="empty-state"><p>加载失败，请检查后端服务是否启动</p></div>';
    }
}

function renderLogCard(log) {
    const categoryLabels = {
        development: '开发', meeting: '会议', research: '研究',
        documentation: '文档', bugfix: 'Bug修复', review: '评审', general: '其他'
    };
    const tags = (log.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
    return `
        <div class="log-card">
            <div class="log-card-header">
                <div>
                    <div class="log-card-title">${escapeHtml(log.title)}</div>
                    <div class="log-card-meta">
                        <span class="log-card-date">${log.date}</span>
                        <span class="log-card-category">${categoryLabels[log.category] || log.category}</span>
                    </div>
                </div>
            </div>
            <div class="log-card-content">${escapeHtml(log.content)}</div>
            ${tags ? `<div class="log-card-tags">${tags}</div>` : ''}
            <div class="log-card-actions">
                <button class="btn btn-danger" onclick="deleteLog(${log.id})">删除</button>
            </div>
        </div>`;
}

function showAddLogModal() {
    document.getElementById('add-log-modal').style.display = 'flex';
    document.getElementById('log-form').reset();
    document.getElementById('log-date').value = new Date().toISOString().split('T')[0];
}

function closeModal() {
    document.getElementById('add-log-modal').style.display = 'none';
}

async function submitLog(e) {
    e.preventDefault();
    const title = document.getElementById('log-title').value.trim();
    const content = document.getElementById('log-content').value.trim();
    const category = document.getElementById('log-category').value;
    const date = document.getElementById('log-date').value;
    const tagsStr = document.getElementById('log-tags').value.trim();
    const tags = tagsStr ? tagsStr.split(/[,，]/).map(t => t.trim()).filter(Boolean) : [];

    try {
        const resp = await fetch(`${API_BASE}/api/work-logs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, category, tags, date })
        });

        if (resp.ok) {
            closeModal();
            showToast('日志保存成功', 'success');
            loadLogs();
        } else {
            const err = await resp.json();
            showToast(`保存失败: ${err.detail || '未知错误'}`, 'error');
        }
    } catch (err) {
        showToast('保存失败，请检查后端服务', 'error');
    }
}

async function deleteLog(id) {
    if (!confirm('确定要删除这条日志吗？')) return;
    try {
        await fetch(`${API_BASE}/api/work-logs/${id}`, { method: 'DELETE' });
        showToast('已删除', 'success');
        loadLogs();
    } catch (err) {
        showToast('删除失败', 'error');
    }
}

async function doSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="loading">搜索中...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/search?query=${encodeURIComponent(query)}`);
        const results = await resp.json();

        if (results.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>未找到相关结果</p></div>';
            return;
        }

        container.innerHTML = results.map(r => `
            <div class="search-result-card">
                <div class="log-card-header">
                    <div>
                        <div class="log-card-title">${escapeHtml(r.title)}</div>
                        <div class="log-card-meta">
                            <span class="log-card-date">${r.date}</span>
                            <span class="search-result-score">相关度: ${r.score.toFixed(1)}</span>
                        </div>
                    </div>
                </div>
                <div class="log-card-content">${escapeHtml(r.content)}</div>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = '<div class="empty-state"><p>搜索失败</p></div>';
    }
}

async function generateReport() {
    const startDate = document.getElementById('report-start').value;
    const endDate = document.getElementById('report-end').value;
    const style = document.getElementById('report-style').value;

    if (!startDate || !endDate) {
        showToast('请选择日期范围', 'error');
        return;
    }

    const output = document.getElementById('report-output');
    output.innerHTML = '<div class="loading">正在生成周报...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/weekly-report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_date: startDate, end_date: endDate, style })
        });
        const data = await resp.json();

        output.innerHTML = `
            <div class="stats-bar">
                <div class="stat-item">
                    <div class="stat-value">${data.statistics.total_logs || 0}</div>
                    <div class="stat-label">工作记录</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${data.statistics.active_days || 0}</div>
                    <div class="stat-label">活跃天数</div>
                </div>
            </div>
            <div style="margin-bottom:16px;padding:12px;background:#f0fdf4;border-radius:6px;font-size:14px;">
                <strong>摘要：</strong>${escapeHtml(data.summary)}
            </div>
            <div>${formatReport(data.report)}</div>
        `;
    } catch (err) {
        output.innerHTML = '<div class="empty-state"><p>生成失败</p></div>';
    }
}

function formatReport(text) {
    return text
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^#### (.+)$/gm, '<h4 style="font-size:14px;margin-top:12px;">$1</h4>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.+?)`/g, '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;">$1</code>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul style="margin:8px 0;padding-left:20px;">$&</ul>');
}

function addWelcomeMessage() {
    const container = document.getElementById('chat-messages');
    container.innerHTML = `
        <div class="chat-message bot">你好！我是 WorkFlow AI 助手。你可以问我关于工作记录的问题，例如：
- "这周做了多少工作？"
- "最近的工作记录"
- "总结一下我的工作"
- "关于前端开发的工作"</div>`;
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question) return;

    const container = document.getElementById('chat-messages');
    container.innerHTML += `<div class="chat-message user">${escapeHtml(question)}</div>`;
    input.value = '';
    container.scrollTop = container.scrollHeight;

    container.innerHTML += '<div class="chat-message bot loading">思考中...</div>';
    container.scrollTop = container.scrollHeight;

    try {
        const resp = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, context_days: 30 })
        });
        const data = await resp.json();

        container.querySelector('.loading')?.remove();
        container.innerHTML += `<div class="chat-message bot">${escapeHtml(data.answer)}</div>`;
    } catch (err) {
        container.querySelector('.loading')?.remove();
        container.innerHTML += '<div class="chat-message bot">抱歉，查询失败。请确保后端服务正在运行。</div>';
    }
    container.scrollTop = container.scrollHeight;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
