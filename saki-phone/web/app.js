/**
 * Saki Phone App — Gateway Dashboard
 * Connects to saki-gateway backend API for chat, memory, reminders, and settings.
 */

// ============================================
// SVG Icon Helper
// ============================================
function svgIcon(id, extraClass = '') {
  return `<svg class="icon${extraClass ? ' ' + extraClass : ''}"><use href="#i-${id}"/></svg>`;
}

// ============================================
// Main Application Class
// ============================================
class SakiPhoneApp {
  constructor() {
    this.currentPage = 'home';
    this.previousPage = null;
    this.chatHistory = [];
    this.isTyping = false;
    this.gatewayConfig = null;
    this.healthData = null;
    this.currentMemoryView = 'long_term';
    this.currentMemoryCategory = '';
    this.expandedLogIds = new Set();
    this.editingMemoryId = null;
    this.studyWindowDays = 7;
    this.studyData = null;
    this.init();
  }

  async apiFetch(url, options = {}) {
    const opts = {
      cache: 'no-store',
      ...options,
      headers: {
        ...(options.headers || {}),
      },
    };
    const res = await fetch(url, opts);
    if (res.status === 401) {
      const error = new Error('AUTH_REQUIRED');
      error.code = 'AUTH_REQUIRED';
      throw error;
    }
    return res;
  }

  // ------------------------------------------
  // Initialization
  // ------------------------------------------
  async init() {
    this.loadLocalData();
    this.applyTheme(localStorage.getItem('saki_theme') || 'pink');
    this.setupEventListeners();
    this.setupTouchEvents();
    this.startClock();
    this.showHome();
  }

  loadLocalData() {
    try {
      this.chatHistory = JSON.parse(localStorage.getItem('saki_chat_history') || '[]');
    } catch {
      this.chatHistory = [];
    }
  }

  saveChatHistory() {
    try {
      // keep last 500 messages
      if (this.chatHistory.length > 500) {
        this.chatHistory = this.chatHistory.slice(-500);
      }
      localStorage.setItem('saki_chat_history', JSON.stringify(this.chatHistory));
    } catch (e) {
      console.warn('Failed to save chat history:', e);
    }
  }

  setupEventListeners() {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.hideModal();
    });

    // Memory search debounce
    const searchInput = document.getElementById('memory-search');
    if (searchInput) {
      let timer = null;
      searchInput.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const q = searchInput.value.trim();
          if (q) {
            this.searchMemories(q);
          } else {
            this.renderMemories();
          }
        }, 400);
      });
    }

    // Auto-resize chat input
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
      });
    }
  }

  setupTouchEvents() {
    let startX = 0;
    document.addEventListener('touchstart', (e) => {
      startX = e.changedTouches[0].screenX;
    }, { passive: true });
    document.addEventListener('touchend', (e) => {
      const endX = e.changedTouches[0].screenX;
      if (endX - startX > 100 && this.currentPage !== 'home') {
        this.goBack();
      }
    }, { passive: true });
  }

  startClock() {
    const update = () => {
      const el = document.getElementById('status-time');
      if (el) {
        const now = new Date();
        el.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
      }
    };
    update();
    setInterval(update, 30000);
  }

  // ------------------------------------------
  // Navigation
  // ------------------------------------------
  switchPage(name) {
    this.previousPage = this.currentPage;
    this.currentPage = name;

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`page-${name}`);
    if (target) {
      target.classList.add('active');
      target.style.animation = 'slideIn 0.3s ease-out';
    }

    this.updateBottomNav(name);

    switch (name) {
      case 'home': this.renderHome(); break;
      case 'chat': this.renderChat(); this.ensureChatInput(); break;
      case 'memory': this.renderMemories(); break;
      case 'reminders': this.renderReminders(); break;
      case 'study': this.renderStudy(); break;
      case 'settings': this.renderSettings(); break;
    }
  }

  updateBottomNav(page) {
    document.querySelectorAll('.tab-item').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });
  }

  goBack() {
    if (this.previousPage && this.previousPage !== this.currentPage) {
      this.switchPage(this.previousPage);
    } else {
      this.showHome();
    }
  }

  showHome() { this.switchPage('home'); }
  showChat() { this.switchPage('chat'); }
  showMemory() { this.switchPage('memory'); }
  showReminders() { this.switchPage('reminders'); }
  showStudy() { this.switchPage('study'); }
  showSettings() { this.switchPage('settings'); }

  // ------------------------------------------
  // Home Page
  // ------------------------------------------
  async renderHome() {
    let partnerName = 'TA';
    let online = false;
    let memoryCount = 0;
    let tools = [];

    try {
      const res = await this.apiFetch('/health');
      if (res.ok) {
        const data = await res.json();
        this.healthData = data;
        const state = data.state || {};
        partnerName = state.persona || 'TA';
        online = true;
        memoryCount = state.memory_count || 0;
        tools = state.enabled_tools || [];
      }
    } catch (err) {
      online = false;
      if (err?.code === 'AUTH_REQUIRED') {
        const statusText = document.getElementById('home-status-text');
        if (statusText) statusText.textContent = '需要重新登录';
      }
    }

    // Partner name
    const nameEl = document.getElementById('home-partner-name');
    if (nameEl) nameEl.textContent = partnerName;
    const chatName = document.getElementById('chat-partner-name');
    if (chatName) chatName.textContent = partnerName;
    const previewName = document.getElementById('preview-name');
    if (previewName) previewName.textContent = partnerName;

    // Status
    const dot = document.getElementById('home-status-dot');
    if (dot) {
      dot.className = 'status-dot ' + (online ? 'online' : 'offline');
    }
    const statusText = document.getElementById('home-status-text');
    if (statusText) statusText.textContent = online ? '在线' : '离线';

    // Memory count
    const memEl = document.getElementById('home-memory-count');
    if (memEl) memEl.textContent = `${memoryCount} 条记忆`;

    // Reminder count
    let reminderCount = 0;
    try {
      const rRes = await fetch('/api/reminders');
      
      if (rRes.ok) {
        const rData = await rRes.json();
        reminderCount = (rData.items || []).length;
      }
    } catch { /* ignore */ }
    const remEl = document.getElementById('home-reminder-count');
    if (remEl) remEl.textContent = reminderCount > 0 ? `${reminderCount} 个提醒` : '无提醒';

    let studyText = '查看当前学习状态';
    try {
      const studyRes = await this.apiFetch('/api/learning-sessions/active');
      if (studyRes.ok) {
        const studyData = await studyRes.json();
        const active = studyData.item;
        if (active) {
          const modeText = this.studyModeLabel(active.mode);
          studyText = `${modeText} · ${active.elapsed_minutes || 0}/${active.planned_minutes || 0} 分钟`;
        } else {
          studyText = '暂无进行中的学习会话';
        }
      }
    } catch (_) {
      studyText = '学习面板暂时不可用';
    }
    const studyEl = document.getElementById('home-study-status');
    if (studyEl) studyEl.textContent = studyText;

    // Tools list
    const toolsList = document.getElementById('home-tools-list');
    if (toolsList) {
      if (tools.length === 0) {
        toolsList.innerHTML = '<div class="empty-text">暂无启用的工具</div>';
      } else {
        toolsList.innerHTML = tools.map(t => `
          <div class="list-item">
            <div class="list-icon">${svgIcon('tool')}</div>
            <div class="list-content">
              <div class="list-title">${this.escapeHtml(t.id || t.name || 'tool')}</div>
              <div class="list-desc">${this.escapeHtml(t.description || '')}</div>
            </div>
          </div>
        `).join('');
      }
    }

    // Chat preview
    const lastAssistant = [...this.chatHistory].reverse().find(m => m.role === 'assistant');
    const previewText = document.getElementById('preview-text');
    if (previewText) {
      previewText.textContent = lastAssistant ? lastAssistant.content.slice(0, 80) : '点击开始聊天...';
    }
  }

  // ------------------------------------------
  // Chat Page
  // ------------------------------------------
  renderChat() {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    if (this.chatHistory.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">${svgIcon('chat', 'icon-xl')}</div>
          <p>开始你们的甜蜜聊天吧</p>
        </div>
      `;
      return;
    }

    container.innerHTML = this.chatHistory.map(msg => {
      if (msg.role === 'system') {
        return `<div class="chat-message system"><div class="system-content">${this.escapeHtml(msg.content)}</div></div>`;
      }
      const isUser = msg.role === 'user';
      const avatar = isUser ? svgIcon('user') : svgIcon('heart');
      const time = msg.timestamp ? this.formatTime(new Date(msg.timestamp)) : '';
      const toolHtml = msg.toolContexts && msg.toolContexts.length > 0
        ? msg.toolContexts.map(tc => `<div class="tool-context-indicator">${svgIcon('tool', 'icon-sm')} ${this.escapeHtml(tc.type || 'tool')}</div>`).join('')
        : '';
      const thinkingHtml = !isUser && msg.thinkingText
        ? `
          <div class="thinking-block" id="thinking-${msg.id}">
            <div class="thinking-header" onclick="app.toggleThinking('${msg.id}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 8v4M12 16h.01"></path>
              </svg>
              <span>思考过程</span>
              <span class="thinking-toggle-icon">›</span>
            </div>
            <div class="thinking-content" id="thinking-content-${msg.id}">
              <pre>${this.escapeHtml(msg.thinkingText)}</pre>
            </div>
          </div>
        `
        : '';
      const tokenHtml = !isUser && msg.tokenInfo && msg.tokenInfo.total > 0
        ? `
          <div class="token-badge">
            <span class="token-in">↑ ${msg.tokenInfo.input}</span>
            <span class="token-out">↓ ${msg.tokenInfo.output}</span>
            <span class="token-sep">·</span>
            <span class="token-total">${msg.tokenInfo.total} tokens</span>
          </div>
        `
        : '';

      return `
        <div class="chat-message ${isUser ? 'user' : 'assistant'}">
          <div class="message-avatar">${avatar}</div>
          <div class="message-body">
            <div class="message-header">
              <span>${isUser ? '我' : (this.healthData?.state?.persona || 'TA')}</span>
              <span>${time}</span>
            </div>
            ${toolHtml}
            ${thinkingHtml}
            <div class="message-bubble-inner">${this.renderMarkdown(msg.content)}</div>
            ${tokenHtml}
          </div>
        </div>
      `;
    }).join('');

    this.scrollToBottom(container);
  }

  renderMarkdown(text) {
    let html = this.escapeHtml(text || '');
    return html.replace(/\n/g, '<br>');
  }

  async sendMessage() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    // Add user message
    this.addMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    this.saveChatHistory();
    this.renderChat();

    // Send to gateway
    this.showTypingIndicator();
    try {
      const res = await fetch('/api/chat/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: text }]
        })
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        throw new Error(`${res.status} ${errText.slice(0, 150)}`);
      }

      const data = await res.json();
      const content = data.content || '...';
      const toolContexts = data.tool_contexts || [];
      const usage = data.raw?.usage || {};
      const tokenInfo = {
        input: usage.prompt_tokens || usage.input_tokens || 0,
        output: usage.completion_tokens || usage.output_tokens || 0,
        total: usage.total_tokens || 0
      };
      const rawContent = data.raw?.content || [];
      const thinkingBlock = Array.isArray(rawContent)
        ? rawContent.find(block => block.type === 'thinking')
        : null;
      const thinkingText = thinkingBlock?.thinking || '';

      this.hideTypingIndicator();
      this.addMessage('assistant', content, { toolContexts, tokenInfo, thinkingText });
      this.saveChatHistory();
      this.renderChat();
    } catch (err) {
      this.hideTypingIndicator();
      this.showToast(`请求失败: ${err.message}`, 'error');
    }
  }

  handleChatKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
  }

  addMessage(role, content, extra = {}) {
    this.chatHistory.push({
      id: this.generateId(),
      role,
      content,
      timestamp: new Date().toISOString(),
      ...extra
    });
  }

  toggleThinking(msgId) {
    const content = document.getElementById(`thinking-content-${msgId}`);
    const block = document.getElementById(`thinking-${msgId}`);
    if (!content || !block) return;
    const isOpen = content.classList.toggle('open');
    block.classList.toggle('open', isOpen);
  }

  showTypingIndicator() {
    this.isTyping = true;
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const existing = container.querySelector('.typing-indicator');
    if (existing) return;
    const div = document.createElement('div');
    div.className = 'chat-message assistant typing-indicator';
    div.innerHTML = `
      <div class="message-avatar">${svgIcon('heart')}</div>
      <div class="message-body">
        <div class="message-bubble-inner">
          <div class="typing-dots"><span></span><span></span><span></span></div>
        </div>
      </div>
    `;
    container.appendChild(div);
    this.scrollToBottom(container);

    const floatingEl = document.getElementById('floating-thinking');
    if (floatingEl) {
      floatingEl.classList.add('visible');
      const textEl = floatingEl.querySelector('.floating-thinking-text');
      if (textEl) textEl.textContent = '思考中...';
    }
  }

  hideTypingIndicator() {
    this.isTyping = false;
    const el = document.querySelector('.typing-indicator');
    if (el) el.remove();
    const floatingEl = document.getElementById('floating-thinking');
    if (floatingEl) floatingEl.classList.remove('visible');
  }

  ensureChatInput() {
    const area = document.getElementById('chat-input-area');
    if (area) {
      area.style.display = 'flex';
      area.style.visibility = 'visible';
    }
  }

  showChatMenu() {
    this.showModal('聊天', `
      <div style="padding:8px 0;">
        <p style="font-size:13px;color:var(--secondary-text);margin-bottom:16px;">
          聊天记录保存在本地浏览器中。网关服务端维护独立会话历史。
        </p>
      </div>
    `, `
      <button class="btn btn-danger" onclick="app.clearChatHistory()">清除本地聊天</button>
      <button class="btn btn-secondary" onclick="app.hideModal()">关闭</button>
    `);
  }

  clearChatHistory() {
    this.chatHistory = [];
    this.saveChatHistory();
    this.renderChat();
    this.hideModal();
    this.showToast('聊天记录已清除', 'success');
  }

  scrollToBottom(container) {
    if (!container) return;
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }

  // ------------------------------------------
  // Memory Page
  // ------------------------------------------
  async renderMemories() {
    const tabsEl = document.getElementById('memory-tabs');
    const contentEl = document.getElementById('memory-content');
    if (!tabsEl || !contentEl) return;

    contentEl.innerHTML = '<div class="empty-text">加载中...</div>';

    try {
      if (this.currentMemoryView === 'logs') {
        const res = await fetch('/api/logs');
        if (!res.ok) throw new Error('Failed to load logs');
        const data = await res.json();
        const items = data.items || [];

        tabsEl.innerHTML = `
          <div class="memory-tab ${this.currentMemoryView === 'long_term' ? 'active' : ''}" onclick="app.switchMemoryView('long_term')">
            长期记忆
          </div>
          <div class="memory-tab ${this.currentMemoryView === 'logs' ? 'active' : ''}" onclick="app.switchMemoryView('logs')">
            今日日志 <span class="tab-count">${items.length}</span>
          </div>
        `;

        if (items.length === 0) {
          contentEl.innerHTML = `
            <div class="empty-state">
              <div class="empty-icon">${svgIcon('clock', 'icon-xl')}</div>
              <p>今天还没有生成日志</p>
              <div class="empty-text">聊天消息达到 20 条后，会更新同一天的那一条日志。</div>
            </div>
          `;
          return;
        }

        contentEl.innerHTML = `<div class="memory-log-list">${items.map(m => `
          <div class="memory-card memory-log-card ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
            <div class="memory-card-header memory-log-header" onclick="app.toggleLogCard('${this.escAttr(String(m.id || ''))}')">
              <div class="memory-log-main">
                <span class="memory-date">${m.date || ''}</span>
                <div class="memory-title">${this.escapeHtml(m.title || m.key || '未命名日志')}</div>
              </div>
              <div class="memory-log-side">
                <span class="memory-log-badge">只读日志</span>
                <span class="memory-log-toggle-label">${this.expandedLogIds.has(String(m.id || '')) ? '收起' : '展开'}</span>
              </div>
            </div>
            <div class="memory-card-body memory-log-body ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
              <div class="memory-log-content">${this.escapeHtml(m.content || '')}</div>
            </div>
          </div>
        `).join('')}</div>`;
        return;
      }

      const res = await fetch('/api/memories');
      if (!res.ok) throw new Error('Failed to load memories');
      const data = await res.json();

      const items = data.items || [];
      this.memoryCache = items;
      const stats = data.stats || {};

      const categories = [
        { key: '', label: '全部', count: items.length },
        { key: 'anniversary', label: '纪念日', count: stats.anniversary || 0 },
        { key: 'preference', label: '喜好', count: stats.preference || 0 },
        { key: 'promise', label: '约定', count: stats.promise || 0 },
        { key: 'event', label: '事件', count: stats.event || 0 },
        { key: 'emotion', label: '情绪', count: stats.emotion || 0 },
        { key: 'habit', label: '习惯', count: stats.habit || 0 },
        { key: 'boundary', label: '边界', count: stats.boundary || 0 },
        { key: 'other', label: '其他', count: stats.other || 0 },
      ];

      tabsEl.innerHTML = `
        <div class="memory-tab ${this.currentMemoryView === 'long_term' ? 'active' : ''}" onclick="app.switchMemoryView('long_term')">
          长期记忆 <span class="tab-count">${items.length}</span>
        </div>
        <div class="memory-tab ${this.currentMemoryView === 'logs' ? 'active' : ''}" onclick="app.switchMemoryView('logs')">
          今日日志
        </div>
        ${categories.map(c => `
          <div class="memory-tab ${this.currentMemoryCategory === c.key ? 'active' : ''}"
               onclick="app.filterMemoryCategory('${c.key}')">
            ${c.label} <span class="tab-count">${c.count}</span>
          </div>
        `).join('')}
      `;

      const filtered = this.currentMemoryCategory
        ? items.filter(m => m.category === this.currentMemoryCategory)
        : items;

      if (filtered.length === 0) {
        contentEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">${svgIcon('memory', 'icon-xl')}</div>
            <p>暂无长期记忆</p>
            <button class="btn btn-primary btn-sm" onclick="app.showAddMemoryModal()">添加记忆</button>
          </div>
        `;
        return;
      }

      contentEl.innerHTML = `<div class="memory-log-list">${filtered.map(m => `
        <div class="memory-card memory-log-card ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
          <div class="memory-card-header memory-log-header" onclick="app.toggleLogCard('${this.escAttr(String(m.id || ''))}')">
            <div class="memory-log-main">
              <span class="memory-date">${this.escapeHtml(m.date || '')}</span>
              <div class="memory-title">${this.escapeHtml(m.title || m.key || '')}</div>
            </div>
            <div class="memory-log-side">
              <span class="memory-log-badge">${this.escapeHtml(m.category || '记忆')}</span>
              <span class="memory-log-toggle-label">${this.expandedLogIds.has(String(m.id || '')) ? '收起' : '展开'}</span>
            </div>
          </div>
          <div class="memory-card-body memory-log-body ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
            <div class="memory-log-content">${this.escapeHtml(m.content || '')}</div>
            <div class="memory-card-footer memory-unified-footer">
              <button class="action-btn" onclick="event.stopPropagation(); app.showEditMemoryModal('${this.escAttr(String(m.id || ''))}')" title="编辑">
                ${svgIcon('edit', 'icon-sm')}
              </button>
              <button class="action-btn delete" onclick="event.stopPropagation(); app.deleteMemory('${this.escAttr(String(m.id || ''))}')" title="删除">
                ${svgIcon('trash', 'icon-sm')}
              </button>
            </div>
          </div>
        </div>
      `).join('')}</div>`;

    } catch (err) {
      contentEl.innerHTML = `<div class="empty-text">加载失败: ${this.escapeHtml(err.message)}</div>`;
    }
  }

  switchMemoryView(view) {
    this.currentMemoryView = view;
    if (view === 'logs') {
      this.currentMemoryCategory = '';
    }
    const addBtn = document.getElementById('memory-add-btn');
    if (addBtn) {
      addBtn.style.display = view === 'logs' ? 'none' : 'inline-flex';
    }
    this.renderMemories();
  }

  filterMemoryCategory(key) {
    this.currentMemoryView = 'long_term';
    this.currentMemoryCategory = key;
    this.renderMemories();
  }

  toggleLogCard(id) {
    const key = String(id || '').trim();
    if (!key) return;
    if (this.expandedLogIds.has(key)) {
      this.expandedLogIds.delete(key);
    } else {
      this.expandedLogIds.add(key);
    }
    this.renderMemories();
  }

  async searchMemories(query) {
    const contentEl = document.getElementById('memory-content');
    if (!contentEl) return;

    if (this.currentMemoryView === 'logs') {
      this.renderMemories();
      return;
    }

    try {
      const res = await fetch(`/api/memories/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      const items = data.items || data.results || [];

      if (items.length === 0) {
        contentEl.innerHTML = '<div class="empty-text">未找到匹配的记忆</div>';
        return;
      }

      contentEl.innerHTML = `<div class="memory-log-list">${items.map(m => `
        <div class="memory-card memory-log-card ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
          <div class="memory-card-header memory-log-header" onclick="app.toggleLogCard('${this.escAttr(String(m.id || ''))}')">
            <div class="memory-log-main">
              <span class="memory-date">${this.escapeHtml(m.date || '')}</span>
              <div class="memory-title">${this.escapeHtml(m.title || m.key || '')}</div>
            </div>
            <div class="memory-log-side">
              <span class="memory-log-badge">${this.escapeHtml(m.category || '记忆')}</span>
              <span class="memory-log-toggle-label">${this.expandedLogIds.has(String(m.id || '')) ? '收起' : '展开'}</span>
            </div>
          </div>
          <div class="memory-card-body memory-log-body ${this.expandedLogIds.has(String(m.id || '')) ? 'expanded' : ''}">
            <div class="memory-log-content">${this.escapeHtml(m.content || '')}</div>
            <div class="memory-card-footer memory-unified-footer">
              <button class="action-btn" onclick="event.stopPropagation(); app.showEditMemoryModal('${this.escAttr(String(m.id || ''))}')" title="编辑">
                ${svgIcon('edit', 'icon-sm')}
              </button>
              <button class="action-btn delete" onclick="event.stopPropagation(); app.deleteMemory('${this.escAttr(String(m.id || ''))}')" title="删除">
                ${svgIcon('trash', 'icon-sm')}
              </button>
            </div>
          </div>
        </div>
      `).join('')}</div>`;
    } catch (err) {
      contentEl.innerHTML = `<div class="empty-text">搜索失败: ${this.escapeHtml(err.message)}</div>`;
    }
  }

  showAddMemoryModal() {
    this.showModal('添加记忆', `
      <div class="form-group">
        <label>标题</label>
        <input type="text" id="mem-title" placeholder="记忆标题">
      </div>
      <div class="form-group">
        <label>内容</label>
        <textarea id="mem-content" rows="4" placeholder="记忆内容"></textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>分类</label>
          <select id="mem-category">
            <option value="preference">喜好</option>
            <option value="anniversary">纪念日</option>
            <option value="promise">约定</option>
            <option value="story">故事</option>
            <option value="password">密码</option>
            <option value="travel">旅行</option>
            <option value="other">其他</option>
          </select>
        </div>
        <div class="form-group">
          <label>重要度 (0-1)</label>
          <input type="number" id="mem-importance" min="0" max="1" step="0.1" value="0.5">
        </div>
      </div>
    `, `
      <button class="btn btn-secondary" onclick="app.hideModal()">取消</button>
      <button class="btn btn-primary" onclick="app.saveNewMemory()">保存</button>
    `);
  }

  showEditMemoryModal(id) {
    const item = (this.memoryCache || []).find(m => String(m.id || '') === String(id || ''));
    if (!item) {
      this.showToast('没找到这条记忆', 'warning');
      return;
    }
    this.editingMemoryId = String(item.id || '');
    this.showModal('编辑记忆', `
      <div class="form-group">
        <label>标题</label>
        <input type="text" id="mem-title" value="${this.escAttr(item.title || item.key || '')}">
      </div>
      <div class="form-group">
        <label>内容</label>
        <textarea id="mem-content" rows="4">${this.escapeHtml(item.content || '')}</textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>分类</label>
          <select id="mem-category">
            <option value="preference" ${(item.category || '') === 'preference' ? 'selected' : ''}>喜好</option>
            <option value="anniversary" ${(item.category || '') === 'anniversary' ? 'selected' : ''}>纪念日</option>
            <option value="promise" ${(item.category || '') === 'promise' ? 'selected' : ''}>约定</option>
            <option value="story" ${(item.category || '') === 'story' ? 'selected' : ''}>故事</option>
            <option value="password" ${(item.category || '') === 'password' ? 'selected' : ''}>密码</option>
            <option value="travel" ${(item.category || '') === 'travel' ? 'selected' : ''}>旅行</option>
            <option value="other" ${!item.category || item.category === 'other' ? 'selected' : ''}>其他</option>
          </select>
        </div>
        <div class="form-group">
          <label>重要度 (0-1)</label>
          <input type="number" id="mem-importance" min="0" max="1" step="0.1" value="${this.escAttr(String(item.importance ?? 0.5))}">
        </div>
      </div>
    `, `
      <button class="btn btn-secondary" onclick="app.hideModal()">取消</button>
      <button class="btn btn-primary" onclick="app.updateMemory()">保存修改</button>
    `);
  }

  async saveNewMemory() {
    const title = document.getElementById('mem-title')?.value?.trim();
    const content = document.getElementById('mem-content')?.value?.trim();
    const category = document.getElementById('mem-category')?.value || 'other';
    const importance = parseFloat(document.getElementById('mem-importance')?.value) || 0.5;

    if (!title || !content) {
      this.showToast('请填写标题和内容', 'warning');
      return;
    }

    try {
      const res = await fetch('/api/memories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, key: title, content, category, importance })
      });
      if (!res.ok) throw new Error('Failed to save');
      this.hideModal();
      this.showToast('记忆已保存', 'success');
      this.renderMemories();
    } catch (err) {
      this.showToast(`保存失败: ${err.message}`, 'error');
    }
  }

  async updateMemory() {
    const id = this.editingMemoryId;
    const title = document.getElementById('mem-title')?.value?.trim();
    const content = document.getElementById('mem-content')?.value?.trim();
    const category = document.getElementById('mem-category')?.value || 'other';
    const importance = parseFloat(document.getElementById('mem-importance')?.value) || 0.5;

    if (!id || !title || !content) {
      this.showToast('请填写标题和内容', 'warning');
      return;
    }

    try {
      const res = await this.apiFetch(`/api/memories/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, key: title, content, category, importance })
      });
      if (!res.ok) throw new Error('Failed to update');
      this.hideModal();
      this.showToast('记忆已更新', 'success');
      this.renderMemories();
    } catch (err) {
      this.showToast(`更新失败: ${err.message}`, 'error');
    }
  }

  async deleteMemory(id) {
    if (!confirm('确定删除这条记忆？')) return;
    try {
      const res = await fetch(`/api/memories/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      this.showToast('已删除', 'success');
      this.renderMemories();
    } catch (err) {
      this.showToast(`删除失败: ${err.message}`, 'error');
    }
  }

  async clearAllMemories() {
    if (!confirm('确定一键清空所有长期记忆和今日日志吗？此操作不可恢复。')) return;
    try {
      const res = await this.apiFetch('/api/memories', { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to clear memories');
      this.expandedLogIds.clear();
      this.showToast('记忆和日志已清空', 'success');
      this.renderMemories();
    } catch (err) {
      this.showToast(`清空失败: ${err.message}`, 'error');
    }
  }

  // ------------------------------------------
  // Study Page
  // ------------------------------------------
  async renderStudy() {
    const container = document.getElementById('study-content');
    if (!container) return;
    container.innerHTML = '<div class="empty-text">加载中...</div>';
    await this.refreshStudyData();
  }

  async refreshStudyData() {
    const container = document.getElementById('study-content');
    if (!container) return;

    try {
      const [activePayload, sessionsPayload, progressPayload, planPayload] = await Promise.all([
        this.getJson('/api/learning-sessions/active'),
        this.getJson('/api/learning-sessions?limit=6'),
        this.getJson(`/api/learning-sessions/progress?window_days=${encodeURIComponent(this.studyWindowDays)}&session_limit=20`),
        this.getJson('/api/study-plan'),
      ]);

      const recentSessions = sessionsPayload.items || [];
      const activeSession = activePayload.item || null;
      const inspectionSession = activeSession || recentSessions[0] || null;

      let events = [];
      let responses = [];
      let framework = null;
      let checkins = [];
      if (inspectionSession?.id) {
        const [eventsPayload, responsesPayload, frameworkPayload, checkinsPayload] = await Promise.all([
          this.getJson(`/api/learning-sessions/${encodeURIComponent(inspectionSession.id)}/events?limit=8`),
          this.getJson(`/api/learning-sessions/${encodeURIComponent(inspectionSession.id)}/responses?limit=8`),
          this.getJson(`/api/learning-sessions/framework?session_id=${encodeURIComponent(inspectionSession.id)}`),
          this.getJson(`/api/learning-sessions/${encodeURIComponent(inspectionSession.id)}/checkins?limit=5`),
        ]);
        events = eventsPayload.items || [];
        responses = responsesPayload.items || [];
        framework = frameworkPayload.framework || null;
        checkins = checkinsPayload.items || [];
      }

      this.studyData = {
        activeSession,
        inspectionSession,
        recentSessions,
        progress: progressPayload,
        plan: planPayload.item || null,
        planInspection: planPayload.inspection || {},
        events,
        responses,
        framework,
        checkins,
        error: '',
      };
      container.innerHTML = this.buildStudyPageMarkup(this.studyData);
    } catch (err) {
      this.studyData = {
        activeSession: null,
        inspectionSession: null,
        recentSessions: [],
        progress: null,
        plan: null,
        planInspection: {},
        events: [],
        responses: [],
        framework: null,
        checkins: [],
        error: err.message || '加载失败',
      };
      container.innerHTML = this.buildStudyPageMarkup(this.studyData);
    }
  }

  async getJson(url, options = {}) {
    const res = await this.apiFetch(url, options);
    let data = {};
    try {
      data = await res.json();
    } catch (_) {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data.error || data.message || `HTTP ${res.status}`);
    }
    return data;
  }

  buildStudyPageMarkup(data) {
    const active = data.activeSession;
    const inspection = data.inspectionSession;
    const progress = data.progress || {};
    const plan = data.plan || null;
    const metrics = progress.metrics || {};
    const balance = progress.focus_balance || { totals: {}, ratios: {} };
    const texts = progress.summary_text || {};
    const patterns = (progress.friction_patterns || {}).patterns || [];
    const recoveryState = (((data.framework || {}).recovery_state || {}).state) || 'stable';
    const responseItems = data.responses || [];
    const eventItems = data.events || [];
    const checkins = data.checkins || [];
    const recentResponse = responseItems[0] || null;
    const progressWindow = ((progress.window || {}).label) || `last ${this.studyWindowDays} days`;
    const focusTitle = plan?.current_task || plan?.current_goal || '专注学习';
    const focusGoal = plan?.next_step || plan?.current_task || '';
    const planLinkedLabel = plan?.linked_session_id
      ? `关联会话 ${this.escapeHtml(plan.linked_session_id)}`
      : '未绑定会话';
    const primarySessionTitle = this.escapeHtml(active?.title || active?.subject || focusTitle || '当前学习');
    const sessionGoal = this.escapeHtml(active?.goal || focusGoal || '从一个最小动作开始');
    const currentTask = this.escapeHtml(plan?.current_task || '还没有当前任务');
    const nextStep = this.escapeHtml(plan?.next_step || '写下一步后，工具会用它预填 focus');
    const blockerNote = this.escapeHtml(plan?.blocker_note || '暂无阻碍备注');
    const completionRate = Math.round((metrics.completion_rate || 0) * 100);
    const focusMinutes = ((balance.totals || {}).focus_minutes) || 0;
    const reviewMinutes = ((balance.totals || {}).review_minutes) || 0;
    const recoveryMinutes = ((balance.totals || {}).recovery_minutes) || 0;
    const pauseFriction = ((metrics.pause_resume || {}).friction_score) ?? 0;
    const latestEvent = eventItems[0] || null;
    const plannedMinutes = Math.max(0, Number(active?.planned_minutes) || 25);
    const elapsedMinutes = Math.max(0, Number(active?.elapsed_minutes) || 0);
    const fallbackRemainingMinutes = Math.max(plannedMinutes - elapsedMinutes, 0);
    const remainingMinutes = Math.max(0, Number(active?.remaining_minutes) || fallbackRemainingMinutes);
    const progressPercent = active
      ? Math.max(0, Math.min(100, plannedMinutes > 0 ? Math.round((elapsedMinutes / plannedMinutes) * 100) : 0))
      : 0;
    const remainingSeconds = Math.max(0, Math.round(remainingMinutes * 60));
    const displayMinutes = String(Math.floor(remainingSeconds / 60)).padStart(2, '0');
    const displaySeconds = String(remainingSeconds % 60).padStart(2, '0');
    const pomodoroDisplay = `${displayMinutes}:${displaySeconds}`;
    const pomodoroLabel = active
      ? this.escapeHtml(this.studyRuntimeStateLabel(active.runtime_state || active.status || 'active'))
      : '准备开始';
    const pomodoroElapsed = `已专注 ${Math.max(0, Math.round(elapsedMinutes))} 分钟`;
    const pomodoroCount = `第 ${Math.max(0, Number(active?.pomodoro_count) || 0)} 个番茄`;
    const pomodoroRingClass = `pomodoro-ring${active ? ' active' : ''}`;
    const pomodoroRingStyle = `--progress:${progressPercent};`;

    return `
      ${data.error ? `<div class="study-card study-card-subtle"><div class="study-note">学习面板加载失败：${this.escapeHtml(data.error)}</div></div>` : ''}

      <div class="study-workspace study-workspace-shell">
        <div class="study-workspace-main">
          <div class="study-card study-workspace-hero" id="study-workspace-overview">
            <div class="study-shell-header">
              <div>
                <div class="study-eyebrow">Study Workspace</div>
                <h4>${svgIcon('chat', 'icon-sm')} 单一对话里的学习工作台</h4>
                <div class="study-note">把当前会话、计划、check-in、进展和最近支持信息放在同一个轻量工作区里，不改动现有 B1-B6 能力。</div>
              </div>
              <div class="study-shell-actions">
                <button class="btn btn-secondary btn-sm" onclick="app.showChat()">打开聊天</button>
                <button class="btn btn-secondary btn-sm" onclick="app.refreshStudyData()">刷新工作台</button>
              </div>
            </div>

            <div class="study-hero-grid">
              <div class="study-hero-panel study-hero-panel-primary">
                <div class="study-hero-kicker">Current focus</div>
                <div class="study-hero-title">${primarySessionTitle}</div>
                <div class="study-hero-copy">${active ? `当前以 ${this.escapeHtml(this.studyModeLabel(active.mode))} 模式进行中，目标是 ${sessionGoal}。` : `还没有 active session。可以从计划里的下一小步直接启动一个 focus。`}</div>
                <div class="study-inline">
                  <span class="study-pill ${active ? 'active' : ''}">${active ? this.escapeHtml(this.studyRuntimeStateLabel(active.runtime_state)) : 'ready to start'}</span>
                  <span class="study-pill">recovery ${this.escapeHtml(recoveryState)}</span>
                  ${plan ? `<span class="study-pill">${planLinkedLabel}</span>` : ''}
                </div>
              </div>

              <div class="study-hero-panel">
                <div class="study-mini-stat-list">
                  <div class="study-mini-stat"><span>Current task</span><strong>${currentTask}</strong></div>
                  <div class="study-mini-stat"><span>Next step</span><strong>${nextStep}</strong></div>
                  <div class="study-mini-stat"><span>Progress window</span><strong>${this.escapeHtml(progressWindow)}</strong></div>
                </div>
              </div>
            </div>

            <div class="pomodoro-widget" aria-label="Pomodoro widget">
              <div class="pomodoro-ring-wrap">
                <div class="${pomodoroRingClass}" id="pomodoro-ring" style="${pomodoroRingStyle}">
                  <div class="pomodoro-time" id="pomodoro-display">${pomodoroDisplay}</div>
                  <div class="pomodoro-label" id="pomodoro-status-label">${pomodoroLabel}</div>
                </div>
              </div>
              <div class="pomodoro-controls">
                <button class="pomo-btn pomo-start" onclick="app.applyQuickStudyAction('focus', {title: '专注', planned_minutes: 25})">开始</button>
                <button class="pomo-btn pomo-pause" onclick="app.studyRuntimeAction('pause')">暂停</button>
                <button class="pomo-btn pomo-done" onclick="app.completeStudySession()">完成</button>
              </div>
              <div class="pomodoro-meta">
                <span id="pomo-elapsed">${pomodoroElapsed}</span>
                <span id="pomo-count">${pomodoroCount}</span>
              </div>
            </div>
          </div>

          <div class="study-card study-session-card" id="study-current-session-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Current Session</div>
                <h4>${svgIcon('clock', 'icon-sm')} 当前高优先级工作</h4>
              </div>
              ${active ? `<span class="study-pill active">${this.escapeHtml(active.status || 'active')}</span>` : ''}
            </div>
            ${active ? `
              <div class="study-session-overview">
                <div>
                  <div class="study-session-title">${this.escapeHtml(active.title || active.subject || '未命名会话')}</div>
                  <div class="study-note">${active.goal ? `目标：${this.escapeHtml(active.goal)}` : '当前没有单独记录的 goal，会默认沿用 plan tracker 里的下一步。'} </div>
                </div>
                <div class="study-inline">
                  <span class="study-pill">${this.escapeHtml(this.studyModeLabel(active.mode))}</span>
                  <span class="study-pill">${this.escapeHtml(this.studyRuntimeStateLabel(active.runtime_state))}</span>
                  <span class="study-pill">${active.planned_minutes || 0} min</span>
                </div>
              </div>
              <div class="study-metric-band">
                <div class="study-stat prominent"><div class="study-stat-label">已过 / 剩余</div><div class="study-stat-value">${active.elapsed_minutes || 0} / ${Math.max(0, active.remaining_minutes || 0)} 分钟</div></div>
                <div class="study-stat"><div class="study-stat-label">模式</div><div class="study-stat-value">${this.studyModeLabel(active.mode)}</div></div>
                <div class="study-stat"><div class="study-stat-label">计划分钟</div><div class="study-stat-value">${active.planned_minutes || 0}</div></div>
                <div class="study-stat"><div class="study-stat-label">番茄 / 休息</div><div class="study-stat-value">${active.pomodoro_count || 0} / ${active.break_count || 0}</div></div>
              </div>
              ${recentResponse ? `
                <div class="study-support-callout">
                  <div class="study-log-title">最近陪伴回应</div>
                  <div class="study-log-body">${this.escapeHtml(recentResponse.message || '')}</div>
                </div>
              ` : ''}
              <div class="study-actions study-actions-primary">
                ${active.runtime_state === 'paused'
                  ? `<button class="btn btn-primary btn-sm" onclick="app.studyRuntimeAction('resume')">继续</button>`
                  : `<button class="btn btn-secondary btn-sm" onclick="app.studyRuntimeAction('pause')">暂停</button>`}
                <button class="btn btn-secondary btn-sm" onclick="app.applyQuickStudyAction('checkin')">Check-in</button>
                <button class="btn btn-primary btn-sm" onclick="app.completeStudySession()">完成</button>
                <button class="btn btn-secondary btn-sm" onclick="app.abandonStudySession()">结束</button>
              </div>
            ` : `
              <div class="study-empty">当前没有进行中的学习会话。</div>
              <div class="study-note">可以从上面的番茄钟直接开始，也可以先在右侧写下 current task 和 next small step。</div>
            `}
          </div>

          <div class="study-card" id="study-feed-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Recent support</div>
                <h4>${svgIcon('refresh', 'icon-sm')} Session Feed</h4>
              </div>
              ${inspection ? `<div class="study-note">查看 ${this.escapeHtml(inspection.title || inspection.subject || inspection.id || '')}</div>` : ''}
            </div>

            <div class="study-feed-grid">
              <div class="study-feed-column">
                <div class="study-feed-heading">Recent responses</div>
                ${responseItems.length > 0 ? `<div class="study-log-list">
                  ${responseItems.map(item => {
                    const context = item.response_context || {};
                    const derivedState = ((context.recovery_state || {}).state) || '';
                    const nextStepLabel = ((context.next_step || {}).label) || '';
                    return `<div class="study-log-item"><div class="study-log-head"><div class="study-log-title">${this.escapeHtml(item.event_type || 'response')}</div><div class="study-log-time">${this.formatDateTime(new Date(item.created_at || ''))}</div></div><div class="study-log-body">${this.escapeHtml(item.message || '')}</div>${(derivedState || nextStepLabel) ? `<div class="study-log-meta">${derivedState ? `<span>support ${this.escapeHtml(derivedState)}</span>` : ''}${nextStepLabel ? `<span>${this.escapeHtml(nextStepLabel)}</span>` : ''}</div>` : ''}</div>`;
                  }).join('')}
                </div>` : '<div class="study-empty">暂无陪伴回应。</div>'}
              </div>
              <div class="study-feed-column">
                <div class="study-feed-heading">Recent activity</div>
                ${eventItems.length > 0 ? `<div class="study-log-list">
                  ${eventItems.map(item => `<div class="study-log-item"><div class="study-log-head"><div class="study-log-title">${this.escapeHtml(item.event_type || 'event')}</div><div class="study-log-time">${this.formatDateTime(new Date(item.created_at || ''))}</div></div><div class="study-log-meta"><span>${this.escapeHtml(item.runtime_state || 'state unavailable')}</span></div></div>`).join('')}
                </div>` : '<div class="study-empty">暂无事件记录。</div>'}
                ${latestEvent ? `<div class="study-note">最近事件：${this.escapeHtml(latestEvent.event_type || 'event')} · ${this.formatDateTime(new Date(latestEvent.created_at || ''))}</div>` : ''}
              </div>
            </div>
          </div>
        </div>

        <aside class="study-workspace-side">
          <div class="study-card study-card-subtle" id="study-start-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Focus launcher</div>
                <h4>${svgIcon('plus', 'icon-sm')} 轻量启动器</h4>
              </div>
            </div>
            <div class="study-note">复用现有 learning-session 接口，只把最常用字段放到工作台里。</div>
            <div class="study-form-grid compact" style="margin-top:12px;">
              <div class="setting-item full">
                <label>标题</label>
                <input type="text" id="study-title" value="${this.escapeHtml(focusTitle)}" placeholder="例如：线代复习">
              </div>
              <div class="setting-item full">
                <label>目标</label>
                <input type="text" id="study-goal" value="${this.escapeHtml(focusGoal)}" placeholder="例如：先做两道题">
              </div>
              <div class="setting-item">
                <label>模式</label>
                <select id="study-mode">
                  <option value="focus">focus</option>
                  <option value="review">review</option>
                  <option value="recovery">recovery</option>
                </select>
              </div>
              <div class="setting-item">
                <label>计划分钟</label>
                <input type="number" id="study-planned-minutes" min="1" value="25">
              </div>
            </div>
            <div class="study-actions">
              <button class="btn btn-primary btn-sm" onclick="app.startStudySession()">开始会话</button>
            </div>
          </div>

          <div class="study-card" id="study-plan-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Plan Tracker</div>
                <h4>${svgIcon('star', 'icon-sm')} 当前目标与下一步</h4>
              </div>
              ${plan ? `<span class="study-pill">${this.escapeHtml(plan.status || 'active')}</span>` : ''}
            </div>
            ${plan ? `
              <div class="study-plan-summary">
                <div class="study-plan-line"><span>当前目标</span><strong>${this.escapeHtml(plan.current_goal || '未填写')}</strong></div>
                <div class="study-plan-line"><span>当前任务</span><strong>${currentTask}</strong></div>
                <div class="study-plan-line"><span>下一步</span><strong>${nextStep}</strong></div>
              </div>
              <div class="study-inline" style="margin-top:12px;">
                <span class="study-pill">${plan.carry_forward ? 'carry forward' : 'clear on complete'}</span>
                <span class="study-pill">${planLinkedLabel}</span>
              </div>
            ` : '<div class="study-note">还没有当前计划。写下 goal、task 和 next small step 就够了。</div>'}
            <div class="study-form-grid compact" style="margin-top:12px;">
              <div class="setting-item full"><label>Current goal</label><input type="text" id="study-plan-goal" value="${this.escapeHtml(plan?.current_goal || '')}" placeholder="例如：把今天的复盘推进一点"></div>
              <div class="setting-item full"><label>Current task</label><input type="text" id="study-plan-task" value="${this.escapeHtml(plan?.current_task || '')}" placeholder="例如：整理错题第 2 题"></div>
              <div class="setting-item full"><label>Next small step</label><input type="text" id="study-plan-next-step" value="${this.escapeHtml(plan?.next_step || '')}" placeholder="例如：先打开笔记并写下题号"></div>
              <div class="setting-item full"><label>Blocker</label><textarea id="study-plan-blocker" rows="2" placeholder="可选：一句话记下摩擦点">${this.escapeHtml(plan?.blocker_note || '')}</textarea></div>
              <div class="setting-item full"><label><input type="checkbox" id="study-plan-carry-forward" ${plan?.carry_forward ? 'checked' : ''}> 未完成时保留 next step</label></div>
            </div>
            <div class="study-actions">
              <button class="btn btn-primary btn-sm" onclick="app.saveStudyPlan()">保存</button>
              <button class="btn btn-secondary btn-sm" onclick="app.completeStudyPlanStep()">标记完成</button>
            </div>
            <div class="study-note">${blockerNote !== '暂无阻碍备注' ? `当前阻碍：${blockerNote}` : 'Plan Tracker 是轻量持久 guidance，不是完整任务管理系统。'}</div>
          </div>

          <div class="study-card" id="study-checkin-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Check-in</div>
                <h4>${svgIcon('heart', 'icon-sm')} 快速状态输入</h4>
              </div>
            </div>
            <div class="study-note">给现有 B3 恢复感知逻辑一个短输入，而不是填写沉重表单。</div>
            <div class="study-form-grid compact short-fields" style="margin-top:12px;">
              <div class="setting-item">
                <label>阶段</label>
                <select id="study-checkin-stage">
                  <option value="start">start</option>
                  <option value="end">end</option>
                </select>
              </div>
              <div class="setting-item"><label>能量</label><input type="number" id="study-checkin-energy" min="1" max="5" placeholder="1-5"></div>
              <div class="setting-item"><label>压力</label><input type="number" id="study-checkin-stress" min="1" max="5" placeholder="1-5"></div>
              <div class="setting-item"><label>专注困难</label><input type="number" id="study-checkin-focus" min="1" max="5" placeholder="1-5"></div>
              <div class="setting-item"><label>身体负担</label><input type="number" id="study-checkin-body" min="1" max="5" placeholder="1-5"></div>
              <div class="setting-item full"><label>备注</label><textarea id="study-checkin-note" rows="2" placeholder="一句话就够，例如：有点累，但可以先做 5 分钟"></textarea></div>
            </div>
            <div class="study-actions">
              <button class="btn btn-primary btn-sm" onclick="app.submitStudyCheckin()">提交 check-in</button>
            </div>
            ${checkins.length > 0 ? `<div class="study-log-list" style="margin-top:12px;">
              ${checkins.slice(0, 3).map(item => `<div class="study-log-item"><div class="study-log-head"><div class="study-log-title">${this.escapeHtml(item.stage || 'checkin')}</div><div class="study-log-time">${this.formatDateTime(new Date(item.created_at || ''))}</div></div><div class="study-log-meta"><span>energy ${item.energy_level ?? '-'}</span><span>stress ${item.stress_level ?? '-'}</span><span>focus ${item.focus_level ?? '-'}</span><span>body ${item.body_state_level ?? '-'}</span></div>${item.note ? `<div class="study-log-body" style="margin-top:6px;">${this.escapeHtml(item.note)}</div>` : ''}</div>`).join('')}
            </div>` : '<div class="study-empty" style="margin-top:12px;">还没有记录 check-in。</div>'}
          </div>

          <div class="study-card" id="study-progress-card">
            <div class="study-section-head">
              <div>
                <div class="study-eyebrow">Progress Snapshot</div>
                <h4>${svgIcon('star', 'icon-sm')} 近期趋势</h4>
              </div>
              <div class="study-inline">
                ${[7, 14, 30].map(days => `
                  <button class="study-pill ${this.studyWindowDays === days ? 'active' : ''}" onclick="app.setStudyWindow(${days})">${days}d</button>
                `).join('')}
              </div>
            </div>
            <div class="study-note">窗口：${this.escapeHtml(progressWindow)}</div>
            ${progress.metrics ? `
              <div class="study-metric-band compact">
                <div class="study-stat prominent"><div class="study-stat-label">完成率</div><div class="study-stat-value">${completionRate}%</div></div>
                <div class="study-stat"><div class="study-stat-label">开始 / 完成 / 放弃</div><div class="study-stat-value">${metrics.sessions_started || 0} / ${metrics.sessions_completed || 0} / ${metrics.sessions_abandoned || 0}</div></div>
                <div class="study-stat"><div class="study-stat-label">focus / review / recovery</div><div class="study-stat-value">${focusMinutes} / ${reviewMinutes} / ${recoveryMinutes}</div></div>
                <div class="study-stat"><div class="study-stat-label">pause friction</div><div class="study-stat-value">${pauseFriction}</div></div>
              </div>
              <div class="study-balance-bar">
                <div class="study-balance-focus" style="width:${((balance.ratios || {}).focus_ratio || 0) * 100}%;"></div>
                <div class="study-balance-review" style="width:${((balance.ratios || {}).review_ratio || 0) * 100}%;"></div>
                <div class="study-balance-recovery" style="width:${((balance.ratios || {}).recovery_ratio || 0) * 100}%;"></div>
              </div>
              <div class="study-log-list">
                <div class="study-log-item"><div class="study-log-title">recent summary</div><div class="study-log-body">${this.escapeHtml(texts.weekly_summary || '暂无总结')}</div></div>
                <div class="study-log-item"><div class="study-log-title">momentum</div><div class="study-log-body">${this.escapeHtml(texts.momentum_check || '暂无数据')}</div></div>
                <div class="study-log-item"><div class="study-log-title">blocker / friction</div><div class="study-log-body">${this.escapeHtml(texts.blocker_focus_balance_note || '暂无数据')}</div></div>
              </div>
              ${patterns.length > 0 ? `
                <div class="study-log-list" style="margin-top:12px;">
                  ${patterns.slice(0, 3).map(item => `<div class="study-log-item"><div class="study-log-title">${this.escapeHtml(item.label || item.pattern || 'pattern')}</div><div class="study-log-body">${this.escapeHtml(item.reason || '')}</div></div>`).join('')}
                </div>
              ` : '<div class="study-empty" style="margin-top:12px;">最近还没有明显的摩擦模式。</div>'}
            ` : '<div class="study-empty">还没有可展示的趋势数据。</div>'}
          </div>
        </aside>
      </div>
    `;
  }
  scrollStudySection(sectionId, focusId = '') {
    const target = document.getElementById(sectionId);
    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    if (focusId) {
      const input = document.getElementById(focusId);
      if (input && typeof input.focus === 'function') {
        setTimeout(() => input.focus(), 50);
      }
    }
  }

  async startStudySession(overrides = {}) {
    const title = String(overrides.title ?? this.getVal('study-title')).trim();
    const goal = String(overrides.goal ?? this.getVal('study-goal')).trim();
    const mode = String(overrides.mode ?? (this.getVal('study-mode') || 'focus'));
    const plannedMinutes = parseInt(overrides.planned_minutes ?? this.getVal('study-planned-minutes'), 10) || 25;
    const pomodoroCount = parseInt(overrides.pomodoro_count ?? 0, 10) || 0;
    if (!title) {
      this.showToast('请先填写学习标题', 'warning');
      return;
    }
    try {
      await this.getJson('/api/learning-sessions/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          goal,
          mode,
          planned_minutes: plannedMinutes,
          pomodoro_count: pomodoroCount,
        }),
      });
      this.showToast('学习会话已开始', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`开始失败: ${err.message}`, 'error');
    }
  }

  async studyRuntimeAction(action) {
    const active = this.studyData?.activeSession;
    if (!active?.id) {
      this.showToast('当前没有 active 会话', 'warning');
      return;
    }
    const elapsed = parseInt(active.elapsed_minutes || 0, 10) || 0;
    const remaining = parseInt(active.remaining_minutes || 0, 10) || 0;
    try {
      await this.getJson(`/api/learning-sessions/${encodeURIComponent(active.id)}/runtime`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          elapsed_minutes: elapsed,
          remaining_minutes: remaining,
        }),
      });
      this.showToast(`已执行 ${action}`, 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`操作失败: ${err.message}`, 'error');
    }
  }

  async completeStudySession() {
    const active = this.studyData?.activeSession;
    if (!active?.id) {
      this.showToast('当前没有 active 会话', 'warning');
      return;
    }
    try {
      await this.getJson(`/api/learning-sessions/${encodeURIComponent(active.id)}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      this.showToast('学习会话已完成', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`完成失败: ${err.message}`, 'error');
    }
  }

  async abandonStudySession() {
    const active = this.studyData?.activeSession;
    if (!active?.id) {
      this.showToast('当前没有 active 会话', 'warning');
      return;
    }
    try {
      await this.getJson(`/api/learning-sessions/${encodeURIComponent(active.id)}/abandon`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      this.showToast('学习会话已结束', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`结束失败: ${err.message}`, 'error');
    }
  }

  async submitStudyCheckin() {
    const session = this.studyData?.activeSession || this.studyData?.inspectionSession;
    if (!session?.id) {
      this.showToast('还没有可关联的学习会话', 'warning');
      return;
    }
    const payload = {
      stage: this.getVal('study-checkin-stage') || 'start',
      energy_level: this.getOptionalNumber('study-checkin-energy'),
      stress_level: this.getOptionalNumber('study-checkin-stress'),
      focus_level: this.getOptionalNumber('study-checkin-focus'),
      body_state_level: this.getOptionalNumber('study-checkin-body'),
      note: this.getVal('study-checkin-note').trim(),
    };
    try {
      await this.getJson(`/api/learning-sessions/${encodeURIComponent(session.id)}/checkins`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      this.showToast('check-in 已提交', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`check-in 失败: ${err.message}`, 'error');
    }
  }

  async setStudyWindow(days) {
    this.studyWindowDays = days;
    await this.refreshStudyData();
  }

  async applyQuickStudyAction(kind, payload = {}) {
    if (kind === 'resume') {
      if (this.studyData?.activeSession?.runtime_state === 'paused') {
        await this.studyRuntimeAction('resume');
      } else {
        this.showToast('当前没有可继续的暂停会话', 'warning');
      }
      return;
    }
    if (kind === 'focus' || kind === 'pomodoro') {
      if (this.studyData?.activeSession?.id) {
        this.showToast('已经有进行中的会话了，请先完成或结束它', 'warning');
        return;
      }
      await this.startStudySession({
        title: payload.title || '',
        goal: payload.goal || '',
        mode: 'focus',
        planned_minutes: payload.planned_minutes || 25,
        pomodoro_count: payload.pomodoro_count || 0,
      });
      return;
    }
    if (kind === 'progress') {
      if (this.studyWindowDays !== 14) {
        await this.setStudyWindow(14);
      }
      this.scrollStudySection('study-progress-card');
      return;
    }
    if (kind === 'plan') {
      this.scrollStudySection('study-plan-card', 'study-plan-goal');
      return;
    }
    if (kind === 'checkin') {
      this.scrollStudySection('study-checkin-card', 'study-checkin-note');
      return;
    }
    this.showToast(`${kind} 工具已准备好`, 'success');
  }

  async saveStudyPlan() {
    try {
      await this.getJson('/api/study-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_goal: this.getVal('study-plan-goal').trim(),
          current_task: this.getVal('study-plan-task').trim(),
          next_step: this.getVal('study-plan-next-step').trim(),
          blocker_note: this.getVal('study-plan-blocker').trim(),
          carry_forward: this.getChecked('study-plan-carry-forward'),
          linked_session_id: this.studyData?.activeSession?.id || this.studyData?.plan?.linked_session_id || '',
        }),
      });
      this.showToast('计划已保存', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`计划保存失败: ${err.message}`, 'error');
    }
  }

  async completeStudyPlanStep() {
    try {
      await this.getJson('/api/study-plan/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          carry_forward: this.getChecked('study-plan-carry-forward'),
        }),
      });
      this.showToast('已更新计划步骤状态', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`计划更新失败: ${err.message}`, 'error');
    }
  }

  async clearStudyPlan() {
    try {
      await this.getJson('/api/study-plan/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      this.showToast('计划已清空', 'success');
      await this.refreshStudyData();
    } catch (err) {
      this.showToast(`计划清空失败: ${err.message}`, 'error');
    }
  }

  studyModeLabel(mode) {
    return {
      focus: 'focus',
      review: 'review',
      recovery: 'recovery',
    }[mode] || (mode || 'unknown');
  }

  studyRuntimeStateLabel(state) {
    return {
      focus: 'focus',
      paused: 'paused',
      break: 'break',
      focus_completed: 'focus_completed',
      completed: 'completed',
      abandoned: 'abandoned',
    }[state] || (state || 'unknown');
  }

  // ------------------------------------------
  // Reminders Page
  // ------------------------------------------
  async renderReminders() {
    const container = document.getElementById('reminders-content');
    if (!container) return;

    container.innerHTML = '<div class="empty-text">加载中...</div>';

    try {
      const res = await fetch('/api/reminders');
      if (!res.ok) throw new Error('Failed to load');
      const data = await res.json();
      const items = data.items || [];

      if (items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">${svgIcon('bell', 'icon-xl')}</div>
            <p>暂无提醒</p>
            <button class="btn btn-primary btn-sm" onclick="app.showAddReminderModal()">创建提醒</button>
          </div>
        `;
        return;
      }

      container.innerHTML = items.map(r => {
        const statusClass = r.status === 'delivered' ? 'delivered' : 'pending';
        const statusLabel = r.status === 'delivered' ? '已送达' : '等待中';
        const triggerTime = r.trigger_at ? this.formatDateTime(new Date(r.trigger_at)) : '';

        return `
          <div class="reminder-item">
            <div class="list-icon">${svgIcon('bell')}</div>
            <div class="reminder-info">
              <div class="reminder-content">${this.escapeHtml(r.content)}</div>
              <div class="reminder-meta">${triggerTime}</div>
            </div>
            <span class="reminder-status ${statusClass}">${statusLabel}</span>
            <button class="action-btn delete" onclick="app.deleteReminder('${r.id}')" title="删除">
              ${svgIcon('trash', 'icon-sm')}
            </button>
          </div>
        `;
      }).join('');
    } catch (err) {
      container.innerHTML = `<div class="empty-text">加载失败: ${this.escapeHtml(err.message)}</div>`;
    }
  }

  showAddReminderModal() {
    this.showModal('创建提醒', `
      <div class="form-group">
        <label>提醒内容</label>
        <input type="text" id="rem-content" placeholder="提醒我做什么...">
      </div>
      <div class="form-group">
        <label>多少分钟后提醒</label>
        <input type="number" id="rem-minutes" min="1" value="30" placeholder="分钟">
      </div>
    `, `
      <button class="btn btn-secondary" onclick="app.hideModal()">取消</button>
      <button class="btn btn-primary" onclick="app.createNewReminder()">创建</button>
    `);
  }

  async createNewReminder() {
    const content = document.getElementById('rem-content')?.value?.trim();
    const minutes = parseInt(document.getElementById('rem-minutes')?.value) || 0;

    if (!content) {
      this.showToast('请填写提醒内容', 'warning');
      return;
    }
    if (minutes <= 0) {
      this.showToast('请输入有效的分钟数', 'warning');
      return;
    }

    try {
      const res = await fetch('/api/reminders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, minutes })
      });
      if (!res.ok) throw new Error('Failed to create');
      this.hideModal();
      this.showToast('提醒已创建', 'success');
      this.renderReminders();
    } catch (err) {
      this.showToast(`创建失败: ${err.message}`, 'error');
    }
  }

  async deleteReminder(id) {
    try {
      const res = await fetch(`/api/reminders/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      this.showToast('已删除', 'success');
      this.renderReminders();
    } catch (err) {
      this.showToast(`删除失败: ${err.message}`, 'error');
    }
  }

  // ------------------------------------------
  // Settings Page
  // ------------------------------------------
  async renderSettings() {
    const statusEl = document.getElementById('settings-gateway-status');
    const contentEl = document.getElementById('settings-content');
    if (!contentEl) return;

    contentEl.innerHTML = '<div class="empty-text">加载中...</div>';

    let health = null;
    let config = null;
    let authExpired = false;

    try {
      const [hRes, cRes] = await Promise.all([
        this.apiFetch('/health'),
        this.apiFetch('/api/config')
      ]);
      if (hRes.ok) health = await hRes.json();
      if (cRes.ok) config = await cRes.json();
    } catch (err) {
      authExpired = err?.code === 'AUTH_REQUIRED';
    }

    if (!config) {
      contentEl.innerHTML = authExpired
        ? '<div class="empty-text">面板登录已失效，请刷新页面后重新输入密码。</div>'
        : '<div class="empty-text">无法连接到网关接口。更像是静态页面打开了，但 API 没通；请检查网关服务、反向代理和浏览器缓存。</div>';
      if (statusEl) statusEl.innerHTML = '';
      return;
    }

    this.gatewayConfig = config;

    // Gateway status
    if (statusEl) {
      const state = health?.state || {};
      const memCount = state.memory_count || 0;
      const sessions = state.runtime?.sessions || 0;
      const events = state.runtime?.events || 0;
      const toolCount = (state.enabled_tools || []).length;

      statusEl.innerHTML = `
        <div class="gateway-info-grid">
          <div class="gateway-info-item">
            <span class="gateway-info-label">状态</span>
            <span class="gateway-info-value" style="color: var(--success-dark);">在线</span>
          </div>
          <div class="gateway-info-item">
            <span class="gateway-info-label">记忆</span>
            <span class="gateway-info-value">${memCount}</span>
          </div>
          <div class="gateway-info-item">
            <span class="gateway-info-label">会话</span>
            <span class="gateway-info-value">${sessions}</span>
          </div>
          <div class="gateway-info-item">
            <span class="gateway-info-label">工具</span>
            <span class="gateway-info-value">${toolCount}</span>
          </div>
        </div>
      `;
    }

    // Settings sections
    contentEl.innerHTML = this.buildSettingsSections(config);
  }

  async refreshGatewayConfig() {
    this.showToast('刷新中...', 'info');
    await this.renderSettings();
    this.showToast('已刷新', 'success');
  }

  buildSettingsSections(c) {
    const persona = c.persona || {};
    const chatApi = c.chat_api || {};
    const actionApi = c.action_api || {};
    const searchApi = c.search_api || {};
    const ttsApi = c.tts_api || {};
    const imageApi = c.image_api || {};
    const memory = c.memory || {};
    const session = c.session || {};
    const scheduler = c.scheduler || {};
    const channels = c.channels || {};
    const dashboardSecurity = c.dashboard_security || {};

    return `
      <!-- Persona -->
      <div class="settings-section" id="sec-persona">
        <h4>${svgIcon('heart', 'icon-sm')} 人设</h4>
        <div class="setting-item">
          <label>伴侣名字</label>
          <input type="text" id="cfg-persona-partner_name" value="${this.escAttr(persona.partner_name || '')}">
        </div>
        <div class="setting-item">
          <label>伴侣角色</label>
          <input type="text" id="cfg-persona-partner_role" value="${this.escAttr(persona.partner_role || '')}">
        </div>
        <div class="setting-item">
          <label>对你的称呼</label>
          <input type="text" id="cfg-persona-call_user" value="${this.escAttr(persona.call_user || '')}">
        </div>
        <div class="setting-item">
          <label>基础人设</label>
          <textarea id="cfg-persona-base_persona" rows="3">${this.escapeHtml(persona.base_persona || persona.core_identity || '')}</textarea>
        </div>
        <div class="setting-item">
          <label>学习覆盖层</label>
          <textarea id="cfg-persona-study_overlay" rows="3">${this.escapeHtml(persona.study_overlay || '')}</textarea>
        </div>
        <div class="setting-item">
          <label>恢复覆盖层</label>
          <textarea id="cfg-persona-recovery_overlay" rows="3">${this.escapeHtml(persona.recovery_overlay || '')}</textarea>
        </div>
        <div class="setting-item">
          <label>安全备注</label>
          <textarea id="cfg-persona-safety_notes" rows="2">${this.escapeHtml(persona.safety_notes || persona.boundaries || '')}</textarea>
        </div>
        <div class="about-info" style="margin-bottom:12px;">
          学习回复默认组合：基础人设 + 学习覆盖层 + 风格配置 + 安全边界。恢复态会额外启用恢复覆盖层，不会回退成单一大段 prompt。
        </div>
        <div class="setting-item">
          <label>dominance_style</label>
          <select id="cfg-persona-style-dominance_style">
            ${['low', 'medium', 'high'].map((value) => `<option value="${value}" ${(persona.style_config || {}).dominance_style === value ? 'selected' : ''}>${value}</option>`).join('')}
          </select>
        </div>
        <div class="setting-item">
          <label>care_style</label>
          <select id="cfg-persona-style-care_style">
            ${['soft', 'steady', 'strict_care'].map((value) => `<option value="${value}" ${(persona.style_config || {}).care_style === value ? 'selected' : ''}>${value}</option>`).join('')}
          </select>
        </div>
        <div class="setting-item">
          <label>praise_style</label>
          <select id="cfg-persona-style-praise_style">
            ${['restrained', 'warm', 'possessive_lite'].map((value) => `<option value="${value}" ${(persona.style_config || {}).praise_style === value ? 'selected' : ''}>${value}</option>`).join('')}
          </select>
        </div>
        <div class="setting-item">
          <label>correction_style</label>
          <select id="cfg-persona-style-correction_style">
            ${['gentle', 'firm'].map((value) => `<option value="${value}" ${(persona.style_config || {}).correction_style === value ? 'selected' : ''}>${value}</option>`).join('')}
          </select>
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('persona')">保存分层人设</button>
      </div>

      <!-- Chat API -->
      ${this.buildApiSection('chat_api', '聊天 API', 'chat', chatApi)}

      <!-- Action API -->
      ${this.buildActionApiSection(actionApi)}

      <!-- Search API -->
      ${this.buildApiSection('search_api', '搜索 API', 'search', searchApi)}

      <!-- TTS API -->
      ${this.buildApiSection('tts_api', 'TTS API', 'mic', ttsApi)}

      <!-- Image API -->
      ${this.buildApiSection('image_api', '图像 API', 'star', imageApi)}

      <!-- Memory -->
      <div class="settings-section" id="sec-memory">
        <h4>${svgIcon('memory', 'icon-sm')} 记忆系统</h4>
        <div class="setting-item toggle">
          <label>启用记忆</label>
          <label class="switch">
            <input type="checkbox" id="cfg-memory-enabled" ${memory.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('memory')">保存</button>
      </div>

      <!-- Session -->
      <div class="settings-section" id="sec-session">
        <h4>${svgIcon('clock', 'icon-sm')} 会话</h4>
        <div class="setting-item toggle">
          <label>启用会话管理</label>
          <label class="switch">
            <input type="checkbox" id="cfg-session-enabled" ${session.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <label>空闲轮转 (分钟)</label>
          <input type="number" id="cfg-session-idle_rotation_minutes" value="${session.idle_rotation_minutes || 360}">
        </div>
        <div class="setting-item">
          <label>上下文消息数</label>
          <input type="number" id="cfg-session-recent_message_limit" value="${session.recent_message_limit || 12}">
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('session')">保存</button>
      </div>

      <!-- Scheduler -->
      <div class="settings-section" id="sec-scheduler">
        <h4>${svgIcon('clock', 'icon-sm')} 调度器</h4>
        <div class="setting-item toggle">
          <label>启用调度器</label>
          <label class="switch">
            <input type="checkbox" id="cfg-scheduler-enabled" ${scheduler.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item toggle">
          <label>主动消息</label>
          <label class="switch">
            <input type="checkbox" id="cfg-scheduler-proactive_enabled" ${scheduler.proactive_enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <label>主动消息空闲阈值 (小时)</label>
          <input type="number" id="cfg-scheduler-proactive_idle_hours" value="${scheduler.proactive_idle_hours || 72}">
        </div>
        <div class="setting-item">
          <label>额外空闲阈值 (分钟)</label>
          <input type="number" id="cfg-scheduler-proactive_idle_minutes" value="${scheduler.proactive_idle_minutes || 0}">
        </div>
        <div class="setting-item">
          <label>白天开始小时</label>
          <input type="number" id="cfg-scheduler-proactive_day_start_hour" value="${scheduler.proactive_day_start_hour ?? 8}" min="0" max="23">
        </div>
        <div class="setting-item">
          <label>白天结束小时</label>
          <input type="number" id="cfg-scheduler-proactive_day_end_hour" value="${scheduler.proactive_day_end_hour ?? 22}" min="0" max="23">
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('scheduler')">保存</button>
      </div>

      <!-- Channels -->
      <div class="settings-section" id="sec-channels">
        <h4>${svgIcon('chat', 'icon-sm')} 渠道</h4>
        <div class="setting-item toggle">
          <label>飞书</label>
          <label class="switch">
            <input type="checkbox" id="cfg-channels-feishu_enabled" ${channels.feishu_enabled ? 'checked' : ''}
                   onchange="app.toggleFeishuFields()">
            <span class="slider"></span>
          </label>
        </div>
        <div id="feishu-fields" style="display:${channels.feishu_enabled ? 'block' : 'none'};">
          <div class="setting-item">
            <label>App ID</label>
            <input type="text" id="cfg-channels-feishu_app_id" value="${this.escAttr(channels.feishu_app_id || '')}">
          </div>
          <div class="setting-item">
            <label>App Secret</label>
            <input type="password" id="cfg-channels-feishu_app_secret" value="${this.escAttr(channels.feishu_app_secret || '')}">
          </div>
        </div>

        <div class="setting-item toggle" style="margin-top:16px;">
          <label>QQ Bot</label>
          <label class="switch">
            <input type="checkbox" id="cfg-channels-qqbot_enabled" ${channels.qqbot_enabled ? 'checked' : ''}
                   onchange="app.toggleQQBotFields()">
            <span class="slider"></span>
          </label>
        </div>
        <div id="qqbot-fields" style="display:${channels.qqbot_enabled ? 'block' : 'none'};">
          <div class="setting-item">
            <label>App ID</label>
            <input type="text" id="cfg-channels-qqbot_app_id" value="${this.escAttr(channels.qqbot_app_id || '')}" placeholder="QQ Bot AppID">
          </div>
          <div class="setting-item">
            <label>Token / Secret</label>
            <input type="password" id="cfg-channels-qqbot_token" value="${this.escAttr(channels.qqbot_token || '')}" placeholder="QQ Bot Token / Secret">
          </div>
          <div class="about-info" style="margin-bottom:12px;">使用 QQ 开放平台官方机器人接入。保存后即可由网关直接连接官方 QQBot 通道，不再依赖 NapCat。</div>
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('channels')">保存</button>
      </div>

      <!-- Dashboard Security -->
      <div class="settings-section" id="sec-dashboard-security">
        <h4>${svgIcon('lock', 'icon-sm')} 面板密码</h4>
        <div class="setting-item toggle">
          <label>启用密码保护</label>
          <label class="switch">
            <input type="checkbox" id="cfg-dashboard-security-enabled" ${dashboardSecurity.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <label>新密码</label>
          <input type="password" id="cfg-dashboard-security-password" value="" placeholder="留空则不修改当前密码">
        </div>
        <div class="setting-item">
          <label>确认新密码</label>
          <input type="password" id="cfg-dashboard-security-password_confirm" value="" placeholder="再次输入新密码">
        </div>
        <div class="about-info" style="margin-bottom:12px;">默认密码是 admin123。修改密码后面板会自动刷新并要求重新登录。</div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('dashboard_security')">保存密码设置</button>
      </div>

      <div class="settings-section" id="sec-data-transfer">
        <h4>${svgIcon('download', 'icon-sm')} 数据导入 / 导出</h4>
        <div class="about-info" style="margin-bottom:12px;">导出内容包含人设、长期记忆和今日日志。导入采用合并更新，不会先清空现有数据。</div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.exportDataBackup()">导出 JSON</button>
        <button class="btn btn-secondary btn-block" style="margin-top:10px;" onclick="app.openImportDataPicker()">导入 JSON</button>
        <input type="file" id="data-import-input" accept="application/json,.json" style="display:none;" onchange="app.importDataBackup(event)">
      </div>

      <!-- Theme -->
      <div class="settings-section">
        <h4>${svgIcon('star', 'icon-sm')} 主题</h4>
        <div class="theme-selector">
          ${['pink', 'blue', 'purple', 'green', 'orange'].map(t => `
            <div class="theme-option ${(localStorage.getItem('saki_theme') || 'pink') === t ? 'active' : ''}"
                 style="background: ${this.themePreviewColor(t)};"
                 onclick="app.setTheme('${t}')">
            </div>
          `).join('')}
        </div>
      </div>

      <!-- About -->
      <div class="settings-section">
        <h4>${svgIcon('info', 'icon-sm')} 关于</h4>
        <div class="about-info">
          <strong>咲手机 Gateway</strong><br>
          版本: 2.0.0<br>
          网关驱动的 AI 伴侣面板
        </div>
        <div class="setting-actions" style="margin-top:12px;">
          <button class="btn btn-danger btn-block" onclick="app.clearChatHistory(); app.showToast('聊天已清除','success');">清除本地聊天</button>
        </div>
      </div>
    `;
  }

  buildApiSection(key, label, icon, api) {
    return `
      <div class="settings-section" id="sec-${key}">
        <h4>${svgIcon(icon, 'icon-sm')} ${label}</h4>
        <div class="setting-item toggle">
          <label>启用</label>
          <label class="switch">
            <input type="checkbox" id="cfg-${key}-enabled" ${api.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <label>Base URL</label>
          <input type="text" id="cfg-${key}-base_url" value="${this.escAttr(api.base_url || '')}" placeholder="https://api.openai.com/v1">
        </div>
        <div class="setting-item">
          <label>API Key</label>
          <input type="password" id="cfg-${key}-api_key" value="${this.escAttr(api.api_key || '')}" placeholder="sk-...">
        </div>
        <div class="setting-item">
          <label>Model</label>
          <input type="text" id="cfg-${key}-model" value="${this.escAttr(api.model || '')}" placeholder="gpt-4o">
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('${key}')">保存</button>
      </div>
    `;
  }

  buildActionApiSection(api) {
    return `
      <div class="settings-section" id="sec-action_api">
        <h4>${svgIcon('tool', 'icon-sm')} 工具执行 API</h4>
        <div class="setting-item toggle">
          <label>启用</label>
          <label class="switch">
            <input type="checkbox" id="cfg-action_api-enabled" ${api.enabled ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-item">
          <label>Base URL</label>
          <input type="text" id="cfg-action_api-base_url" value="${this.escAttr(api.base_url || '')}" placeholder="https://api.openai.com/v1">
        </div>
        <div class="setting-item">
          <label>API Key</label>
          <input type="password" id="cfg-action_api-api_key" value="${this.escAttr(api.api_key || '')}" placeholder="sk-...">
        </div>
        <div class="setting-item">
          <label>Model</label>
          <input type="text" id="cfg-action_api-model" value="${this.escAttr(api.model || '')}" placeholder="gpt-4o-mini">
        </div>
        <div class="setting-item toggle">
          <label>启用 MCP</label>
          <label class="switch">
            <input type="checkbox" id="cfg-action_api-enable_mcp" ${api.enable_mcp ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
        <button class="btn btn-primary btn-block btn-save" onclick="app.saveSection('action_api')">保存</button>
      </div>
    `;
  }

  toggleFeishuFields() {
    const enabled = document.getElementById('cfg-channels-feishu_enabled')?.checked;
    const fields = document.getElementById('feishu-fields');
    if (fields) fields.style.display = enabled ? 'block' : 'none';
  }

  toggleQQBotFields() {
    const enabled = document.getElementById('cfg-channels-qqbot_enabled')?.checked;
    const fields = document.getElementById('qqbot-fields');
    if (fields) fields.style.display = enabled ? 'block' : 'none';
  }

  async saveSection(section) {
    let payload = {};

    switch (section) {
      case 'persona':
        payload = {
          persona: {
            partner_name: this.getVal('cfg-persona-partner_name'),
            partner_role: this.getVal('cfg-persona-partner_role'),
            call_user: this.getVal('cfg-persona-call_user'),
            base_persona: this.getVal('cfg-persona-base_persona'),
            study_overlay: this.getVal('cfg-persona-study_overlay'),
            recovery_overlay: this.getVal('cfg-persona-recovery_overlay'),
            safety_notes: this.getVal('cfg-persona-safety_notes'),
          }
        };
        payload.persona.core_identity = payload.persona.base_persona;
        payload.persona.boundaries = payload.persona.safety_notes;
        payload.learning_response_style = {
          dominance_style: this.getVal('cfg-persona-style-dominance_style'),
          care_style: this.getVal('cfg-persona-style-care_style'),
          praise_style: this.getVal('cfg-persona-style-praise_style'),
          correction_style: this.getVal('cfg-persona-style-correction_style'),
        };
        break;

      case 'chat_api':
      case 'action_api':
      case 'search_api':
      case 'tts_api':
      case 'image_api':
        if (section === 'action_api') {
          payload[section] = {
            enabled: this.getChecked('cfg-action_api-enabled'),
            base_url: this.getVal('cfg-action_api-base_url'),
            api_key: this.getVal('cfg-action_api-api_key'),
            model: this.getVal('cfg-action_api-model'),
            enable_mcp: this.getChecked('cfg-action_api-enable_mcp'),
          };
        } else {
          payload[section] = {
            enabled: this.getChecked(`cfg-${section}-enabled`),
            base_url: this.getVal(`cfg-${section}-base_url`),
            api_key: this.getVal(`cfg-${section}-api_key`),
            model: this.getVal(`cfg-${section}-model`),
          };
        }
        break;

      case 'memory':
        payload = {
          memory: {
            enabled: this.getChecked('cfg-memory-enabled'),
          }
        };
        break;

      case 'session':
        payload = {
          session: {
            enabled: this.getChecked('cfg-session-enabled'),
            idle_rotation_minutes: parseInt(this.getVal('cfg-session-idle_rotation_minutes')) || 360,
            recent_message_limit: parseInt(this.getVal('cfg-session-recent_message_limit')) || 12,
          }
        };
        break;

      case 'scheduler':
        {
          const idleHours = Number.parseInt(this.getVal('cfg-scheduler-proactive_idle_hours'), 10);
          const idleMinutes = Number.parseInt(this.getVal('cfg-scheduler-proactive_idle_minutes'), 10);
          const dayStart = Number.parseInt(this.getVal('cfg-scheduler-proactive_day_start_hour'), 10);
          const dayEnd = Number.parseInt(this.getVal('cfg-scheduler-proactive_day_end_hour'), 10);
        payload = {
          scheduler: {
            enabled: this.getChecked('cfg-scheduler-enabled'),
            proactive_enabled: this.getChecked('cfg-scheduler-proactive_enabled'),
            proactive_idle_hours: Number.isFinite(idleHours) ? idleHours : 72,
            proactive_idle_minutes: Number.isFinite(idleMinutes) ? idleMinutes : 0,
            proactive_day_start_hour: Number.isFinite(dayStart) ? dayStart : 8,
            proactive_day_end_hour: Number.isFinite(dayEnd) ? dayEnd : 22,
          }
        };
        break;
        }

      case 'channels':
        payload = {
          channels: {
            feishu_enabled: this.getChecked('cfg-channels-feishu_enabled'),
            feishu_app_id: this.getVal('cfg-channels-feishu_app_id'),
            feishu_app_secret: this.getVal('cfg-channels-feishu_app_secret'),
            qqbot_enabled: this.getChecked('cfg-channels-qqbot_enabled'),
            qqbot_app_id: this.getVal('cfg-channels-qqbot_app_id'),
            qqbot_token: this.getVal('cfg-channels-qqbot_token'),
          }
        };
        break;

      case 'dashboard_security': {
        const password = this.getVal('cfg-dashboard-security-password');
        const confirm = this.getVal('cfg-dashboard-security-password_confirm');
        if (password || confirm) {
          if (password.length < 4) {
            this.showToast('密码至少需要 4 位', 'warning');
            return;
          }
          if (password !== confirm) {
            this.showToast('两次输入的密码不一致', 'warning');
            return;
          }
        }
        payload = {
          dashboard_security: {
            enabled: this.getChecked('cfg-dashboard-security-enabled'),
          }
        };
        if (password) {
          payload.dashboard_security.password = password;
        }
        break;
      }

      default:
        return;
    }

    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      let result = null;
      try {
        result = await res.json();
      } catch (_) {
        result = null;
      }
      if (!res.ok) {
        const detail = result?.error || result?.message || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      if (section === 'dashboard_security') {
        this.showToast('密码设置已保存，正在刷新...', 'success');
        setTimeout(() => window.location.reload(), 800);
        return;
      }
      const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
      if (warnings.length > 0) {
        const warningText = warnings.map(item => `${item.channel || 'channel'}: ${item.error || 'unknown error'}`).join('；');
        this.showToast(`已保存，但部分通道启动失败：${warningText}`, 'warning');
      } else {
        this.showToast('已保存', 'success');
      }
    } catch (err) {
      this.showToast(`保存失败: ${err.message}`, 'error');
    }
  }

  async exportDataBackup() {
    try {
      const res = await this.apiFetch('/api/data/export');
      if (!res.ok) throw new Error('Export failed');
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const link = document.createElement('a');
      link.href = url;
      link.download = `aelios-backup-${stamp}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      this.showToast('导出成功', 'success');
    } catch (err) {
      this.showToast(`导出失败: ${err.message}`, 'error');
    }
  }

  openImportDataPicker() {
    const input = document.getElementById('data-import-input');
    if (!input) return;
    input.value = '';
    input.click();
  }

  async importDataBackup(event) {
    const file = event?.target?.files?.[0];
    if (!file) return;

    try {
      const raw = await file.text();
      const payload = JSON.parse(raw);
      const res = await this.apiFetch('/api/data/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Import failed');
      const result = await res.json();
      const imported = result.imported || {};
      this.showToast(`导入成功：人设 ${imported.persona ? '已更新' : '未变更'}，记忆 ${imported.memories || 0} 条，日志 ${imported.logs || 0} 条`, 'success');
      await Promise.all([this.renderSettings(), this.renderMemories()]);
    } catch (err) {
      this.showToast(`导入失败: ${err.message}`, 'error');
    } finally {
      if (event?.target) event.target.value = '';
    }
  }

  // ------------------------------------------
  // Theme
  // ------------------------------------------
  setTheme(theme) {
    if (theme === 'pink') {
      document.body.removeAttribute('data-theme');
    } else {
      document.body.setAttribute('data-theme', theme);
    }
    localStorage.setItem('saki_theme', theme);

    // Update theme selector active state
    document.querySelectorAll('.theme-option').forEach(el => el.classList.remove('active'));
    // Re-render is simplest
    if (this.currentPage === 'settings') {
      this.renderSettings();
    }
  }

  applyTheme(theme) {
    if (theme && theme !== 'pink') {
      document.body.setAttribute('data-theme', theme);
    }
  }

  themePreviewColor(theme) {
    const map = {
      pink: '#F3E5E9',
      blue: '#E3EFF9',
      purple: '#EDE5F3',
      green: '#E5F3E9',
      orange: '#F3ECE5',
    };
    return map[theme] || '#F3E5E9';
  }

  // ------------------------------------------
  // Toast
  // ------------------------------------------
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.classList.add('show');
    });

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ------------------------------------------
  // Modal
  // ------------------------------------------
  showModal(title, bodyHtml, footerHtml = '') {
    const overlay = document.getElementById('modal-overlay');
    const titleEl = document.getElementById('modal-title');
    const bodyEl = document.getElementById('modal-body');
    const footerEl = document.getElementById('modal-footer');

    if (titleEl) titleEl.textContent = title;
    if (bodyEl) bodyEl.innerHTML = bodyHtml;
    if (footerEl) footerEl.innerHTML = footerHtml;

    if (overlay) {
      overlay.style.display = 'flex';
      requestAnimationFrame(() => overlay.classList.add('show'));
    }
  }

  hideModal() {
    const overlay = document.getElementById('modal-overlay');
    if (!overlay) return;
    overlay.classList.remove('show');
    setTimeout(() => {
      overlay.style.display = 'none';
    }, 300);
  }

  // ------------------------------------------
  // Utilities
  // ------------------------------------------
  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  escAttr(str) {
    return (str || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  formatTime(date) {
    if (!(date instanceof Date) || isNaN(date)) return '';
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
  }

  formatDate(date) {
    if (!(date instanceof Date) || isNaN(date)) return '';
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  }

  formatDateTime(date) {
    if (!(date instanceof Date) || isNaN(date)) return '';
    return `${this.formatDate(date)} ${this.formatTime(date)}`;
  }

  generateId() {
    return 'id_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
  }

  getVal(id) {
    const el = document.getElementById(id);
    return el ? (el.value || '') : '';
  }

  getChecked(id) {
    const el = document.getElementById(id);
    return el ? el.checked : false;
  }

  getOptionalNumber(id) {
    const raw = this.getVal(id).trim();
    if (!raw) return undefined;
    const value = parseInt(raw, 10);
    return Number.isFinite(value) ? value : undefined;
  }
}

// ============================================
// Bootstrap
// ============================================
if (
  typeof window !== 'undefined' &&
  typeof document !== 'undefined' &&
  !window.__SAKI_DISABLE_BOOTSTRAP__
) {
  window.app = new SakiPhoneApp();
}

if (typeof module !== 'undefined') {
  module.exports = { SakiPhoneApp, svgIcon };
}
