/* ────────────────────────────────────────────────────────────────────────────
 *  _shell.js — wires up the admin chrome that's identical on every page:
 *    • Auth gate (redirect to /admin/login.html if no token)
 *    • Render the SHARED SIDEBAR NAV (single source of truth: ADMIN_NAV below)
 *      with role gating — operators (dispatchers) never see admin-only pages
 *    • Live "pending approvals" badge on the Approvals link (admins)
 *    • Render the logged-in user's name/role/initial; wire logout
 *    • Bilingual AR/EN toggle via /lib/i18n.js
 *
 *  Usage in each sub-page HTML:
 *    <body data-page="vehicles">  (overview|approvals|vehicles|users|routes|
 *                                  alerts|payments|audit)
 *    <nav data-shell-nav></nav>   inside <aside class="sidebar">
 *    <script src="/lib/i18n.js"></script>
 *    <script src="/admin/_shell.js" defer></script>
 *
 *  Restructure 2026-06-11: nav was previously copy-pasted per page and four
 *  of its links pointed at pages that did not exist. It is now generated
 *  here so every page always links only to real pages.
 * ──────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  const TOKEN_KEY = 'dt_token';
  const USER_KEY  = 'dt_user';

  // Single source of truth for the admin navigation.
  // roles: which roles see the link. (super_admin sees everything admin does.)
  const ADMIN_NAV = [
    { nav: 'overview',  href: '/admin/',                 i18n: 'admin.nav.overview',  ar: 'النظرة العامة',  en: 'Overview',
      icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>' },
    { nav: 'approvals', href: '/admin/approvals.html',   i18n: 'admin.nav.approvals', ar: 'الموافقات',      en: 'Approvals', roles: ['admin', 'super_admin'], badge: true,
      icon: '<path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>' },
    { nav: 'vehicles',  href: '/admin/vehicles.html',    i18n: 'admin.nav.vehicles',  ar: 'المركبات',       en: 'Vehicles',
      icon: '<path d="M3 13l1.5-7h15L21 13M4 13v6h2v-2h12v2h2v-6"/><circle cx="7" cy="16" r="1"/><circle cx="17" cy="16" r="1"/>' },
    { nav: 'users',     href: '/admin/users.html',       i18n: 'admin.nav.users',     ar: 'المستخدمون',     en: 'Users', roles: ['admin', 'super_admin'],
      icon: '<circle cx="9" cy="8" r="4"/><path d="M2 22v-1a7 7 0 0 1 14 0v1"/><circle cx="17" cy="6" r="3"/><path d="M22 22v-1a5 5 0 0 0-5-5"/>' },
    { nav: 'routes',    href: '/admin/routes.html',      i18n: 'admin.nav.routes',    ar: 'الخطوط',         en: 'Routes',
      icon: '<path d="M6 3v18M18 3v18M6 7h12M6 12h12M6 17h12"/>' },
    { nav: 'dispatch',  href: '/admin/dispatch.html',    i18n: 'admin.nav.dispatch',  ar: 'توزيع الرحلات',  en: 'Dispatch', roles: ['dispatcher', 'admin', 'super_admin'],
      icon: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>' },
    { nav: 'alerts',    href: '/admin/alerts.html',      i18n: 'admin.nav.alerts',    ar: 'التنبيهات',      en: 'Alerts',
      icon: '<path d="M12 2 2 22h20L12 2Z"/><path d="M12 9v5"/><circle cx="12" cy="18" r=".5" fill="currentColor"/>' },
    { nav: 'payments',  href: '/admin/payments.html',    i18n: 'admin.nav.payments',  ar: 'المدفوعات',      en: 'Payments',
      icon: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>' },
    { nav: 'audit',     href: '/admin/audit.html',       i18n: 'admin.nav.audit',     ar: 'سجل التدقيق',    en: 'Audit log', roles: ['admin', 'super_admin'],
      icon: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h6"/>' },
    { nav: 'analytics', href: '/dashboard/analytics.html', i18n: 'admin.nav.analytics', ar: 'التحليلات',    en: 'Analytics',
      icon: '<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 5-7"/>' },
    { nav: 'help',      href: '/help/',                  i18n: 'admin.nav.help',      ar: 'كيفية الاستخدام', en: 'Help',
      icon: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>' },
  ];

  // ── Auth gate ───────────────────────────────────────────────────────────────
  let token = null, user = null;
  try {
    // `token` is usually absent now (web auth is the httpOnly cookie); it's only
    // present for the native driver path or local dev. `dt_user` is the gate.
    token = localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY);
    user  = rawUser ? JSON.parse(rawUser) : null;
  } catch (_) {}
  if (!user) {
    window.location.replace('/admin/login.html');
    return;
  }

  // Lift the head-injected visibility cloak (added by _gate.js)
  document.documentElement.dataset.auth = 'ok';

  const role = ((user && user.role) || 'viewer').toLowerCase();
  const isAdmin = role === 'admin' || role === 'super_admin';

  function navVisible(item) {
    if (!item.roles) return true;
    return item.roles.indexOf(role) >= 0;
  }

  function isArabic() {
    return (document.documentElement.lang || 'ar').slice(0, 2) === 'ar';
  }

  function renderNav() {
    const host = document.querySelector('[data-shell-nav]');
    if (!host) return;
    const ar = isArabic();
    host.setAttribute('aria-label', ar ? 'إدارة' : 'Administration');
    host.textContent = '';
    ADMIN_NAV.filter(navVisible).forEach(function (item) {
      const a = document.createElement('a');
      a.href = item.href;
      a.dataset.nav = item.nav;
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '2');
      svg.innerHTML = item.icon; // static trusted markup from this file only
      const span = document.createElement('span');
      span.textContent = ar ? item.ar : item.en;
      if (item.i18n) span.dataset.i18n = item.i18n;
      a.appendChild(svg);
      a.appendChild(span);
      if (item.badge) {
        const b = document.createElement('span');
        b.id = 'nav-badge-' + item.nav;
        b.style.cssText = 'display:none;margin-inline-start:auto;background:var(--national-gold,#C9A95B);color:#0B0B0B;font-size:11px;font-weight:700;border-radius:999px;padding:1px 7px;';
        a.appendChild(b);
      }
      host.appendChild(a);
    });
    const page = document.body.dataset.page;
    if (page) {
      const link = host.querySelector('a[data-nav="' + page + '"]');
      if (link) link.classList.add('is-active');
    }
  }

  // Live pending-approvals badge (admins only; silent failure)
  function refreshBadge() {
    if (!isAdmin) return;
    ADMIN_AUTH.fetch('/api/admin/vehicles/pending-count')
      .then(r => (r.ok ? r.json() : null))
      .then(j => {
        const b = document.getElementById('nav-badge-approvals');
        if (!b || !j) return;
        const n = j.pending || 0;
        b.style.display = n > 0 ? 'inline-block' : 'none';
        b.textContent = String(n);
      })
      .catch(() => {});
  }

  // Build the profile dropdown in the pinned sidebar footer: hovering (or
  // tapping) the user row reveals Settings (admins) + Sign out.
  function buildProfileMenu(onLogout) {
    const footer = document.querySelector('.sidebar__footer');
    const userRow = footer && footer.querySelector('.sidebar__user');
    if (!footer || !userRow || footer.querySelector('.sidebar__menu')) return;
    const ar = isArabic();
    const gear = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
    const exit = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></svg>';
    const menu = document.createElement('div');
    menu.className = 'sidebar__menu';
    let html = '';
    if (isAdmin) html += '<a href="/admin/settings.html">' + gear + '<span data-i18n="admin.nav.settings">' + (ar ? 'الإعدادات' : 'Settings') + '</span></a>';
    html += '<button type="button" id="profile-signout">' + exit + '<span data-i18n="admin.signOut">' + (ar ? 'تسجيل الخروج' : 'Sign out') + '</span></button>';
    menu.innerHTML = html; // static, trusted markup
    footer.appendChild(menu);
    const so = menu.querySelector('#profile-signout');
    if (so) so.addEventListener('click', onLogout);
    userRow.style.userSelect = 'none';
    userRow.addEventListener('click', function (e) { e.stopPropagation(); footer.classList.toggle('is-open'); });
    menu.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () { footer.classList.remove('is-open'); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const initial = ((user && (user.name || user.email)) || '?').trim().charAt(0).toUpperCase();
    setText('#user-initial', initial);
    setText('#user-name', (user && (user.name || user.email)) || '—');
    setText('#user-role', ((user && user.role) || 'admin').toUpperCase());

    renderNav();
    refreshBadge();
    setInterval(refreshBadge, 60000);

    // Direct-URL guard for role-gated pages (the API 403s anyway; this is UX)
    const page = document.body.dataset.page;
    const gated = ADMIN_NAV.find(i => i.nav === page && i.roles);
    if (gated && !navVisible(gated)) {
      window.location.replace('/admin/?denied=' + encodeURIComponent(page));
      return;
    }

    function doLogout() {
      const done = function () {
        try {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          sessionStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(USER_KEY);
        } catch (_) {}
        window.location.replace('/admin/login.html');
      };
      // Revoke the httpOnly cookie server-side first (JS can't clear it), then
      // wipe the local hints regardless of the request outcome.
      fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }).then(done, done);
    }
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.addEventListener('click', doLogout);
    buildProfileMenu(doLogout);

    const langBtn = document.getElementById('lang-toggle');
    if (langBtn && window.I18N) {
      const updateLabel = function () {
        langBtn.textContent = window.I18N.lang === 'ar' ? 'English' : 'العربية';
      };
      updateLabel();
      document.addEventListener('i18n:change', function () {
        updateLabel();
        renderNav();
        refreshBadge();
        setText('#user-role', ((user && user.role) || 'admin').toUpperCase());
      });
    }
  });

  function setText(sel, value) {
    const el = document.querySelector(sel);
    if (el) el.textContent = value;
  }

  // ── Helper API exposed to sub-pages ────────────────────────────────────────
  const ADMIN_AUTH = {
    token: token,
    user: user,
    role: role,
    isAdmin: function () { return isAdmin; },
    isOperator: function () { return role === 'dispatcher'; },
    esc: function (s) {
      return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[c]));
    },
    // Normalise a FastAPI error `detail` into a readable string. FastAPI
    // returns 422 validation errors as an ARRAY of {msg, loc, ...}; rendering
    // that array directly used to show "[object Object]". Handles string,
    // array, and object shapes.
    errText: function (detail, fallback) {
      fallback = fallback || (isArabic() ? 'فشل الحفظ' : 'Save failed');
      if (detail == null) return fallback;
      if (typeof detail === 'string') return detail || fallback;
      if (Array.isArray(detail)) {
        const parts = detail.map(function (d) {
          if (typeof d === 'string') return d;
          if (d && d.msg) {
            const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : null;
            return field ? field + ': ' + d.msg : d.msg;
          }
          return '';
        }).filter(Boolean);
        return parts.length ? parts.join('؛ ') : fallback;
      }
      if (typeof detail === 'object') return detail.msg || detail.detail || fallback;
      return String(detail) || fallback;
    },
    fetch: function (url, opts) {
      opts = opts || {};
      // Auth travels in the httpOnly cookie (same-origin → sent automatically).
      // A Bearer header is only attached when a token is present (native/dev).
      opts.headers = Object.assign({}, opts.headers || {});
      if (token) opts.headers['Authorization'] = 'Bearer ' + token;
      if (!opts.credentials) opts.credentials = 'same-origin';
      return fetch(url, opts).then(r => {
        if (r.status === 401) {
          try {
            localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY);
            sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY);
          } catch (_) {}
          window.location.replace('/admin/login.html');
          throw new Error('unauthorized');
        }
        return r;
      });
    },
    toast: function (msgAr, msgEn, type) {
      if (window.DT && window.DT.toast) { window.DT.toast(msgAr, msgEn, type || 'info'); return; }
      const el = document.createElement('div');
      el.textContent = isArabic() ? msgAr : (msgEn || msgAr);
      el.style.cssText = 'position:fixed;bottom:24px;inset-inline-start:24px;z-index:9999;background:#0E5650;color:#fff;padding:12px 18px;border-radius:10px;font-family:inherit;box-shadow:0 6px 24px rgba(0,0,0,.25);' + (type === 'error' ? 'background:#9b121e;' : '');
      document.body.appendChild(el);
      setTimeout(() => el.remove(), 4000);
    },
    /**
     * Client-side paginator shared by every list page.
     *   const PAGER = ADMIN_AUTH.pager({ render, pageSize: 15, mountAfter: '.data-table-card' });
     *   PAGER.set(rows);   // call instead of render(rows) after a fetch
     *   PAGER.redraw();    // call on i18n:change to relabel + keep the page
     * `render(slice)` receives only the current page's rows.
     */
    pager: function (opts) {
      var pageSize = opts.pageSize || 15;
      var rows = [], page = 1;
      var bar = document.createElement('div');
      bar.className = 'dt-pager';
      bar.style.cssText = 'display:none;gap:10px;align-items:center;justify-content:center;padding:14px 0;flex-wrap:wrap;';
      var mount = typeof opts.mountAfter === 'string' ? document.querySelector(opts.mountAfter) : opts.mountAfter;
      if (mount && mount.parentNode) mount.parentNode.insertBefore(bar, mount.nextSibling);

      function t(k, fb) { return (window.I18N && window.I18N.t && window.I18N.t(k)) || fb; }
      function totalPages() { return Math.max(1, Math.ceil(rows.length / pageSize)); }
      function draw() {
        var tp = totalPages();
        if (page > tp) page = tp;
        if (page < 1) page = 1;
        var start = (page - 1) * pageSize;
        opts.render(rows.slice(start, start + pageSize));
        if (rows.length <= pageSize) { bar.style.display = 'none'; return; }
        bar.style.display = 'flex';
        bar.textContent = '';
        var prev = document.createElement('button');
        prev.className = 'btn btn--sm btn--outline';
        prev.textContent = '‹ ' + t('admin.pager.prev', 'Previous');
        prev.disabled = page <= 1;
        prev.onclick = function () { page = Math.max(1, page - 1); draw(); };
        var lbl = document.createElement('span');
        lbl.className = 'cell-muted';
        lbl.style.cssText = 'font-size:13px;min-width:120px;text-align:center;';
        lbl.textContent = t('admin.pager.page', 'Page') + ' ' + page + ' ' + t('admin.pager.of', 'of') + ' ' + tp;
        var next = document.createElement('button');
        next.className = 'btn btn--sm btn--outline';
        next.textContent = t('admin.pager.next', 'Next') + ' ›';
        next.disabled = page >= tp;
        next.onclick = function () { page = Math.min(tp, page + 1); draw(); };
        bar.appendChild(prev); bar.appendChild(lbl); bar.appendChild(next);
      }
      return {
        set: function (newRows) { rows = Array.isArray(newRows) ? newRows : []; page = 1; draw(); },
        redraw: draw,
      };
    },

    /**
     * Server-side paginator — the API returns ONE page at a time, so the table
     * never pulls the whole dataset. `fetchPage(page)` must resolve to
     * `{ items, has_more }`; `render(items)` draws the current page.
     */
    serverPager: function (opts) {
      var page = 1, hasMore = false, busy = false, lastItems = [];
      var bar = document.createElement('div');
      bar.className = 'dt-pager';
      bar.style.cssText = 'display:none;gap:10px;align-items:center;justify-content:center;padding:14px 0;flex-wrap:wrap;';
      var mount = typeof opts.mountAfter === 'string' ? document.querySelector(opts.mountAfter) : opts.mountAfter;
      if (mount && mount.parentNode) mount.parentNode.insertBefore(bar, mount.nextSibling);

      function t(k, fb) { return (window.I18N && window.I18N.t && window.I18N.t(k)) || fb; }
      function draw() {
        if (page <= 1 && !hasMore) { bar.style.display = 'none'; return; }
        bar.style.display = 'flex';
        bar.textContent = '';
        var prev = document.createElement('button');
        prev.className = 'btn btn--sm btn--outline';
        prev.textContent = '‹ ' + t('admin.pager.prev', 'Previous');
        prev.disabled = page <= 1 || busy;
        prev.onclick = function () { go(page - 1); };
        var lbl = document.createElement('span');
        lbl.className = 'cell-muted';
        lbl.style.cssText = 'font-size:13px;min-width:90px;text-align:center;';
        lbl.textContent = t('admin.pager.page', 'Page') + ' ' + page;
        var next = document.createElement('button');
        next.className = 'btn btn--sm btn--outline';
        next.textContent = t('admin.pager.next', 'Next') + ' ›';
        next.disabled = !hasMore || busy;
        next.onclick = function () { go(page + 1); };
        bar.appendChild(prev); bar.appendChild(lbl); bar.appendChild(next);
      }
      function go(p) {
        if (busy || p < 1) return Promise.resolve();
        busy = true;
        return Promise.resolve(opts.fetchPage(p)).then(function (res) {
          res = res || {};
          page = p;
          hasMore = !!res.has_more;
          lastItems = res.items || [];
          opts.render(lastItems);
          busy = false;
          draw();
        }, function (e) {
          busy = false;
          if (opts.onError) opts.onError(e);
        });
      }
      return {
        first: function () { return go(1); },
        reload: function () { return go(page); },
        rerender: function () { opts.render(lastItems); },
      };
    },

    /** Minimal modal form helper — see source page usage. */
    openForm: function (opts) {
      const isAr = isArabic();
      const esc = ADMIN_AUTH.esc;
      const overlay = document.createElement('div');
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:grid;place-items:center;padding:24px;';
      const card = document.createElement('div');
      card.style.cssText = 'background:var(--color-surface,#fff);color:var(--color-text,#0B0B0B);border-radius:12px;padding:24px;max-width:560px;width:100%;max-height:90vh;overflow:auto;box-shadow:0 8px 32px rgba(0,0,0,.18);font-family:"Readex Pro",system-ui,sans-serif;';
      overlay.appendChild(card);
      card.innerHTML =
        '<h2 style="margin:0 0 6px;font-size:20px;color:var(--national-green,#0E5650);">' + esc(opts.title) + '</h2>' +
        (opts.subtitle ? '<p style="margin:0 0 16px;color:var(--color-text-mute,#64748b);font-size:13px;">' + esc(opts.subtitle) + '</p>' : '') +
        '<form id="dts-form"></form>' +
        '<div id="dts-err" style="color:#b91c1c;font-size:13px;margin-top:10px;min-height:18px;"></div>' +
        '<div style="display:flex;gap:8px;margin-top:14px;justify-content:flex-end;">' +
        '  <button id="dts-cancel" type="button" style="padding:10px 16px;border:1px solid #cbd5e1;background:transparent;color:inherit;border-radius:8px;cursor:pointer;">' + (isAr ? 'إلغاء' : 'Cancel') + '</button>' +
        '  <button id="dts-save"   type="button" style="padding:10px 16px;border:0;background:var(--national-green,#0E5650);color:#fff;border-radius:8px;cursor:pointer;">' + (isAr ? 'حفظ' : 'Save') + '</button>' +
        '</div>';
      const form = card.querySelector('#dts-form');
      opts.fields.forEach(f => {
        const row = document.createElement('div');
        row.style.cssText = 'margin-bottom:12px;';
        const label = isAr ? (f.label_ar || f.label) : f.label;
        const lab = document.createElement('label');
        lab.style.cssText = 'display:block;font-size:13px;color:var(--color-text-soft,#475569);margin-bottom:4px;';
        lab.textContent = label + (f.required ? ' *' : '');
        row.appendChild(lab);
        let input;
        if (f.type === 'select') {
          input = document.createElement('select');
          (f.options || []).forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = isAr ? (o.label_ar || o.label) : o.label;
            if (f.value != null && String(o.value) === String(f.value)) opt.selected = true;
            input.appendChild(opt);
          });
        } else if (f.type === 'textarea') {
          input = document.createElement('textarea');
          input.rows = 3;
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
        input.style.cssText = 'width:100%;padding:9px 11px;border:1px solid #cbd5e1;border-radius:8px;font:inherit;background:var(--color-surface,#fff);color:inherit;';
        row.appendChild(input);
        if (f.hint) {
          const h = document.createElement('div');
          h.style.cssText = 'color:var(--color-text-mute,#94a3b8);font-size:12px;margin-top:2px;';
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
          if (f.required && (v === '' || v == null)) missing = (isAr ? (f.label_ar || f.label) : f.label);
          values[f.name] = v;
        });
        if (missing) { err.textContent = (isAr ? 'الحقل مطلوب: ' : 'Missing field: ') + missing; return; }
        card.querySelector('#dts-save').disabled = true;
        try {
          const detail = await opts.onSubmit(values);
          if (detail && detail.error) { err.textContent = ADMIN_AUTH.errText(detail.error); card.querySelector('#dts-save').disabled = false; return; }
          close();
          if (opts.onAfter) opts.onAfter();
        } catch (e) {
          err.textContent = (e && e.message) || (isAr ? 'فشل الحفظ' : 'Save failed');
          card.querySelector('#dts-save').disabled = false;
        }
      };
      document.addEventListener('keydown', onKey);
      document.body.appendChild(overlay);
    },
  };

  window.ADMIN_AUTH = ADMIN_AUTH;
})();
