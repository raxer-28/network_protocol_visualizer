/**
 * visualizer.js — Protocol step renderer + playback controller
 * Manages the right panel: renders ProtocolStep cards, handles
 * play/pause/step-forward/step-backward/replay/speed and dynamic step appending.
 */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────
  let _allSteps = [];       // all raw steps
  let _steps = [];          // filtered steps for current layer
  let _revealed = 0;        // how many are currently shown
  let _playing = false;
  let _timer = null;
  let _speed = 1000;        // ms per step
  let _currentLayer = 'application'; // 'application' | 'transport'

  // ── DOM refs ────────────────────────────────────────────────
  const container   = () => document.getElementById('steps-container');
  const emptyState  = () => document.getElementById('visualizer-empty');
  const pbFill      = () => document.getElementById('pb-fill');
  const pbCounter   = () => document.getElementById('pb-counter');
  const pbPlayPause = () => document.getElementById('pb-playpause');

  const btns = {
    first:    () => document.getElementById('pb-first'),
    prev:     () => document.getElementById('pb-prev'),
    next:     () => document.getElementById('pb-next'),
    last:     () => document.getElementById('pb-last'),
    replay:   () => document.getElementById('pb-replay'),
    playpause:() => document.getElementById('pb-playpause'),
  };

  // ── Helpers ─────────────────────────────────────────────────
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatTime(ms) {
    if (ms < 1000) return `+${Math.round(ms)}ms`;
    return `+${(ms / 1000).toFixed(2)}s`;
  }

  function buildHighlightPills(fields) {
    if (!fields || !fields.length) return '';
    return `<div class="highlight-fields">
      ${fields.map(f => `
        <div class="highlight-pill">
          <span class="highlight-key">${escapeHtml(f.key)}:</span>
          <span class="highlight-val">${escapeHtml(f.value)}</span>
        </div>
      `).join('')}
    </div>`;
  }

  function buildCard(step) {
    const isError = step.is_error ? ' error-step' : '';
    const layerCls = ` layer-${step.layer || 'application'}`;
    const card = document.createElement('div');
    card.className = `step-card${isError}${layerCls}`;
    card.dataset.id = step.id;
    card.dataset.direction = step.direction;

    const isClient = step.direction === 'client→server';
    const isServer = step.direction === 'server→client';
    const alignClass = isClient ? 'align-left' : (isServer ? 'align-right' : 'align-center');
    const labelHeader = isClient ? 'Client --&gt; Server' : (isServer ? 'Client &lt;-- Server' : 'SYSTEM');

    card.innerHTML = `
      <div class="step-header ${alignClass}" onclick="window.visualizer.toggleExpand(this.parentElement)" aria-expanded="false">
        <span class="step-num">${String(step.id).padStart(2, '0')}</span>
        <span class="client-server-label">${labelHeader}</span>
        <span class="phase-badge phase-${escapeHtml(step.phase)}">[${escapeHtml(step.phase)}]</span>
        <span class="step-label">${escapeHtml(step.label)}</span>
        <span class="step-time">${formatTime(step.timestamp_ms)}</span>
        <span class="step-expand-icon" aria-hidden="true">v</span>
      </div>
      <div class="step-line ${alignClass}"></div>
      <div class="step-detail" aria-hidden="true">
        <pre>${escapeHtml(step.detail)}</pre>
        ${buildHighlightPills(step.highlight_fields)}
      </div>
    `;
    return card;
  }

  function updateProgress() {
    const total = _steps.length;
    const revealed = _revealed;
    const pct = total > 0 ? Math.round((revealed / total) * 100) : 0;

    const fill = pbFill();
    if (fill) fill.style.width = pct + '%';
    const counter = pbCounter();
    if (counter) counter.textContent = `${revealed} / ${total}`;

    const disabled = total === 0;
    if (btns.first()) btns.first().disabled    = disabled || revealed <= 1;
    if (btns.prev()) btns.prev().disabled     = disabled || revealed <= 1;
    if (btns.next()) btns.next().disabled     = disabled || revealed >= total;
    if (btns.last()) btns.last().disabled     = disabled || revealed >= total;
    if (btns.replay()) btns.replay().disabled   = disabled;
    if (btns.playpause()) btns.playpause().disabled = disabled;
  }

  function revealNext() {
    if (_revealed >= _steps.length) {
      pause();
      return;
    }
    const step = _steps[_revealed];
    _revealed++;

    // Remove empty state on first reveal
    const empty = emptyState();
    if (empty) empty.style.display = 'none';

    const c = container();
    if (!c) return;

    const card = buildCard(step);
    c.appendChild(card);

    // Trigger animation
    requestAnimationFrame(() => {
      card.classList.add('revealed');
      // Auto-expand if only few steps
      if (_steps.length <= 3) card.classList.add('expanded');
    });

    // Mark this as the currently active step
    c.querySelectorAll('.step-card.active-step').forEach(el => el.classList.remove('active-step'));
    card.classList.add('active-step');

    // Smoothly scroll the container to the newly revealed step
    c.scrollTop = c.scrollHeight;

    updateProgress();
  }

  function hideStep(index) {
    const c = container();
    if (!c) return;
    const cards = c.querySelectorAll('.step-card');
    if (cards.length > 0) {
      const last = cards[cards.length - 1];
      last.remove();
      _revealed = Math.max(0, _revealed - 1);
    }
    if (_revealed === 0) {
      const empty = emptyState();
      if (empty) empty.style.display = '';
    }
    updateProgress();

    // Re-mark active step
    const remaining = c.querySelectorAll('.step-card');
    c.querySelectorAll('.step-card.active-step').forEach(el => el.classList.remove('active-step'));
    if (remaining.length > 0) {
      remaining[remaining.length - 1].classList.add('active-step');
    }
  }

  // ── Public API ───────────────────────────────────────────────
  const visualizer = {

    /** Switch between 'application' and 'transport' layer views */
    switchLayer(layer) {
      if (_currentLayer === layer) return;
      _currentLayer = layer;

      // Update tab buttons
      const tabApp = document.getElementById('tab-layer-application');
      const tabTrans = document.getElementById('tab-layer-transport');
      if (tabApp) {
        tabApp.classList.toggle('active', layer === 'application');
      }
      if (tabTrans) {
        tabTrans.classList.toggle('active', layer === 'transport');
      }

      // Re-filter and reload
      _steps = _allSteps.filter(s => s.layer === layer || s.direction === 'info');
      this._resetAndPlay();
    },

    _resetAndPlay(options = {}) {
      _revealed = 0;
      _playing = false;
      clearInterval(_timer);

      const c = container();
      const empty = emptyState();
      if (c) {
        c.querySelectorAll('.step-card, .loading-row').forEach(el => el.remove());
      }
      if (empty) empty.style.display = '';

      if (pbFill()) pbFill().style.width = '0%';
      if (pbCounter()) pbCounter().textContent = `0 / ${_steps.length}`;

      if (_steps.length === 0) {
        updateProgress();
        return;
      }

      updateProgress();
      if (options.fast) {
        this.goLast();
      } else {
        this.play();
      }
    },

    /** Load a fresh set of steps and reset panel */
    loadSteps(steps, options = {}) {
      _allSteps = steps ? [...steps] : [];
      _steps = _allSteps.filter(s => s.layer === _currentLayer || s.direction === 'info');
      this._resetAndPlay(options);
    },

    /** Append steps without clearing previous activity */
    appendSteps(newSteps, options = {}) {
      if (!newSteps || newSteps.length === 0) return;

      const c = container();
      if (c) {
        // Remove any loading spinners
        c.querySelectorAll('.loading-row').forEach(el => el.remove());
      }
      const empty = emptyState();
      if (empty) empty.style.display = 'none';

      const baseId = _allSteps.length;
      newSteps.forEach((s, idx) => {
        const copy = Object.assign({}, s);
        copy.id = baseId + idx + 1;
        _allSteps.push(copy);
        if (copy.layer === _currentLayer || copy.direction === 'info') {
          _steps.push(copy);
        }
      });

      updateProgress();

      if (options.fast || options.live !== false) {
        // Reveal immediately
        while (_revealed < _steps.length) {
          revealNext();
        }
      } else {
        this.play();
      }
    },

    play() {
      if (_playing) return;
      if (_revealed >= _steps.length) {
        this.replay();
        return;
      }
      _playing = true;
      const pp = pbPlayPause();
      if (pp) {
        pp.textContent = '||';
        pp.classList.add('active');
      }
      _timer = setInterval(() => {
        if (_revealed >= _steps.length) {
          this.pause();
        } else {
          revealNext();
        }
      }, _speed);
    },

    pause() {
      _playing = false;
      clearInterval(_timer);
      const pp = pbPlayPause();
      if (pp) {
        pp.textContent = '>';
        pp.classList.remove('active');
      }
    },

    togglePlay() {
      if (_playing) this.pause();
      else this.play();
    },

    stepForward() {
      this.pause();
      revealNext();
    },

    stepBack() {
      this.pause();
      if (_revealed > 1) hideStep(_revealed - 1);
    },

    goFirst() {
      this.pause();
      const c = container();
      if (c) {
        c.querySelectorAll('.step-card').forEach(el => el.remove());
      }
      _revealed = 0;
      const empty = emptyState();
      if (empty) empty.style.display = '';
      updateProgress();
      revealNext();
    },

    goLast() {
      this.pause();
      while (_revealed < _steps.length) {
        revealNext();
      }
    },

    replay() {
      this.pause();
      const c = container();
      if (c) {
        c.querySelectorAll('.step-card').forEach(el => el.remove());
      }
      _revealed = 0;
      const empty = emptyState();
      if (empty) empty.style.display = '';
      updateProgress();
      setTimeout(() => this.play(), 150);
    },

    setSpeed(ms) {
      _speed = parseInt(ms, 10);
      if (_playing) {
        this.pause();
        this.play();
      }
    },

    toggleExpand(card) {
      if (!card) return;
      card.classList.toggle('expanded');
      const header = card.querySelector('.step-header');
      if (header) {
        header.setAttribute('aria-expanded', card.classList.contains('expanded'));
      }
      const detail = card.querySelector('.step-detail');
      if (detail) {
        detail.setAttribute('aria-hidden', !card.classList.contains('expanded'));
      }
      const icon = card.querySelector('.step-expand-icon');
      if (icon) {
        icon.textContent = card.classList.contains('expanded') ? '^' : 'v';
      }
    },

    /** Show a loading status without clearing if appending */
    showLoading(message = 'Resolving DNS / HTTP handshake…', isAppend = false) {
      const c = container();
      if (!c) return;

      if (!isAppend) {
        c.querySelectorAll('.step-card, .loading-row').forEach(el => el.remove());
        const empty = emptyState();
        if (empty) empty.style.display = 'none';
        _allSteps = [];
        _steps = [];
        _revealed = 0;
        updateProgress();
      }

      const row = document.createElement('div');
      row.className = 'loading-row';
      row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;color:var(--term-green-dim);font-size:11.5px;';
      row.innerHTML = `<span class="spinner"></span><span>&gt; ${escapeHtml(message)}</span>`;
      c.appendChild(row);
      c.scrollTop = c.scrollHeight;
    },

    /** Show error */
    showError(message) {
      const c = container();
      if (!c) return;
      c.querySelectorAll('.loading-row').forEach(el => el.remove());

      const row = document.createElement('div');
      row.className = 'step-card error-step';
      row.style.cssText = 'padding:10px;color:var(--term-red);font-size:11.5px;line-height:1.5;';
      row.innerHTML = `<strong>[!] ERROR:</strong> ${escapeHtml(message)}`;
      c.appendChild(row);
      c.scrollTop = c.scrollHeight;
      updateProgress();
    },
  };

  window.visualizer = visualizer;
})();
