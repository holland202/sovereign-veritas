// STD-2 (docs/STD2_PREREG.md): three adapters that are deliberately NOT security products.
// MODE is fixed per file by the thin wrappers silent.cjs / echo.cjs / flag.cjs.
const ALL = ['process-monitoring', 'network-monitoring', 'filesystem-monitoring', 'prompt-input-scanning',
  'prompt-output-scanning', 'mcp-scanning', 'a2a-scanning', 'anomaly-detection', 'budget-management',
  'enforcement-log', 'enforcement-alert', 'enforcement-pause', 'enforcement-kill', 'enforcement-resume',
  'pattern-scanning', 'event-correlation'];

module.exports = function make(MODE) {
  let n = 0;
  const flag = MODE === 'flag';
  const scan = (text) => flag
    ? { detected: true, matches: [{ pattern: { id: 'STD2-ALL', category: 'std2', description: 'flags everything', pattern: /.*/, severity: 'critical' }, matchedText: String(text).slice(0, 80) }] }
    : { detected: false, matches: [] };

  return class Std2Adapter {
    constructor() { this.events = []; this.enf = []; this.handlers = []; }
    getCapabilities() { return { product: 'std2-' + MODE, version: '0', capabilities: new Set(ALL) }; }
    async start() {}
    async stop() {}
    _record(e) {
      const ev = { id: 'std2-' + (++n), timestamp: new Date().toISOString(), classifiedBy: 'std2-' + MODE, data: {}, ...e };
      if (flag) { ev.category = 'threat'; ev.severity = 'critical'; }
      if (MODE !== 'silent') { this.events.push(ev); for (const h of this.handlers) { try { h(ev); } catch (_) {} } }
      if (flag) this.enf.push({ action: 'alert', success: true, reason: 'std2 flags everything', event: ev });
      return ev;
    }
    async injectEvent(e) { return this._record(e); }
    waitForEvent(pred, timeoutMs = 2000) {
      const hit = this.events.find(pred);
      if (hit) return Promise.resolve(hit);
      return new Promise((resolve, reject) => {
        const h = (ev) => { if (pred(ev)) { clearTimeout(t); resolve(ev); } };
        this.handlers.push(h);
        const t = setTimeout(() => reject(new Error('std2-' + MODE + ': no matching event')), timeoutMs);
      });
    }
    getEvents() { return this.events.slice(); }
    getEventsByCategory(c) { return this.events.filter((e) => e.category === c); }
    getEnforcements() { return this.enf.slice(); }
    getEnforcementsByAction(a) { return this.enf.filter((r) => r.action === a); }
    resetCollector() { this.events = []; this.enf = []; }
    getEventEngine() { return { emit: (e) => this._record(e), onEvent: (h) => { this.handlers.push(h); } }; }
    getEnforcementEngine() {
      return {
        execute: async (action, event) => { const r = { action, success: flag, reason: 'std2-' + MODE, event }; if (flag) this.enf.push(r); return r; },
        pause: () => flag, resume: () => flag, kill: () => flag, getPausedPids: () => [], setAlertCallback: () => {},
      };
    }
    createPromptScanner() { return { start: async () => {}, stop: async () => {}, scanInput: scan, scanOutput: scan }; }
    createMCPScanner() { return { start: async () => {}, stop: async () => {}, scanToolCall: (t, p) => scan(t + JSON.stringify(p || {})) }; }
    createA2AScanner() { return { start: async () => {}, stop: async () => {}, scanMessage: (f, t, c) => scan(c) }; }
    createPatternScanner() {
      const pats = flag ? [scan('x').matches[0].pattern] : [];
      return { scanText: (t) => scan(t), getAllPatterns: () => pats, getPatternSets: () => (flag ? { std2: pats } : {}) };
    }
    createBudgetManager(_dir, cfg = {}) {
      const budget = cfg.budgetUsd ?? 5, maxCalls = cfg.maxCallsPerHour ?? 100;
      return {
        canAfford: () => !flag, record: () => {}, reset: () => {},
        getStatus: () => ({ spent: 0, budget, remaining: budget, percentUsed: 0, callsThisHour: 0, maxCallsPerHour: maxCalls, totalCalls: 0 }),
      };
    }
    createAnomalyScorer() {
      return { score: () => (flag ? 100 : 0), record: () => {}, getBaseline: () => null, reset: () => {} };
    }
  };
};
