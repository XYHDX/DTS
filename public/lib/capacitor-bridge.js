/**
 * capacitor-bridge.js
 * Damascus Transit System — Native Capacitor integration layer
 *
 * Detects whether the app is running inside a Capacitor native shell and
 * upgrades browser APIs with native plugin equivalents. Falls back to
 * standard browser APIs transparently so the PWA continues to work in a
 * regular browser without any changes.
 *
 * Load this script BEFORE the app code that uses geolocation, camera, auth.
 * Include it in both driver/ and passenger/ index.html files.
 *
 * Plugins used:
 *   @capacitor/core              — base runtime
 *   @capacitor/geolocation       — foreground GPS
 *   @capawesome-team/capacitor-background-geolocation — background GPS
 *   @capacitor/push-notifications — FCM (Android) + APNs (iOS)
 *   @capacitor/camera            — photo capture
 *   capacitor-biometric-auth     — fingerprint / Face ID
 *   @capacitor/splash-screen     — hide splash after boot
 *   @capacitor/status-bar        — status bar style
 */

(function (window) {
  'use strict';

  // ─── Capacitor Detection ──────────────────────────────────────────────────

  /**
   * True when running inside the Capacitor native runtime.
   * window.Capacitor is injected by the Capacitor bridge before the page loads.
   */
  const IS_NATIVE = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  const PLATFORM  = IS_NATIVE ? (window.Capacitor.getPlatform ? window.Capacitor.getPlatform() : 'web') : 'web';

  console.log(`[CapacitorBridge] platform=${PLATFORM} native=${IS_NATIVE}`);

  // ─── Plugin Loader ───────────────────────────────────────────────────────

  /**
   * Lazy-loads a Capacitor plugin by namespace key.
   * Returns null if not available (web environment or plugin not installed).
   */
  function getPlugin(namespace) {
    try {
      if (!IS_NATIVE) return null;
      const p = window.Capacitor.Plugins[namespace];
      return p || null;
    } catch (_) {
      return null;
    }
  }

  // ─── Splash Screen ───────────────────────────────────────────────────────

  /**
   * Call once the app is ready to hide the native splash screen.
   */
  function hideSplash() {
    const splash = getPlugin('SplashScreen');
    if (splash && splash.hide) {
      splash.hide().catch(() => {});
    }
  }

  // ─── Status Bar ──────────────────────────────────────────────────────────

  function setupStatusBar() {
    const sb = getPlugin('StatusBar');
    if (!sb) return;
    // Dark text/icons for our dark background
    sb.setStyle && sb.setStyle({ style: 'DARK' }).catch(() => {});
    sb.setBackgroundColor && sb.setBackgroundColor({ color: '#002623' }).catch(() => {});
  }

  // ─── Geolocation ─────────────────────────────────────────────────────────

  /**
   * Requests geolocation permission from the native layer.
   * Returns 'granted' | 'denied' | 'prompt'.
   */
  async function requestLocationPermission() {
    const geo = getPlugin('Geolocation');
    if (!geo) return 'granted'; // browser will ask natively
    try {
      const result = await geo.requestPermissions({ permissions: ['location'] });
      return result.location;
    } catch (_) {
      return 'denied';
    }
  }

  /**
   * Native watchPosition equivalent.
   * Returns a cleanup function (call to stop watching).
   *
   * @param {function} successCb  — called with { coords: { latitude, longitude, speed, heading } }
   * @param {function} errorCb    — called on error
   */
  function watchPosition(successCb, errorCb) {
    const geo = getPlugin('Geolocation');
    if (!geo || !geo.watchPosition) {
      // Fall back to browser geolocation
      const id = navigator.geolocation.watchPosition(successCb, errorCb, {
        enableHighAccuracy: true,
        maximumAge: 3000,
        timeout: 10000,
      });
      return () => navigator.geolocation.clearWatch(id);
    }

    let watchId = null;
    geo.watchPosition(
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 },
      (pos, err) => {
        if (err) { errorCb && errorCb(err); return; }
        successCb(pos);
      }
    ).then(id => { watchId = id; }).catch(errorCb);

    return () => {
      if (watchId !== null && geo.clearWatch) {
        geo.clearWatch({ id: watchId }).catch(() => {});
      }
    };
  }

  // ─── Background Geolocation (Driver only) ────────────────────────────────

  /**
   * Starts background GPS tracking (driver app only).
   * Calls `onLocation(pos)` each time a position arrives.
   *
   * The @capawesome-team/capacitor-background-geolocation plugin keeps the
   * device reporting position even when the app is backgrounded or the screen
   * is off — critical for driver duty tracking.
   *
   * @param {function} onLocation  — callback with { latitude, longitude, speed, heading }
   */
  async function startBackgroundGeolocation(onLocation) {
    const bgGeo = getPlugin('BackgroundGeolocation');
    if (!bgGeo) {
      // On web / iOS simulator without the plugin, use foreground watch as fallback
      console.warn('[CapacitorBridge] BackgroundGeolocation plugin not available, using foreground watch');
      return watchPosition(onLocation, console.warn);
    }

    try {
      await bgGeo.requestPermissions();
      await bgGeo.addListener('location', (location) => {
        onLocation({
          coords: {
            latitude:  location.latitude,
            longitude: location.longitude,
            speed:     location.speed || 0,
            heading:   location.bearing || 0,
            accuracy:  location.accuracy,
          },
        });
      });
      await bgGeo.start();
      console.log('[CapacitorBridge] Background geolocation started');
      return () => bgGeo.stop().catch(() => {});
    } catch (e) {
      console.error('[CapacitorBridge] Background geolocation error:', e);
      return watchPosition(onLocation, console.warn);
    }
  }

  // ─── Push Notifications ──────────────────────────────────────────────────

  /**
   * Registers the device for push notifications.
   * On Android uses FCM; on iOS uses APNs.
   *
   * Returns the device token string, or null on failure.
   *
   * @param {function} onNotification — called when a notification is received in foreground
   */
  async function registerPushNotifications(onNotification) {
    const push = getPlugin('PushNotifications');
    if (!push) return null;

    try {
      const permResult = await push.requestPermissions();
      if (permResult.receive !== 'granted') {
        console.warn('[CapacitorBridge] Push permission denied');
        return null;
      }

      await push.register();

      push.addListener('registration', (token) => {
        console.log('[CapacitorBridge] Push token:', token.value);
        // Send token to backend
        _sendPushTokenToServer(token.value);
      });

      push.addListener('registrationError', (err) => {
        console.error('[CapacitorBridge] Push registration error:', err);
      });

      push.addListener('pushNotificationReceived', (notification) => {
        console.log('[CapacitorBridge] Push received (foreground):', notification);
        onNotification && onNotification(notification);
      });

      push.addListener('pushNotificationActionPerformed', (action) => {
        console.log('[CapacitorBridge] Push action:', action);
        onNotification && onNotification(action.notification);
      });

      return true;
    } catch (e) {
      console.error('[CapacitorBridge] Push setup error:', e);
      return null;
    }
  }

  async function _sendPushTokenToServer(token) {
    try {
      const authToken = sessionStorage.getItem('authToken');
      if (!authToken) return;
      const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? `http://${window.location.hostname}:8080`
        : window.location.origin;
      await fetch(`${API_BASE}/api/devices/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          token,
          platform: PLATFORM,
          app: window.TRANSIT_APP_TYPE || 'unknown',
        }),
      });
    } catch (_) {}
  }

  // ─── Camera ──────────────────────────────────────────────────────────────

  /**
   * Opens the native camera to capture an incident photo.
   * Returns a base64 JPEG string, or null on cancellation.
   *
   * @param {object} opts — optional overrides (quality, allowEditing, etc.)
   */
  async function captureIncidentPhoto(opts = {}) {
    const camera = getPlugin('Camera');
    if (!camera || !camera.getPhoto) {
      // Fall back to <input type="file" capture="environment">
      return _webCameraFallback(opts);
    }

    try {
      const photo = await camera.getPhoto({
        quality: opts.quality || 80,
        allowEditing: opts.allowEditing || false,
        resultType: 'base64',           // 'uri' | 'base64' | 'dataUrl'
        source: 'CAMERA',               // 'CAMERA' | 'PHOTOS' | 'PROMPT'
        saveToGallery: opts.saveToGallery || false,
        width: opts.width || 1280,
        height: opts.height || 960,
        correctOrientation: true,
      });
      return photo.base64String || null;
    } catch (e) {
      if (e && e.message === 'User cancelled photos app') return null;
      console.error('[CapacitorBridge] Camera error:', e);
      return null;
    }
  }

  /**
   * Web / PWA fallback: triggers a file-input camera capture.
   * Returns a base64 JPEG string via a hidden <input type="file">.
   */
  function _webCameraFallback() {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.capture = 'environment';
      input.style.display = 'none';
      document.body.appendChild(input);

      input.addEventListener('change', () => {
        const file = input.files && input.files[0];
        if (!file) { resolve(null); return; }
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result;
          // Strip the data: prefix to match native base64 output
          const base64 = dataUrl ? dataUrl.split(',')[1] : null;
          resolve(base64);
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(file);
        document.body.removeChild(input);
      });

      input.click();
    });
  }

  // ─── Biometric Authentication ─────────────────────────────────────────────

  /**
   * Attempts biometric authentication (fingerprint or Face ID).
   * Falls back gracefully: returns false rather than throwing.
   *
   * @param {string} reason — shown to the user (e.g. "Sign in to Damascus Transit Driver")
   * @returns {Promise<boolean>} — true if authenticated, false otherwise
   */
  async function authenticateBiometric(reason) {
    const bio = getPlugin('BiometricAuth');
    if (!bio) return false;

    try {
      // Check availability first
      const avail = await bio.checkBiometry();
      if (!avail.isAvailable) {
        console.log('[CapacitorBridge] Biometrics not available:', avail.biometryType);
        return false;
      }

      await bio.authenticate({
        reason: reason || 'تسجيل الدخول — Sign in to Damascus Transit',
        title: 'نقل دمشق',
        subtitle: 'Damascus Transit',
        cancelTitle: 'إلغاء — Cancel',
        allowDeviceCredential: true,
        iosFallbackTitle: 'Use Passcode',
      });
      return true;
    } catch (e) {
      // BiometryError.userCancel or authentication failure — not a crash
      console.log('[CapacitorBridge] Biometric auth failed/cancelled:', e.code || e.message);
      return false;
    }
  }

  /**
   * Returns the biometry type available on this device.
   * @returns {Promise<'touchId'|'faceId'|'fingerprint'|'none'>}
   */
  async function getBiometryType() {
    const bio = getPlugin('BiometricAuth');
    if (!bio) return 'none';
    try {
      const result = await bio.checkBiometry();
      if (!result.isAvailable) return 'none';
      const type = (result.biometryType || '').toLowerCase();
      if (type.includes('face')) return PLATFORM === 'ios' ? 'faceId' : 'face';
      if (type.includes('finger') || type.includes('touch')) return PLATFORM === 'ios' ? 'touchId' : 'fingerprint';
      return 'none';
    } catch (_) {
      return 'none';
    }
  }

  // ─── RTL Verification ────────────────────────────────────────────────────

  /**
   * Verifies RTL layout is correctly applied on native devices.
   * On Android, dir="rtl" can sometimes be overridden by system settings.
   * Forces RTL at the document level and logs any inconsistencies.
   */
  function enforceRTL() {
    const html = document.documentElement;
    const body = document.body;

    if (html.getAttribute('lang') === 'ar') {
      html.setAttribute('dir', 'rtl');
      body.style.direction = 'rtl';
      body.style.textAlign = 'right';

      // On Android, also set layoutDirection via style
      if (PLATFORM === 'android') {
        body.style.unicodeBidi = 'embed';
      }
    }

    // Log mismatch for debugging
    const computedDir = window.getComputedStyle(body).direction;
    if (computedDir !== 'rtl' && html.getAttribute('lang') === 'ar') {
      console.warn('[CapacitorBridge] RTL mismatch detected — forcing direction:rtl on body');
      body.style.direction = 'rtl';
    }
  }

  // ─── App Lifecycle ────────────────────────────────────────────────────────

  /**
   * Listens for native app lifecycle events (foreground/background).
   *
   * @param {function} onResume  — called when app comes to foreground
   * @param {function} onPause   — called when app goes to background
   */
  function listenAppLifecycle(onResume, onPause) {
    const app = getPlugin('App');
    if (!app) return;
    app.addListener('appStateChange', (state) => {
      if (state.isActive) {
        onResume && onResume();
      } else {
        onPause && onPause();
      }
    });
  }

  // ─── Haptics ─────────────────────────────────────────────────────────────

  /**
   * Triggers a short haptic feedback pulse (e.g. on button tap, alert).
   * @param {'light'|'medium'|'heavy'} style
   */
  async function vibrate(style) {
    const haptics = getPlugin('Haptics');
    if (!haptics) {
      // Browser fallback
      if (navigator.vibrate) navigator.vibrate(style === 'heavy' ? 200 : style === 'medium' ? 100 : 50);
      return;
    }
    try {
      const ImpactStyle = { light: 'LIGHT', medium: 'MEDIUM', heavy: 'HEAVY' };
      await haptics.impact({ style: ImpactStyle[style] || 'MEDIUM' });
    } catch (_) {}
  }

  // ─── Public API ───────────────────────────────────────────────────────────

  window.CapacitorBridge = {
    IS_NATIVE,
    PLATFORM,

    // Lifecycle
    hideSplash,
    setupStatusBar,
    listenAppLifecycle,

    // Location
    requestLocationPermission,
    watchPosition,
    startBackgroundGeolocation,

    // Push
    registerPushNotifications,

    // Camera
    captureIncidentPhoto,

    // Biometrics
    authenticateBiometric,
    getBiometryType,

    // UI
    enforceRTL,
    vibrate,
  };

})(window);
