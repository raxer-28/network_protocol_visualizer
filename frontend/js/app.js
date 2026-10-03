/**
 * app.js — Global application controller
 * Manages tab switching and toast notifications.
 */

(function () {
  'use strict';

  const TABS = ['browse', 'mail', 'stream'];

  const appModule = {

    /** Switch the active activity tab */
    switchTab(name) {
      if (!TABS.includes(name)) return;

      // Update tab buttons
      TABS.forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        if (btn) {
          btn.classList.toggle('active', t === name);
          btn.setAttribute('aria-selected', t === name ? 'true' : 'false');
        }
      });

      // Show / hide sections
      TABS.forEach(t => {
        const section = document.getElementById(`${t}-section`);
        if (section) {
          section.classList.toggle('active', t === name);
        }
      });
    },

    /**
     * Show a toast notification.
     * @param {string} message
     * @param {'success'|'error'|'info'} type
     * @param {number} durationMs
     */
    toast(message, type = 'info', durationMs = 3500) {
      const container = document.getElementById('toast-container');
      if (!container) return;

      const icon = type === 'success' ? '✅'
                 : type === 'error'   ? '❌'
                 : 'ℹ️';

      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
      container.appendChild(toast);

      // Auto-dismiss
      setTimeout(() => {
        toast.style.transition = 'opacity .3s ease, transform .3s ease';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 350);
      }, durationMs);
    },
  };

  // Expose globally for inline onclick handlers
  window.app = appModule;
})();
