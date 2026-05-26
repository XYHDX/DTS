/* ────────────────────────────────────────────────────────────────────────────
 *  _shell.js — wires up the admin chrome that's identical on every page:
 *    • Auth gate (redirect to /admin/login.html if no token)
 *    • Render the logged-in user's name/role/initial into the sidebar
 *    • Wire the logout button
 *    • Wire the bilingual (AR/EN) toggle button, hooking into /lib/i18n.js
 *    • Mark the active nav link via `data-page` attribute on <body>
 *
 *  Usage in each sub-page HTML:
 *    <body data-page="vehicles">       (or "users", "routes", "alerts")
 *    <script src="/lib/i18n.js"></script>
 *    <script src="/admin/_shell.js" defer></script>
 *
 *  This script does NOT fetch the page's own data — each sub-page handles that
 *  inline. _shell.js only owns the chrome.
 * ──────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  const TOKEN_KEY = 'dt_token';
  const USER_KEY  = 'dt_user';

  // ── Auth gate ───────────────────────────────────────────────────────────────
  // Token + user may live in either localStorage (remember-me checked) or
  // sessionStorage (single-session login).
  let token = null, user = null;
  try {
    token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
    user  = rawUser ? JSON.parse(rawUser) : null;
  } catch (_) {}
  if (!token) {
    // Not signed in — bounce to login.
    window.location.replace('/admin/login.html');
    return;
  }

  // ── Lift the head-injected visibility cloak (added by _gate.js) ────────────
  document.documentElement.dataset.auth = 'ok';

  // ── Render sidebar user block ───────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const initial = (user?.name || user?.email || '?').trim().charAt(0).toUpperCase();
    setText('#user-initial', initial);
    setText('#user-name',    user?.name || user?.email || '—');
    setText('#user-role',    (user?.role || 'admin').toUpperCase());

    // Active nav highlight from <body data-page>
    const page = document.body.dataset.page;
    if (page) {
      document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('is-active'));
      const link = document.querySelector('.sidebar nav a[data-nav="' + page + '"]');
      if (link) link.classList.add('is-active');
    }

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.addEventListener('click', function () {
      try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        sessionStorage.removeItem(TOKEN_KEY);
        sessionStorage.removeItem(USER_KEY);
      } catch (_) {}
      window.location.replace('/admin/login.html');
    });

    // Language toggle button — the actual click handler is added by
    // i18n.js via [data-i18n-toggle]; we just keep its label in sync with
    // the current language and re-render the user-block strings after a swap.
    const langBtn = document.getElementById('lang-toggle');
    if (langBtn && window.I18N) {
      const updateLabel = function () {
        const isAr = window.I18N.lang === 'ar';
        langBtn.textContent = isAr ? 'EN' : 'AR';
      };
      updateLabel();
      document.addEventListener('i18n:change', function () {
        updateLabel();
        // Re-render the role pill which is derived (uppercased role) and not driven by data-i18n.
        setText('#user-role', (user?.role || 'admin').toUpperCase());
      });
    }
  });

  function setText(sel, value) {
    const el = document.querySelector(sel);
    if (el) el.textContent = value;
  }

  // Helper exposed to sub-pages.
  window.ADMIN_AUTH = {
    token: token,
    user: user,
    role:  (user && user.role) || 'viewer',
    isAdmin: function () { return ['admin','super_admin'].indexOf(this.role) >= 0; },
    fetch: function (url, opts) {
      opts = opts || {};
      opts.headers = Object.assign({ 'Authorization': 'Bearer ' + token }, opts.headers || {});
      return fetch(url, opts).then(r => {
        if (r.status === 401) {
          try {
            localStorage.removeItem(TOKEN_KEY);
            sessionStorage.removeItem(TOKEN_KEY);
          } catch (_) {}
          window.location.replace('/admin/login.html');
          throw new Error('unauthorized');
        }
        if (r.status === 403) {
          // Forced rotation? backend says "Password change required".
          r.clone().json().then(j => {
            if (j && /password change required/i.test(j.detail || '')) {
              window.location.replace('/admin/reset.html?force=1');
            }
          }).catch(()=>{});
        }
        return r;
      });
    },
    /**
     * Minimal modal helper used by every admin page that needs an
     * Add/Edit form. Pass:
     *   title:    "Add vehicle"
     *   fields:   [{name, label, label_ar, type, options?, required?, value?, placeholder?}, ...]
     *   onSubmit: async (values) => fetch(...).then(handle)
     * Returns nothing — handles its own DOM lifecycle.
     */
    openForm: function (opts) {
      const isAr = (document.documentElement.lang || 'ar').slice(0,2) === 'ar';
      const overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:grid;place-items:center;padding:24px;';
      const card = document.createElement('div');
      card.style.cssText = 'background:#fff;border-radius:12px;padding:24px;max-width:560px;width:100%;max-height:90vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,.18);font-family:"Readex Pro",system-ui,sans-serif;';
      overlay.appendChild(card);
      card.innerHTML =
        '<h2 style="margin:0 0 6px;font-size:20px;color:#0E5650;">' + escape(opts.title) + '</h2>' +
        (opts.subtitle ? '<p style="margin:0 0 16px;color:#64748b;font-size:13px;">' + escape(opts.subtitle) + '</p>' : '') +
        '<form id="dts-form"></form>' +
        '<div id="dts-err" style="color:#b91c1c;font-size:13px;margin-top:10px;min-height:18px;"></div>' +
        '<div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end;">' +
        '  <button id="dts-cancel" type="button" style="padding:10px 16px;border:1px solid #cbd5e1;background:#fff;border-radius:8px;cursor:pointer;">' + (isAr ? 'إلغاء' : 'Cancel') + '</button>' +
        '  <button id="dts-save"   type="button" style="padding:10px 16px;border:0;background:#0E5650;color:#fff;border-radius:8px;cursor:pointer;">' + (isAr ? 'حفظ' : 'Save') + '</button>' +
        '</div>';
      const form = card.querySelector('#dts-form');
      opts.fields.forEach(f => {
        const row = document.createElement('div');
        row.style.cssText = 'margin-bottom:12px;';
        const label = isAr ? (f.label_ar || f.label) : f.label;
        row.innerHTML = '<label style="display:block;font-size:13px;color:#475569;margin-bottom:4px;">' + escape(label) + (f.required ? ' *' : '') + '</label>';
        let input;
        if (f.type === 'select') {
          input = document.createElement('select');
          (f.options || []).forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = isAr ? (o.label_ar || o.label) : o.label;
            if (f.value && String(o.value) === String(f.value)) opt.selected = true;
            input.appendChild(opt);
          });
        } else if (f.type === 'textarea') {
          input = document.createElement('textarea');
          input.rows = 4;
          if (f.value != null) input.value = f.value;
        } else {
          input = document.createElement('input');
          input.type = f.type || 'text';
          if (f.value != null) input.value = f.value;
          if (f.placeholder) input.placeholder = f.placeholder;
          if (f.step) input.step = f.step;
          if (f.min != null) input.min = f.min;
          if (f.max != null) input.max = f.max;
        }
        input.name = f.name;
        if (f.required) input.required = true;
        input.style.cssText = 'width:100%;padding:9px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit;background:#fff;';
        row.appendChild(input);
        if (f.hint) {
          const h = document.createElement('div');
          h.style.cssText = 'color:#94a3b8;font-size:12px;margin-top:2px;';
          h.textContent = f.hint;
          row.appendChild(h);
        }
        form.appendChild(row);
      });
      function close() { overlay.remove(); document.removeEventListener('keydown', onKey); }
      function onKey(ev) { if (ev.key === 'Escape') close(); }
      card.querySelector('#dts-cancel').onclick = close;
      card.querySelector('#dts-save').onclick = async function () {
        const err = card.querySelector('#dts-err'); err.textContent = '';
        const values = {};
        let missing = null;
        opts.fields.forEach(f => {
          const el = form.elements[f.name];
          if (!el) return;
          let v = el.value;
          if (f.type === 'number') v = v === '' ? null : Number(v);
          if (f.type === 'checkbox') v = !!el.checked;
          if (f.required && (v === '' || v == null)) missing = f.label;
          values[f.name] = v;
        });
        if (missing) { err.textContent = (isAr ? 'الحقل مطلوب: ' : 'Missing field: ') + missing; return; }
        card.querySelector('#dts-save').disabled = true;
        try {
          const detail = await opts.onSubmit(values);
          if (detail && detail.error) { err.textContent = detail.error; card.querySelector('#dts-save').disabled = false; return; }
          close();
          if (opts.onAfter) opts.onAfter();
        } catch (e) {
          err.textContent = (e && e.message) || (isAr ? 'فشل الحفظ' : 'Save failed');
          card.querySelector('#dts-save').disabled = false;
        }
      };
      document.addEventListener('keydown', onKey);
      document.body.appendChild(overlay);
      function escape(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    },
  };
})();
