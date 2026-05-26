/**
 * Damascus Transit — Shared Error Handler
 * Provides: global error overlay, toast notifications,
 * fetchWithTimeout, showEmptyState, skeleton helpers.
 */
(function (w, d) {
    'use strict';

    // ── Inject shared CSS ────────────────────────────────────────────────
    var style = d.createElement('style');
    style.textContent = [
        /* Toast container */
        '#dt-toasts{position:fixed;top:16px;left:50%;transform:translateX(-50%);',
        'z-index:99999;display:flex;flex-direction:column;gap:8px;',
        'pointer-events:none;width:min(440px,92vw);}',

        /* Toast item */
        '.dt-toast{background:#1c1c1c;color:#f0f0f0;padding:12px 14px;border-radius:8px;',
        'font-family:"IBM Plex Sans Arabic",-apple-system,sans-serif;font-size:14px;',
        'direction:rtl;pointer-events:auto;box-shadow:0 4px 20px rgba(0,0,0,.6);',
        'border-inline-end:4px solid #ef4444;display:flex;align-items:flex-start;',
        'gap:10px;animation:dt-in .2s ease;line-height:1.5;}',
        '.dt-toast.warn{border-inline-end-color:#f59e0b;}',
        '.dt-toast.info{border-inline-end-color:#3b82f6;}',
        '.dt-toast.success{border-inline-end-color:#10b981;}',
        '.dt-toast-icon{flex-shrink:0;font-size:17px;margin-top:1px;}',
        '.dt-toast-body{flex:1;}',
        '.dt-toast-title{font-weight:600;margin-bottom:2px;}',
        '.dt-toast-sub{font-size:12px;color:#999;}',
        '@keyframes dt-in{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}',

        /* Global error overlay */
        '#dt-err-overlay{display:none;position:fixed;inset:0;z-index:999999;',
        'background:#0d0d0d;align-items:center;justify-content:center;',
        'flex-direction:column;padding:24px;text-align:center;',
        'font-family:"IBM Plex Sans Arabic",-apple-system,sans-serif;}',
        '#dt-err-overlay.active{display:flex;}',
        '#dt-err-overlay .err-bus{font-size:60px;margin-bottom:20px;}',
        '#dt-err-overlay .err-ar{font-size:22px;font-weight:700;color:#edebe0;',
        'margin-bottom:6px;direction:rtl;}',
        '#dt-err-overlay .err-en{font-size:14px;color:#777;margin-bottom:28px;}',
        '#dt-err-overlay .err-detail{font-size:12px;color:#444;margin-bottom:24px;',
        'max-width:360px;word-break:break-word;}',
        '#dt-err-overlay button{background:#428177;color:#fff;border:none;',
        'padding:12px 32px;border-radius:8px;font-size:15px;cursor:pointer;',
        'font-family:inherit;transition:background .15s;}',
        '#dt-err-overlay button:hover{background:#54a59a;}',

        /* Skeleton shimmer */
        '.dt-skel{background:linear-gradient(90deg,#2a2a2a 25%,#3a3a3a 50%,#2a2a2a 75%);',
        'background-size:200% 100%;animation:dt-shimmer 1.5s ease infinite;',
        'border-radius:4px;display:inline-block;min-height:1em;}',
        '@keyframes dt-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}',

        /* Empty state */
        '.dt-empty{display:flex;flex-direction:column;align-items:center;',
        'justify-content:center;padding:48px 20px;direction:rtl;}',
        '.dt-empty .e-icon{font-size:50px;margin-bottom:14px;opacity:.65;}',
        '.dt-empty .e-ar{font-size:16px;font-weight:600;color:#bbb;margin-bottom:4px;}',
        '.dt-empty .e-en{font-size:12px;color:#666;}',
        '.dt-empty .e-hint{font-size:13px;color:#888;margin-top:8px;}',
    ].join('');
    if (d.head) {
        d.head.appendChild(style);
    } else {
        d.addEventListener('DOMContentLoaded', function () { d.head.appendChild(style); });
    }

    // ── Toast ────────────────────────────────────────────────────────────
    var _tc = null;
    function _getTC() {
        if (!_tc || !d.body.contains(_tc)) {
            _tc = d.getElementById('dt-toasts');
            if (!_tc) {
                _tc = d.createElement('div');
                _tc.id = 'dt-toasts';
                d.body.appendChild(_tc);
            }
        }
        return _tc;
    }

    var ICONS = { error: '⚠️', warn: '🔶', info: 'ℹ️', success: '✅' };

    /**
     * Show a bilingual toast notification.
     * @param {string} ar  Arabic message (shown as title)
     * @param {string} en  English message (shown as subtitle, optional)
     * @param {string} type  'error'|'warn'|'info'|'success'
     * @param {number} duration  ms before auto-dismiss (default 5000)
     */
    function toast(ar, en, type, duration) {
        type = type || 'error';
        duration = duration || 5000;
        if (!d.body) { setTimeout(function () { toast(ar, en, type, duration); }, 200); return; }
        var tc = _getTC();
        var el = d.createElement('div');
        el.className = 'dt-toast ' + type;
        el.innerHTML = '<span class="dt-toast-icon">' + (ICONS[type] || '⚠️') + '</span>' +
            '<div class="dt-toast-body">' +
            '<div class="dt-toast-title">' + ar + '</div>' +
            (en ? '<div class="dt-toast-sub">' + en + '</div>' : '') +
            '</div>';
        tc.appendChild(el);
        setTimeout(function () {
            el.style.transition = 'opacity .3s ease';
            el.style.opacity = '0';
            setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 320);
        }, duration);
    }

    // ── Global Error Overlay ─────────────────────────────────────────────
    var _overlay = null;
    var _overlayShown = false;

    // Rate-limit: track timestamps of errors that reached the handler.
    // Second and subsequent errors within 30 s are downgraded to toast.
    var _recentErrors = [];
    var _RATE_WINDOW_MS = 30000;

    function _isRateLimited() {
        var now = Date.now();
        _recentErrors = _recentErrors.filter(function (t) { return now - t < _RATE_WINDOW_MS; });
        return _recentErrors.length > 0;
    }

    function _recordErrorTime() {
        _recentErrors.push(Date.now());
    }

    /** Return true for errors that indicate the page is genuinely broken. */
    function _isFatalError(err) {
        if (!err) return false;
        if (err instanceof ReferenceError) return true;
        if (err instanceof SyntaxError) return true;
        if (err instanceof TypeError && /is not a function/i.test(err.message || '')) return true;
        return false;
    }

    /** Best-effort POST to the backend error log. Never throws. */
    function _logErrorToBackend(message, filename, lineno, colno, errType) {
        try {
            fetch('/api/log-client-error', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    source: filename || '',
                    lineno: lineno || 0,
                    colno: colno || 0,
                    type: errType || 'Error',
                    url: w.location.href,
                    userAgent: w.navigator.userAgent,
                    timestamp: new Date().toISOString()
                })
            }).catch(function () {});
        } catch (e) { /* never let logging crash the page */ }
    }

    function _ensureOverlay() {
        if (_overlay && d.body.contains(_overlay)) return _overlay;
        _overlay = d.createElement('div');
        _overlay.id = 'dt-err-overlay';
        _overlay.innerHTML =
            '<div class="err-bus">🚌</div>' +
            '<div class="err-ar">حدث خطأ غير متوقع في التطبيق</div>' +
            '<div class="err-en">An unexpected error occurred. Please reload the page.</div>' +
            '<div class="err-detail" id="dt-err-detail"></div>' +
            '<button onclick="location.reload()">إعادة التحميل &nbsp;|&nbsp; Reload</button>';
        d.body.appendChild(_overlay);
        return _overlay;
    }

    /**
     * Show a full-page fatal error overlay.
     * @param {string} [detail]  Optional technical detail (shown small)
     */
    function showErrorPage(detail) {
        if (!d.body) { setTimeout(function () { showErrorPage(detail); }, 200); return; }
        var ov = _ensureOverlay();
        if (detail) {
            var det = d.getElementById('dt-err-detail');
            if (det) det.textContent = detail;
        }
        ov.classList.add('active');
        _overlayShown = true;
    }

    // Catch uncaught global JS errors
    w.addEventListener('error', function (ev) {
        if (!ev) return;
        var err = ev.error;
        var msg = ev.message || (err ? String(err) : 'Unknown error');
        var errType = (err && err.constructor && err.constructor.name) || 'Error';

        console.error('[DT] Uncaught error:', err || msg);

        // Log every error to the backend regardless of severity.
        _logErrorToBackend(msg, ev.filename, ev.lineno, ev.colno, errType);

        var rateLimited = _isRateLimited();
        _recordErrorTime();

        // Show full-page overlay only for genuinely fatal errors and only once
        // per 30-second window. Everything else becomes a discreet toast.
        if (!rateLimited && _isFatalError(err) && !_overlayShown) {
            showErrorPage(msg);
        } else {
            var shortMsg = msg.length > 80 ? msg.slice(0, 77) + '\u2026' : msg;
            toast('\u062d\u062f\u062b \u062e\u0637\u0623 \u0641\u064a \u0627\u0644\u062a\u0637\u0628\u064a\u0642', shortMsg, 'error', 7000);
        }
    });

    // Catch unhandled promise rejections (log only — API rejections handled per-call)
    w.addEventListener('unhandledrejection', function (ev) {
        if (ev && ev.reason) {
            console.error('[DT] Unhandled rejection:', ev.reason);
        }
    });

    // ── fetchWithTimeout ─────────────────────────────────────────────────
    /**
     * Fetch with an automatic timeout using AbortController.
     * @param {string} url
     * @param {object} [options]  standard fetch options
     * @param {number} [timeout]  ms before abort (default 5000)
     * @returns {Promise<Response>}
     */
    function fetchWithTimeout(url, options, timeout) {
        timeout = timeout === undefined ? 5000 : timeout;
        var ctrl = new AbortController();
        var timer = setTimeout(function () { ctrl.abort(); }, timeout);
        var merged = Object.assign({}, options || {}, { signal: ctrl.signal });
        return fetch(url, merged)
            .then(function (res) { clearTimeout(timer); return res; })
            .catch(function (err) {
                clearTimeout(timer);
                if (err.name === 'AbortError') {
                    var te = new Error('Request timed out after ' + timeout + 'ms');
                    te.isTimeout = true;
                    throw te;
                }
                throw err;
            });
    }

    // ── showEmptyState ────────────────────────────────────────────────────
    /**
     * Replace a container's content with a styled empty state.
     * @param {string|HTMLElement} container  Element id or element
     * @param {object} opts  { icon, ar, en, hint }
     */
    function showEmptyState(container, opts) {
        var el = typeof container === 'string' ? d.getElementById(container) : container;
        if (!el) return;
        var o = opts || {};
        var icon  = o.icon  || '🚌';
        var ar    = o.ar    || 'لا توجد بيانات';
        var en    = o.en    || 'No data available';
        var hint  = o.hint  || '';
        el.innerHTML =
            '<div class="dt-empty">' +
            '<div class="e-icon">' + icon + '</div>' +
            '<div class="e-ar">' + ar + '</div>' +
            '<div class="e-en">' + en + '</div>' +
            (hint ? '<div class="e-hint">' + hint + '</div>' : '') +
            '</div>';
    }

    // ── skeleton helpers ──────────────────────────────────────────────────
    /**
     * Return an inline skeleton shimmer span.
     * @param {string} [w]  CSS width (default '80px')
     * @param {string} [h]  CSS height (default '1em')
     */
    function skeleton(w, h) {
        return '<span class="dt-skel" style="width:' + (w || '80px') +
               ';height:' + (h || '1em') + ';"></span>';
    }

    // ── Expose ────────────────────────────────────────────────────────────
    w.DT = {
        toast:            toast,
        showErrorPage:    showErrorPage,
        fetchWithTimeout: fetchWithTimeout,
        showEmptyState:   showEmptyState,
        skeleton:         skeleton
    };

}(window, document));
