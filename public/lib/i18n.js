/**
 * i18n.js — bilingual (AR + EN) string table + DOM bind.
 * Updated 25 May 2026 for the Syrian national identity redesign.
 *
 * Usage in HTML:
 *   <h1 data-i18n="hero.title">…fallback Arabic copy…</h1>
 *   <input data-i18n-placeholder="passenger.searchHint">
 *   <button data-i18n-aria-label="header.toggleLang">EN</button>
 *
 * The fallback text inside the element is ALWAYS the Arabic copy so the
 * page reads correctly even if JS is disabled.
 *
 * To switch languages at runtime:
 *   I18N.setLang('en');   // → updates <html lang>, dir, and every data-i18n node
 *   I18N.setLang('ar');
 *
 * Persists to localStorage as `dt_lang`.
 */
(function (window, document) {
  'use strict';

  // ----- Dictionary -----------------------------------------------------------
  const DICT = {
    ar: {
      'app.title':            'نقل دمشق',
      'app.tagline':          'الجمهورية العربية السورية · نظام النقل العام',

      'header.home':          'الرئيسية',
      'header.passenger':     'للركاب',
      'header.driver':        'للسائقين',
      'header.admin':         'دخول الإدارة',
      'header.toggleLang':    'EN',
      'header.live':          'مباشر',

      'hero.eyebrow':         'الجمهورية العربية السورية · نظام النقل العام',
      'hero.title':           'تتبع حافلات دمشق في الوقت الحقيقي',
      'hero.sub':             'منصة وطنية مفتوحة المصدر تربط الركاب والسائقين والمشرفين بمواقع الحافلات وأوقات الوصول لحظياً، بدون إعلانات وبدون مقابل.',
      'hero.ctaPrimary':      'ابحث عن خطك',
      'hero.ctaSecondary':    'عرض الخريطة المباشرة',
      'hero.liveBadge':       'البيانات تُحدَّث كل ٥ ثوانٍ',

      'stat.active':          'حافلات عاملة',
      'stat.activeFrom':      'من إجمالي الأسطول',
      'stat.routes':          'عدد الخطوط',
      'stat.routesSub':       'تغطي محاور المدينة',
      'stat.stops':           'عدد المحطات',
      'stat.stopsSub':        'منتشرة في دمشق',
      'stat.occupancy':       'متوسط الإشغال',
      'stat.occupancySub':    'حسب آخر تحديث',
      'stat.fleet':           'إجمالي الحافلة',

      'map.title':            'الخريطة المباشرة',
      'map.connected':        'متصل',
      'map.disconnected':     'انقطع البث',
      'map.legendBus':        'حافلة',
      'map.legendStop':       'محطة',

      'routes.title':         'الخطوط',
      'routes.viewAll':       'عرض الكل',
      'routes.stopsCount':    'محطة',
      'routes.none':          'لا توجد خطوط حالياً.',

      'features.title':       'لماذا نقل دمشق؟',
      'features.live.title':  'تتبع لحظي',
      'features.live.body':   'مواقع الحافلات تُبَث عبر SSE كل ٥ ثوانٍ. أوقات الوصول دقيقة محسوبة من PostGIS.',
      'features.offline.title': 'يعمل دون اتصال',
      'features.offline.body':  'تطبيق ويب تقدُّمي (PWA) يخزن المحطات والخطوط محلياً ويعمل بدون شبكة.',
      'features.security.title':'خصوصية وأمان',
      'features.security.body': 'JWT مع RBAC، تشفير bcrypt، CSP صارم، ومراقبة الأخطاء عبر Sentry.',

      'passenger.welcome':    'أهلاً بك',
      'passenger.sub':        'ابحث عن محطتك أو خطك أو شاهد أقرب الحافلات.',
      'passenger.searchHint': 'اسم محطة أو خط (مثال: مزة، باب توما)',
      'passenger.nearest':    'أقرب المحطات إليك',
      'passenger.locate':     'موقعي',
      'passenger.popular':    'الخطوط الشائعة',
      'passenger.nearby':     'حافلات قريبة',
      'passenger.quick':      'روابط سريعة',
      'passenger.gtfs':       'جدول GTFS',
      'passenger.gtfsSub':    'بيانات الخطوط القابلة للتنزيل',
      'passenger.home':       'الرئيسية',
      'passenger.homeSub':    'العودة للوحة العامة',
      'passenger.tabHome':    'الرئيسية',
      'passenger.tabNearby':  'قريب',
      'passenger.tabRoutes':  'الخطوط',
      'passenger.tabAccount': 'حسابي',
      'passenger.noStops':    'لا توجد محطات قريبة ضمن ١٫٥ كم.',
      'passenger.install':    'ثبّت التطبيق',
      'passenger.installSub': 'للوصول السريع وأداء أفضل خارج المتصفح.',
      'passenger.installBtn': 'تثبيت',

      'driver.login':         'دخول السائق',
      'driver.loginSub':      'أدخل بريدك وكلمة المرور، أو استخدم البصمة إن كانت مفعّلة.',
      'driver.email':         'البريد',
      'driver.password':      'كلمة المرور',
      'driver.signIn':        'دخول',
      'driver.biometric':     'الدخول ببصمة الإصبع',
      'driver.invalid':       'بيانات الدخول غير صحيحة',
      'driver.vehicle':       'حافلة',
      'driver.gpsConnecting': 'جاري الاتصال…',
      'driver.gpsConnected':  'مرتبط بالقمر',
      'driver.gpsOff':        'بدون GPS',
      'driver.startTrip':     '▶ بدء الرحلة',
      'driver.endTrip':       '■ إنهاء الرحلة',
      'driver.passengers':    'عدد الركاب',
      'driver.speed':         'السرعة',
      'driver.distance':      'المسافة',
      'driver.time':          'المدة',
      'driver.occupancy':     'الإشغال',
      'driver.incident':      '🚨 الإبلاغ عن حادث',
      'driver.offline':       'دون اتصال — يتم تخزين المواقع محلياً وستُرسل عند العودة',

      'admin.title':          'دخول الإدارة',
      'admin.sub':            'للوصول للوحة الإدارة، الموزّعين، والسائقين.',
      'admin.role.admin':     'إدارة',
      'admin.role.dispatcher':'موزّع',
      'admin.role.driver':    'سائق',
      'admin.email':          'البريد الإلكتروني',
      'admin.password':       'كلمة المرور',
      'admin.signIn':         'دخول',
      'admin.signingIn':      '... جاري الدخول',
      'admin.remember':       'تذكّرني لمدة ٣٠ يوماً',
      'admin.forgot':         'نسيت كلمة المرور؟',
      'admin.contact':        'تواجه مشكلة في الدخول؟ راسل المسؤول',
      'admin.error':          'بيانات الدخول غير صحيحة',
      'admin.captcha':        'يرجى إكمال التحقق من خانة الإنسان',

      'error.generic':        'حدث خطأ ما، حاول مجدداً.',
      'error.network':        'تعذّر الاتصال بالخادم.',
      'error.unauthorized':   'انتهت صلاحية الجلسة. يرجى تسجيل الدخول من جديد.',
      'error.notFound':       'لم يُعثر على المورد.',
      'common.retry':         'إعادة المحاولة',
      'common.cancel':        'إلغاء',
      'common.save':          'حفظ',
      'common.close':         'إغلاق',
      'common.loading':       'جاري التحميل…',

      'footer.copyright':     '© ٢٠٢٦ نقل دمشق — الجمهورية العربية السورية',
      'footer.opensource':    'مشروع مفتوح المصدر تحت رخصة MIT.',
      'footer.privacy':       'سياسة الخصوصية',
      'footer.terms':         'الشروط',
    },

    en: {
      'app.title':            'Damascus Transit',
      'app.tagline':          'Syrian Arab Republic · Public Transit System',

      'header.home':          'Home',
      'header.passenger':     'Passengers',
      'header.driver':        'Drivers',
      'header.admin':         'Admin sign-in',
      'header.toggleLang':    'ع',
      'header.live':          'Live',

      'hero.eyebrow':         'Syrian Arab Republic · Public Transit',
      'hero.title':           'Real-time Damascus bus tracking',
      'hero.sub':             'A national open-source platform connecting passengers, drivers, and dispatchers to live bus positions and accurate arrival times. Ad-free and free of charge.',
      'hero.ctaPrimary':      'Find your route',
      'hero.ctaSecondary':    'Open the live map',
      'hero.liveBadge':       'Refreshed every 5 seconds',

      'stat.active':          'Active vehicles',
      'stat.activeFrom':      'of total fleet',
      'stat.routes':          'Routes',
      'stat.routesSub':       'across the city',
      'stat.stops':           'Stops',
      'stat.stopsSub':        'served in Damascus',
      'stat.occupancy':       'Avg. occupancy',
      'stat.occupancySub':    'as of last update',
      'stat.fleet':           'Total fleet',

      'map.title':            'Live map',
      'map.connected':        'Connected',
      'map.disconnected':     'Disconnected',
      'map.legendBus':        'Bus',
      'map.legendStop':       'Stop',

      'routes.title':         'Routes',
      'routes.viewAll':       'See all',
      'routes.stopsCount':    'stops',
      'routes.none':          'No routes available right now.',

      'features.title':       'Why Damascus Transit?',
      'features.live.title':  'Live tracking',
      'features.live.body':   'Vehicle positions stream over SSE every 5 seconds. Arrival times are computed from PostGIS.',
      'features.offline.title': 'Works offline',
      'features.offline.body':  'A progressive web app that caches routes and stops on your device and works without a connection.',
      'features.security.title':'Privacy & security',
      'features.security.body': 'JWT + RBAC, bcrypt password hashing, strict CSP, and error monitoring via Sentry.',

      'passenger.welcome':    'Welcome',
      'passenger.sub':        'Find a stop, search a route, or watch nearby buses.',
      'passenger.searchHint': 'Stop or route (e.g. Mezzeh, Bab Touma)',
      'passenger.nearest':    'Stops near you',
      'passenger.locate':     'My location',
      'passenger.popular':    'Popular routes',
      'passenger.nearby':     'Nearby buses',
      'passenger.quick':      'Quick links',
      'passenger.gtfs':       'GTFS feed',
      'passenger.gtfsSub':    'Downloadable route data',
      'passenger.home':       'Home',
      'passenger.homeSub':    'Back to the public dashboard',
      'passenger.tabHome':    'Home',
      'passenger.tabNearby':  'Nearby',
      'passenger.tabRoutes':  'Routes',
      'passenger.tabAccount': 'Account',
      'passenger.noStops':    'No stops within 1.5 km.',
      'passenger.install':    'Install the app',
      'passenger.installSub': 'For faster access outside the browser.',
      'passenger.installBtn': 'Install',

      'driver.login':         'Driver sign-in',
      'driver.loginSub':      'Sign in with email + password, or use fingerprint if enabled.',
      'driver.email':         'Email',
      'driver.password':      'Password',
      'driver.signIn':        'Sign in',
      'driver.biometric':     'Use fingerprint',
      'driver.invalid':       'Invalid credentials',
      'driver.vehicle':       'Vehicle',
      'driver.gpsConnecting': 'Connecting…',
      'driver.gpsConnected':  'GPS connected',
      'driver.gpsOff':        'No GPS',
      'driver.startTrip':     '▶ Start trip',
      'driver.endTrip':       '■ End trip',
      'driver.passengers':    'Passengers',
      'driver.speed':         'Speed',
      'driver.distance':      'Distance',
      'driver.time':          'Duration',
      'driver.occupancy':     'Occupancy',
      'driver.incident':      '🚨 Report incident',
      'driver.offline':       'Offline — positions stored locally, will sync on reconnect',

      'admin.title':          'Admin sign-in',
      'admin.sub':            'For the admin, dispatcher, and driver dashboards.',
      'admin.role.admin':     'Admin',
      'admin.role.dispatcher':'Dispatcher',
      'admin.role.driver':    'Driver',
      'admin.email':          'Email address',
      'admin.password':       'Password',
      'admin.signIn':         'Sign in',
      'admin.signingIn':      'Signing in…',
      'admin.remember':       'Keep me signed in for 30 days',
      'admin.forgot':         'Forgot password?',
      'admin.contact':        'Trouble signing in? Email the administrator',
      'admin.error':          'Invalid credentials',
      'admin.captcha':        'Please complete the human verification',

      'error.generic':        'Something went wrong. Please try again.',
      'error.network':        'Could not reach the server.',
      'error.unauthorized':   'Session expired. Please sign in again.',
      'error.notFound':       'Resource not found.',
      'common.retry':         'Retry',
      'common.cancel':        'Cancel',
      'common.save':          'Save',
      'common.close':         'Close',
      'common.loading':       'Loading…',

      'footer.copyright':     '© 2026 Damascus Transit — Syrian Arab Republic',
      'footer.opensource':    'Open-source under the MIT license.',
      'footer.privacy':       'Privacy policy',
      'footer.terms':         'Terms of use',
    },
  };

  // ----- Locale state ---------------------------------------------------------
  const STORAGE_KEY = 'dt_lang';
  let current = (function () {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'ar' || saved === 'en') return saved;
    } catch (_) {}
    const htmlLang = (document.documentElement.lang || '').slice(0, 2).toLowerCase();
    return htmlLang === 'en' ? 'en' : 'ar';
  })();

  function t(key) {
    const table = DICT[current] || DICT.ar;
    return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : key;
  }

  function bind(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach((el) => {
      const k = el.getAttribute('data-i18n');
      if (k) el.textContent = t(k);
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const k = el.getAttribute('data-i18n-placeholder');
      if (k) el.setAttribute('placeholder', t(k));
    });
    root.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
      const k = el.getAttribute('data-i18n-aria-label');
      if (k) el.setAttribute('aria-label', t(k));
    });
    root.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const k = el.getAttribute('data-i18n-title');
      if (k) el.setAttribute('title', t(k));
    });
    root.querySelectorAll('[data-i18n-alt]').forEach((el) => {
      const k = el.getAttribute('data-i18n-alt');
      if (k) el.setAttribute('alt', t(k));
    });
  }

  function setLang(lang) {
    if (lang !== 'ar' && lang !== 'en') return;
    current = lang;
    try { localStorage.setItem(STORAGE_KEY, lang); } catch (_) {}
    document.documentElement.lang = lang;
    document.documentElement.dir  = (lang === 'ar') ? 'rtl' : 'ltr';
    bind(document);
    document.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang } }));
  }

  function toggle() { setLang(current === 'ar' ? 'en' : 'ar'); }

  function attachToggle(root) {
    (root || document).querySelectorAll('[data-i18n-toggle]').forEach((btn) => {
      if (btn.__i18nBound) return;
      btn.__i18nBound = true;
      btn.addEventListener('click', toggle);
    });
  }

  function boot() {
    if (document.documentElement.lang !== current) {
      document.documentElement.lang = current;
      document.documentElement.dir  = (current === 'ar') ? 'rtl' : 'ltr';
    }
    bind(document);
    attachToggle(document);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  window.I18N = { t, setLang, toggle, bind, attachToggle, get lang() { return current; } };
})(window, document);
