/* _gate.js — synchronous auth gate loaded in <head>.
 *
 * Loaded with no `defer`/`async` so it executes BEFORE the body is parsed.
 * If the user has no token we redirect to /admin/login.html immediately,
 * preventing the flash-of-empty-admin-chrome bug where anonymous visitors
 * saw the admin shell with "—" placeholders for a few hundred ms before
 * the deferred _shell.js could redirect.
 *
 * Also hides <body> via a CSS rule until the rest of the shell finishes
 * boot — _shell.js calls document.documentElement.dataset.auth = 'ok'
 * after auth completes which lifts the cloak.
 */
(function () {
  'use strict';
  try {
    var token = localStorage.getItem('dt_token') || sessionStorage.getItem('dt_token');
    if (!token) {
      // Replace so the back button doesn't bring the user back to the
      // empty admin chrome.
      location.replace('/admin/login.html');
      return;
    }
  } catch (_) {
    location.replace('/admin/login.html');
    return;
  }
  // Inject the cloak as a <style> in <head> while it still exists.
  var s = document.createElement('style');
  s.id = 'dts-auth-cloak';
  s.textContent = 'html:not([data-auth="ok"]) body{visibility:hidden}';
  (document.head || document.documentElement).appendChild(s);
})();
