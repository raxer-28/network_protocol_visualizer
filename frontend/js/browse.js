/**
 * browse.js — Browsing activity module
 * Handles URL visit, calls /api/browse, updates iframe + visualizer.
 * Supports appending steps for in-page navigation without resetting.
 */

(function () {
  'use strict';

  const API_BASE = '';  // same-origin when served from FastAPI

  function getEl(id) { return document.getElementById(id); }

  function setStatus(text, type = 'idle') {
    const dot  = getEl('browse-status-dot');
    const span = getEl('browse-status-text');
    if (dot)  dot.className = `status-dot ${type}`;
    if (span) span.textContent = text;
  }

  function updateLockIcon(url) {
    const icon = getEl('lock-icon');
    if (!icon) return;
    if (url.startsWith('https://')) {
      icon.textContent = '[*]';
      icon.title = 'Secure connection (HTTPS)';
    } else {
      icon.textContent = '[!]';
      icon.title = 'Insecure connection (HTTP)';
    }
  }

  const browseModule = {
    async visit(targetUrl = null, options = {}) {
      const inputEl  = getEl('url-input');
      const visitBtn = getEl('btn-visit');
      const iframe   = getEl('browse-iframe');
      const isInternal = options.isInternal === true;

      let url = (targetUrl || inputEl?.value || '').trim();
      if (!url) {
        window.app.toast('Please enter a URL', 'error');
        return;
      }
      if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
      }
      if (inputEl) inputEl.value = url;

      updateLockIcon(url);

      if (visitBtn) visitBtn.disabled = true;
      setStatus('Resolving DNS…', 'loading');

      if (isInternal) {
        window.visualizer.showLoading('In-page navigation: DNS & HTTP lookup…', true);
      } else {
        window.visualizer.showLoading('DNS lookup + HTTP request…', false);
      }

      try {
        const res = await fetch(`${API_BASE}/api/browse`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        });

        if (!res.ok) {
          throw new Error(`Server error: ${res.status} ${res.statusText}`);
        }

        const data = await res.json();

        // ── Update iframe
        if (iframe) {
          setStatus('Loading page…', 'loading');
          iframe.src = data.proxy_url;
          iframe.onload = () => {
            if (data.success) {
              setStatus(`OK: ${url}`, 'success');
            } else {
              setStatus(`Loaded with warnings: ${data.error || ''}`, 'error');
            }
          };
          iframe.onerror = () => setStatus('Failed to load page', 'error');
        }

        // ── Load or Append protocol steps
        if (data.steps && data.steps.length > 0) {
          if (isInternal) {
            window.visualizer.appendSteps(data.steps, { live: true });
            window.app.toast(`Appended ${data.steps.length} steps from page activity`, 'info');
          } else {
            window.visualizer.loadSteps(data.steps);
            window.app.toast(`${data.steps.length} protocol steps captured`, 'info');
          }
        } else {
          window.visualizer.showError('No protocol steps returned. Check backend logs.');
        }

      } catch (err) {
        setStatus(`Error: ${err.message}`, 'error');
        window.visualizer.showError(`Failed to fetch: ${err.message}`);
        window.app.toast(err.message, 'error');
      } finally {
        if (visitBtn) visitBtn.disabled = false;
      }
    },
  };

  document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('url-input');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          // Manual entry: reset steps
          browseModule.visit(input.value, { isInternal: false });
        }
      });
    }

    // Listen for navigation messages from the proxied iframe
    window.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'NPV_NAVIGATE') {
        const newUrl = event.data.url;
        if (newUrl) {
          // In-page activity: DO NOT reset steps, append them!
          browseModule.visit(newUrl, { isInternal: true });
        }
      }
    });
  });

  window.browseModule = browseModule;
})();
