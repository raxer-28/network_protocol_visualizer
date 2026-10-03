/**
 * mail.js — Mail activity module
 * Handles compose form, calls /api/mail, updates activity log + visualizer.
 */

(function () {
  'use strict';

  const API_BASE = '';

  function getEl(id) { return document.getElementById(id); }

  function logLine(text, type = 'info') {
    const el = getEl('mail-log-content');
    if (!el) return;
    const color = type === 'success' ? 'var(--green)'
                : type === 'error'   ? 'var(--red)'
                : type === 'cmd'     ? 'var(--cyan)'
                : type === 'tls'     ? 'var(--tls-color)'
                : type === 'tcp'     ? 'var(--tcp-color)'
                : type === 'phase'   ? 'var(--smtp-color)'
                : 'var(--text-secondary)';
    const time = new Date().toLocaleTimeString();
    el.innerHTML += `<div style="color:${color};margin:2px 0;">[${time}] ${text}</div>`;
    el.scrollTop = el.scrollHeight;
  }

  function logSeparator(label) {
    const el = getEl('mail-log-content');
    if (!el) return;
    el.innerHTML += `<div style="color:var(--border-focus);margin:6px 0;border-top:1px solid var(--border);padding-top:6px;font-size:10px;letter-spacing:1px;">── ${label} ──</div>`;
    el.scrollTop = el.scrollHeight;
  }

  function clearLog() {
    const el = getEl('mail-log-content');
    if (el) el.innerHTML = '';
  }

  function setStatus(text, type = '') {
    const el = getEl('mail-send-status');
    if (el) {
      el.textContent = text;
      el.style.color = type === 'success' ? 'var(--green)'
                     : type === 'error'   ? 'var(--red)'
                     : 'var(--text-secondary)';
    }
  }

  function setModeIndicator(simulate) {
    const el = getEl('mail-mode-indicator');
    if (!el) return;
    if (simulate) {
      el.textContent = '⚙ SIMULATION MODE';
      el.style.color = 'var(--tls-color)';
      el.style.borderColor = 'var(--tls-color)';
    } else {
      el.textContent = '📡 LIVE SMTP MODE';
      el.style.color = 'var(--green)';
      el.style.borderColor = 'var(--green)';
    }
    el.style.display = 'inline-block';
  }

  function logStepSummary(steps, simulate) {
    if (!steps || !steps.length) return;
    const byPhase = {};
    steps.forEach(s => {
      byPhase[s.phase] = (byPhase[s.phase] || 0) + 1;
    });
    logSeparator('PROTOCOL STEP SUMMARY');
    const modeLabel = simulate ? 'SIMULATED' : 'LIVE';
    logLine(`Mode: ${modeLabel} | Total steps captured: ${steps.length}`, 'phase');
    Object.entries(byPhase).forEach(([phase, count]) => {
      const color = phase === 'TCP' ? 'tcp'
                  : phase === 'TLS' ? 'tls'
                  : phase === 'SMTP' ? 'phase'
                  : phase === 'DNS' ? 'info'
                  : 'info';
      logLine(`  [${phase}]  ${count} step${count !== 1 ? 's' : ''}`, color);
    });
    const transportCount = steps.filter(s => s.layer === 'transport').length;
    const appCount = steps.filter(s => s.layer === 'application').length;
    logLine(`  App-layer: ${appCount} | Transport-layer: ${transportCount}`, 'info');
  }

  const mailModule = {
    async send() {
      const toEl      = getEl('mail-to');
      const subjEl    = getEl('mail-subject');
      const bodyEl    = getEl('mail-body');
      const sendBtn   = getEl('btn-send');

      const to      = toEl?.value?.trim()   || '';
      const subject = subjEl?.value?.trim() || '';
      const body    = bodyEl?.value?.trim() || '';
      const simulate = getEl('mail-simulate')?.checked || false;

      // Validate
      if (!to || !to.includes('@')) {
        window.app.toast('Please enter a valid recipient email', 'error');
        toEl?.focus();
        return;
      }
      if (!subject) {
        window.app.toast('Subject cannot be empty', 'error');
        subjEl?.focus();
        return;
      }
      if (!body) {
        window.app.toast('Body cannot be empty', 'error');
        bodyEl?.focus();
        return;
      }

      if (sendBtn) sendBtn.disabled = true;
      clearLog();
      setStatus('📤 Sending…');
      setModeIndicator(simulate);

      // ── Phase 1: DNS ───────────────────────────────────────────
      logSeparator('PHASE 1 — DNS');
      logLine(`Recipient domain: ${to.split('@')[1] || 'unknown'}`, 'info');
      logLine('Performing DNS MX lookup for recipient domain…', 'tcp');

      // ── Phase 2: TCP ───────────────────────────────────────────
      logSeparator('PHASE 2 — TCP + SMTP');
      if (simulate) {
        logLine('⚙  Simulation mode — no real email will be sent', 'tls');
      } else {
        logLine('📡 Live mode — connecting to smtp.gmail.com:587', 'phase');
      }
      logLine(`To: ${to}  |  Subject: "${subject}"`, 'cmd');

      window.visualizer.showLoading('DNS MX lookup + TCP connect + SMTP handshake…');

      try {
        const res = await fetch(`${API_BASE}/api/mail`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ to, subject, body, simulate }),
        });

        if (!res.ok) {
          throw new Error(`Server error: ${res.status} ${res.statusText}`);
        }

        const data = await res.json();

        // ── Phase 3: Result ────────────────────────────────────
        logSeparator('PHASE 3 — RESULT');

        if (data.success) {
          setStatus('✅ Sent!', 'success');
          logLine(`✓ ${simulate ? 'Simulation' : 'Email'} completed for → ${to}`, 'success');
          window.app.toast(simulate ? `Simulation done! (${data.steps?.length || 0} steps)` : `Email sent to ${to}!`, 'success');
        } else {
          setStatus('❌ Failed', 'error');
          logLine(`✗ ${simulate ? 'Simulation' : 'Send'} failed: ${data.error || 'Unknown error'}`, 'error');
          if (data.error?.includes('.env')) {
            logLine('ℹ️  Tip: Copy .env.example → .env and fill in Gmail App Password', 'info');
            logLine('ℹ️  Or tick "Simulate SMTP" to see the full protocol without sending', 'info');
          }
          window.app.toast(data.error || 'Failed', 'error');
        }

        // Show summary breakdown in the log
        logStepSummary(data.steps, simulate);

        // Load SMTP steps into visualizer
        if (data.steps && data.steps.length > 0) {
          window.visualizer.loadSteps(data.steps);
        }

      } catch (err) {
        setStatus('❌ Error', 'error');
        logSeparator('ERROR');
        logLine(`Error: ${err.message}`, 'error');
        window.visualizer.showError(`Failed: ${err.message}`);
        window.app.toast(err.message, 'error');
      } finally {
        if (sendBtn) sendBtn.disabled = false;
        setTimeout(() => setStatus(''), 6000);
      }
    },
  };

  window.mailModule = mailModule;
})();
