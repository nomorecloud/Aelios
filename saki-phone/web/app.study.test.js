const test = require('node:test');
const assert = require('node:assert/strict');

global.window = { __SAKI_DISABLE_BOOTSTRAP__: true };
global.document = {
  createElement() {
    return {
      _text: '',
      set textContent(value) { this._text = String(value ?? ''); },
      get textContent() { return this._text; },
      get innerHTML() {
        return this._text
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
      },
    };
  },
  getElementById() {
    return null;
  },
  addEventListener() {},
  querySelectorAll() { return []; },
};

const { SakiPhoneApp } = require('./app.js');

function makeApp() {
  const app = Object.create(SakiPhoneApp.prototype);
  app.studyWindowDays = 7;
  app.studyData = null;
  app.showToast = () => {};
  return app;
}

test('buildStudyPageMarkup renders no-active-session empty state', () => {
  const app = makeApp();
  const html = app.buildStudyPageMarkup({
    activeSession: null,
    inspectionSession: null,
    recentSessions: [],
    progress: { metrics: { completion_rate: 0 }, focus_balance: { totals: {}, ratios: {} }, summary_text: {} },
    events: [],
    responses: [],
    framework: null,
    checkins: [],
    error: '',
  });

  assert.match(html, /当前没有进行中的学习会话/);
  assert.match(html, /暂无事件记录/);
  assert.match(html, /暂无陪伴回应/);
});

test('buildStudyPageMarkup renders active session, responses, and progress summary', () => {
  const app = makeApp();
  const html = app.buildStudyPageMarkup({
    activeSession: {
      id: 'learn_1',
      title: '线代复习',
      mode: 'focus',
      runtime_state: 'focus',
      elapsed_minutes: 15,
      planned_minutes: 25,
      remaining_minutes: 10,
      break_count: 1,
      pomodoro_count: 1,
    },
    inspectionSession: { id: 'learn_1', title: '线代复习' },
    recentSessions: [{ id: 'learn_1', title: '线代复习' }],
    progress: {
      window: { label: 'last 7 days' },
      metrics: {
        completion_rate: 0.5,
        sessions_started: 4,
        sessions_completed: 2,
        sessions_abandoned: 2,
        total_focus_minutes: 40,
        pause_resume: { friction_score: 1.5 },
      },
      focus_balance: {
        totals: { focus_minutes: 20, review_minutes: 10, recovery_minutes: 5 },
        ratios: { focus_ratio: 0.571, review_ratio: 0.286, recovery_ratio: 0.143 },
      },
      summary_text: {
        weekly_summary: 'In the last 7 days window there were 4 study sessions.',
        momentum_check: 'Momentum is mixed.',
        blocker_focus_balance_note: 'Recent time split was 20 focus / 10 review / 5 recovery minutes.',
      },
      friction_patterns: {
        patterns: [{ label: 'Frequent long pauses', reason: '2 sessions had long pauses.' }],
      },
    },
    events: [{ event_type: 'session_started', runtime_state: 'focus', created_at: '2026-03-21T08:00:00' }],
    responses: [{
      event_type: 'low_energy_start',
      created_at: '2026-03-21T08:01:00',
      message: '先把目标缩成最小一步。',
      response_context: { recovery_state: { state: 'low_energy' }, next_step: { label: '先做最小动作' } },
    }],
    framework: { recovery_state: { state: 'low_energy' } },
    checkins: [],
    error: '',
  });

  assert.match(html, /线代复习/);
  assert.match(html, /低能量|low_energy/);
  assert.match(html, /先把目标缩成最小一步/);
  assert.match(html, /Momentum is mixed/);
  assert.match(html, /Frequent long pauses/);
});

test('startStudySession posts to the backend start endpoint', async () => {
  const app = makeApp();
  const values = {
    'study-title': '英语复盘',
    'study-goal': '看错题',
    'study-mode': 'review',
    'study-planned-minutes': '20',
  };
  global.document.getElementById = (id) => ({ value: values[id] || '' });

  let captured = null;
  let refreshed = false;
  app.getJson = async (url, options = {}) => {
    captured = { url, options };
    return { item: { id: 'learn_1' } };
  };
  app.refreshStudyData = async () => { refreshed = true; };

  await app.startStudySession();

  assert.equal(captured.url, '/api/learning-sessions/start');
  const body = JSON.parse(captured.options.body);
  assert.equal(body.title, '英语复盘');
  assert.equal(body.goal, '看错题');
  assert.equal(body.mode, 'review');
  assert.equal(body.planned_minutes, 20);
  assert.equal(refreshed, true);
});

test('studyRuntimeAction sends the active session runtime request', async () => {
  const app = makeApp();
  app.studyData = {
    activeSession: { id: 'learn_9', elapsed_minutes: 8, remaining_minutes: 17 },
  };
  let captured = null;
  app.getJson = async (url, options = {}) => {
    captured = { url, options };
    return { item: { id: 'learn_9' } };
  };
  app.refreshStudyData = async () => {};

  await app.studyRuntimeAction('pause');

  assert.equal(captured.url, '/api/learning-sessions/learn_9/runtime');
  assert.equal(JSON.parse(captured.options.body).action, 'pause');
});

test('buildStudyPageMarkup shows backend error state clearly', () => {
  const app = makeApp();
  const html = app.buildStudyPageMarkup({
    activeSession: null,
    inspectionSession: null,
    recentSessions: [],
    progress: null,
    events: [],
    responses: [],
    framework: null,
    checkins: [],
    error: 'backend offline',
  });

  assert.match(html, /学习面板加载失败/);
  assert.match(html, /backend offline/);
});
