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
      'routes.mainTitle':     'الخطوط الرئيسية',
      'routes.viewAll':       'عرض الكل ←',
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
      'passenger.searchResults':'نتائج البحث',
      'passenger.searchEmpty':  'لا نتائج مطابقة.',
      'passenger.searchPrompt': 'اكتب اسم محطة أو خط للبحث.',
      'passenger.routesGroup':  'الخطوط',
      'passenger.stopsGroup':   'المحطات',
      'passenger.back':         '→ رجوع',
      'passenger.routeStops':   'محطات الخط',
      'passenger.noRouteStops': 'لا توجد محطات لهذا الخط.',
      'passenger.tapForEta':    'اضغط لعرض مواعيد الوصول',
      'passenger.loadingEta':   'جاري الحساب…',
      'passenger.noEta':        'لا حافلات قريبة الآن.',
      'passenger.updateReady':  'يتوفر إصدار جديد',
      'passenger.updateBtn':    'تحديث',

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
      'admin.contactPrefix':  'تواجه مشكلة في الدخول؟',
      'admin.contactLink':    'راسل المسؤول',
      'admin.error':          'بيانات الدخول غير صحيحة',
      'admin.captcha':        'يرجى إكمال التحقق من خانة الإنسان',
      'admin.rolePicker':     'نوع الدخول',
      'admin.pwToggle':       'إظهار/إخفاء كلمة المرور',

      // ─── Admin dashboard (post-login) ──────────────────────────────────────
      'admin.brand':          'نقل دمشق',
      'admin.brandSub':       'لوحة الإدارة',
      'admin.logout':         'تسجيل الخروج',
      'admin.live':           'مباشر',
      'admin.refresh':        'تحديث',
      'admin.viewAll':        'عرض الكل ←',
      'admin.langToggle':     'EN',

      'admin.nav.overview':   'النظرة العامة',
      'admin.nav.vehicles':   'الحافلات',
      'admin.nav.users':      'المستخدمون',
      'admin.nav.routes':     'الخطوط',
      'admin.nav.dispatch':   'توزيع الرحلات',
      'admin.nav.alerts':     'التنبيهات',
      'admin.nav.analytics':  'التحليلات',
      'admin.nav.help':       'كيفية الاستخدام',
      'admin.nav.approvals':  'الموافقات',
      'admin.nav.payments':   'المدفوعات',
      'admin.nav.audit':      'سجل التدقيق',
      'admin.approvals.title': 'موافقات تشغيل المركبات',
      'admin.approvals.sub':  'راجع طلبات المشغّلين واعتمد المركبات المسموح لها بالعمل. لا تعمل أي مركبة قبل موافقة الإدارة.',
      'admin.approvals.empty': 'لا توجد طلبات بانتظار الموافقة.',
      'admin.approvals.approve': 'اعتماد',
      'admin.approvals.reject': 'رفض',
      'admin.approvals.suspend': 'تعليق',
      'admin.approvals.resubmit': 'إعادة للانتظار',
      'admin.payments.title': 'المدفوعات — شام كاش',
      'admin.payments.sub':   'سجل عمليات دفع الأجرة عبر مسح رمز QR. وضع التجربة لا يحرّك أموالاً حقيقية.',
      'admin.payments.empty': 'لا توجد عمليات دفع بعد.',
      'admin.audit.title':    'سجل التدقيق',
      'admin.audit.sub':      'كل إجراء إداري (إنشاء، موافقة، تعيين) يسجَّل هنا تلقائياً.',
      'admin.dispatch.title': 'توزيع الرحلات',
      'admin.dispatch.sub':   'جدوِل رحلة وادفعها إلى سائق؛ تظهر له فوراً لتأكيدها.',
      'admin.dispatch.driver':'السائق',
      'admin.dispatch.vehicle':'المركبة',
      'admin.dispatch.route': 'الخط',
      'admin.dispatch.when':  'الموعد',
      'admin.dispatch.pax':   'ركاب مخططون',
      'admin.dispatch.status':'الحالة',

      'admin.overview.title': 'النظرة العامة',
      'admin.overview.sub':   'حالة الأسطول، التنبيهات، والخريطة المباشرة.',
      'admin.kpi.active':     'الحافلات العاملة',
      'admin.kpi.activeDelta':'+٢ منذ الأمس',
      'admin.kpi.trips':      'إجمالي الرحلات اليوم',
      'admin.kpi.tripsDelta': '+١٢٪',
      'admin.kpi.occupancy':  'متوسط الإشغال',
      'admin.kpi.alertsOpen': 'تنبيهات مفتوحة',
      'admin.kpi.alertsUrgent':'٣ عاجلة',

      'admin.map.title':      'الخريطة المباشرة',
      'admin.map.refresh':    'يُحدَّث كل ٥ ثوانٍ',
      'admin.alerts.title':   'التنبيهات الأخيرة',
      'admin.alerts.none':    'لا تنبيهات جديدة.',

      // ─── Vehicles page ─────────────────────────────────────────────────────
      'admin.vehicles.title': 'الحافلات',
      'admin.vehicles.sub':   'قائمة الأسطول كاملاً مع الخط المعيّن والسعة والحالة.',
      'admin.vehicles.code':  'رمز الحافلة',
      'admin.vehicles.name':  'الاسم',
      'admin.vehicles.type':  'النوع',
      'admin.vehicles.route': 'الخط المعيّن',
      'admin.vehicles.capacity':'السعة',
      'admin.vehicles.status':'الحالة',
      'admin.vehicles.empty': 'لم يتم إضافة حافلات بعد.',
      'admin.vehicles.status.active':'تعمل',
      'admin.vehicles.status.idle':'متوقف',
      'admin.vehicles.status.maintenance':'صيانة',
      'admin.vehicles.status.decommissioned':'مُستبعَدة',
      'admin.vehicles.status.offline':'متوقفة',
      'admin.vehicles.status.unassigned':'دون خط',

      // ─── Users page ────────────────────────────────────────────────────────
      'admin.users.title':    'المستخدمون',
      'admin.users.sub':      'المسؤولون، الموزّعون، والسائقون الذين لديهم حق الوصول.',
      'admin.users.name':     'الاسم',
      'admin.users.email':    'البريد الإلكتروني',
      'admin.users.role':     'الصلاحية',
      'admin.users.status':   'الحالة',
      'admin.users.last':     'آخر دخول',
      'admin.users.empty':    'لم يتم إضافة مستخدمين بعد.',
      'admin.users.active':   'مفعّل',
      'admin.users.inactive': 'موقوف',
      'admin.users.never':    'لم يدخل بعد',

      // ─── Routes page ───────────────────────────────────────────────────────
      'admin.routes.title':   'الخطوط',
      'admin.routes.sub':     'خطوط النقل العام في دمشق مع لون التعريف وعدد الحافلات.',
      'admin.routes.color':   'اللون',
      'admin.routes.short':   'رمز الخط',
      'admin.routes.name':    'الاسم',
      'admin.routes.stops':   'عدد المحطات',
      'admin.routes.vehicles':'الحافلات',
      'admin.routes.status':  'الحالة',
      'admin.routes.empty':   'لم يتم إضافة خطوط بعد.',

      // ─── Alerts page ───────────────────────────────────────────────────────
      'admin.alertsPage.title':'التنبيهات',
      'admin.alertsPage.sub':  'تنبيهات الأسطول مرتبة حسب الأحدث.',
      'admin.alertsPage.when': 'الوقت',
      'admin.alertsPage.type': 'النوع',
      'admin.alertsPage.severity':'الخطورة',
      'admin.alertsPage.titleCol':'العنوان',
      'admin.alertsPage.vehicle':'الحافلة',
      'admin.alertsPage.status':'الحالة',
      'admin.alertsPage.open':'مفتوح',
      'admin.alertsPage.resolved':'تمت المعالجة',
      'admin.alertsPage.empty':'لا توجد تنبيهات حالياً.',
      'admin.alertsPage.action':'الإجراء',
      'admin.alertsPage.resolveBtn':'إغلاق التنبيه',
      'admin.severity.low':   'منخفضة',
      'admin.severity.medium':'متوسطة',
      'admin.severity.high':  'عالية',
      'admin.severity.critical':'حرجة',

      // ─── Analytics page ────────────────────────────────────────────────────
      'admin.analytics.title':  'أداء الشبكة',
      'admin.analytics.sub':    'مؤشرات الرحلات، الدقّة، الإشغال، والحوادث.',
      'admin.analytics.range24h':'آخر ٢٤ ساعة',
      'admin.analytics.range7d':'أسبوع',
      'admin.analytics.range30d':'شهر',
      'admin.analytics.tripsTotal':'رحلات هذا الأسبوع',
      'admin.analytics.onTime':  'دقّة المواعيد',
      'admin.analytics.onTimeSub':'على الموعد ±٣ د',
      'admin.analytics.speed':   'انتهاكات السرعة',
      'admin.analytics.speedSub':'≥ ٧٠ كم/س داخل المدينة',
      'admin.analytics.tripsChart':'الرحلات خلال الأسبوع',
      'admin.analytics.occChart':'توزيع الإشغال',
      'admin.analytics.routePerf':'أداء الخطوط',
      'admin.analytics.topIncidents':'أكثر الحوادث شيوعاً',
      'admin.analytics.deltaSub':'مقارنة بالأسبوع السابق',
      'admin.analytics.thRoute': 'الخط',
      'admin.analytics.thTrips': 'رحلات',
      'admin.analytics.thAccuracy':'دقة',
      'admin.analytics.thOccupancy':'إشغال',

      'common.search':         'بحث',

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
      'footer.copyrightLogin':'© ٢٠٢٦ نقل دمشق',
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
      'routes.mainTitle':     'Main routes',
      'routes.viewAll':       'See all →',
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
      'passenger.searchResults':'Search results',
      'passenger.searchEmpty':  'No matching results.',
      'passenger.searchPrompt': 'Type a stop or route name to search.',
      'passenger.routesGroup':  'Routes',
      'passenger.stopsGroup':   'Stops',
      'passenger.back':         '← Back',
      'passenger.routeStops':   'Route stops',
      'passenger.noRouteStops': 'No stops for this route.',
      'passenger.tapForEta':    'Tap to see arrivals',
      'passenger.loadingEta':   'Calculating…',
      'passenger.noEta':        'No buses nearby right now.',
      'passenger.updateReady':  'A new version is available',
      'passenger.updateBtn':    'Update',

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
      'admin.contactPrefix':  'Trouble signing in?',
      'admin.contactLink':    'Email the administrator',
      'admin.error':          'Invalid credentials',
      'admin.captcha':        'Please complete the human verification',
      'admin.rolePicker':     'Sign-in type',
      'admin.pwToggle':       'Show/hide password',

      // ─── Admin dashboard (post-login) ──────────────────────────────────────
      'admin.brand':          'Damascus Transit',
      'admin.brandSub':       'Admin Console',
      'admin.logout':         'Sign out',
      'admin.live':           'Live',
      'admin.refresh':        'Refresh',
      'admin.viewAll':        'View all →',
      'admin.langToggle':     'AR',

      'admin.nav.overview':   'Overview',
      'admin.nav.vehicles':   'Vehicles',
      'admin.nav.users':      'Users',
      'admin.nav.routes':     'Routes',
      'admin.nav.dispatch':   'Dispatch',
      'admin.nav.alerts':     'Alerts',
      'admin.nav.analytics':  'Analytics',
      'admin.nav.help':       'How it works',
      'admin.nav.approvals':  'Approvals',
      'admin.nav.payments':   'Payments',
      'admin.nav.audit':      'Audit log',
      'admin.approvals.title': 'Vehicle operating approvals',
      'admin.approvals.sub':  'Review operator submissions and authorise vehicles to operate. No vehicle runs before admin approval.',
      'admin.approvals.empty': 'No vehicles awaiting approval.',
      'admin.approvals.approve': 'Approve',
      'admin.approvals.reject': 'Reject',
      'admin.approvals.suspend': 'Suspend',
      'admin.approvals.resubmit': 'Back to pending',
      'admin.payments.title': 'Payments — Sham Cash',
      'admin.payments.sub':   'Fare payments collected by QR scan. Sandbox mode moves no real money.',
      'admin.payments.empty': 'No payments yet.',
      'admin.audit.title':    'Audit log',
      'admin.audit.sub':      'Every administrative action (create, approve, assign) is recorded here automatically.',
      'admin.dispatch.title': 'Dispatch trips',
      'admin.dispatch.sub':   'Schedule a trip and push it to a driver — it appears on their console to acknowledge.',
      'admin.dispatch.driver':'Driver',
      'admin.dispatch.vehicle':'Vehicle',
      'admin.dispatch.route': 'Route',
      'admin.dispatch.when':  'When',
      'admin.dispatch.pax':   'Planned pax',
      'admin.dispatch.status':'Status',

      'admin.overview.title': 'Overview',
      'admin.overview.sub':   'Fleet status, alerts, and live map.',
      'admin.kpi.active':     'Active vehicles',
      'admin.kpi.activeDelta':'+2 since yesterday',
      'admin.kpi.trips':      'Trips today',
      'admin.kpi.tripsDelta': '+12%',
      'admin.kpi.occupancy':  'Average occupancy',
      'admin.kpi.alertsOpen': 'Open alerts',
      'admin.kpi.alertsUrgent':'3 urgent',

      'admin.map.title':      'Live map',
      'admin.map.refresh':    'Refreshes every 5 seconds',
      'admin.alerts.title':   'Recent alerts',
      'admin.alerts.none':    'No new alerts.',

      // ─── Vehicles page ─────────────────────────────────────────────────────
      'admin.vehicles.title': 'Vehicles',
      'admin.vehicles.sub':   'Full fleet roster with assigned route, capacity, and status.',
      'admin.vehicles.code':  'Vehicle ID',
      'admin.vehicles.name':  'Name',
      'admin.vehicles.type':  'Type',
      'admin.vehicles.route': 'Assigned route',
      'admin.vehicles.capacity':'Capacity',
      'admin.vehicles.status':'Status',
      'admin.vehicles.empty': 'No vehicles registered yet.',
      'admin.vehicles.status.active':'Active',
      'admin.vehicles.status.idle':'Idle',
      'admin.vehicles.status.maintenance':'Maintenance',
      'admin.vehicles.status.decommissioned':'Decommissioned',
      'admin.vehicles.status.offline':'Offline',
      'admin.vehicles.status.unassigned':'No route',

      // ─── Users page ────────────────────────────────────────────────────────
      'admin.users.title':    'Users',
      'admin.users.sub':      'Admins, dispatchers, and drivers who can sign in.',
      'admin.users.name':     'Name',
      'admin.users.email':    'Email',
      'admin.users.role':     'Role',
      'admin.users.status':   'Status',
      'admin.users.last':     'Last seen',
      'admin.users.empty':    'No users yet.',
      'admin.users.active':   'Active',
      'admin.users.inactive': 'Suspended',
      'admin.users.never':    'Never',

      // ─── Routes page ───────────────────────────────────────────────────────
      'admin.routes.title':   'Routes',
      'admin.routes.sub':     'Damascus transit lines with identity colour and assigned fleet.',
      'admin.routes.color':   'Colour',
      'admin.routes.short':   'Code',
      'admin.routes.name':    'Name',
      'admin.routes.stops':   'Stops',
      'admin.routes.vehicles':'Vehicles',
      'admin.routes.status':  'Status',
      'admin.routes.empty':   'No routes yet.',

      // ─── Alerts page ───────────────────────────────────────────────────────
      'admin.alertsPage.title':'Alerts',
      'admin.alertsPage.sub':  'Fleet alerts, newest first.',
      'admin.alertsPage.when': 'When',
      'admin.alertsPage.type': 'Type',
      'admin.alertsPage.severity':'Severity',
      'admin.alertsPage.titleCol':'Title',
      'admin.alertsPage.vehicle':'Vehicle',
      'admin.alertsPage.status':'Status',
      'admin.alertsPage.open':'Open',
      'admin.alertsPage.resolved':'Resolved',
      'admin.alertsPage.empty':'No alerts at this time.',
      'admin.alertsPage.action':'Action',
      'admin.alertsPage.resolveBtn':'Mark resolved',
      'admin.severity.low':   'Low',
      'admin.severity.medium':'Medium',
      'admin.severity.high':  'High',
      'admin.severity.critical':'Critical',

      // ─── Analytics page ────────────────────────────────────────────────────
      'admin.analytics.title':  'Network performance',
      'admin.analytics.sub':    'Trips, on-time accuracy, occupancy, and incidents.',
      'admin.analytics.range24h':'Last 24h',
      'admin.analytics.range7d':'Week',
      'admin.analytics.range30d':'Month',
      'admin.analytics.tripsTotal':'Trips this week',
      'admin.analytics.onTime':  'On-time accuracy',
      'admin.analytics.onTimeSub':'On schedule ±3 min',
      'admin.analytics.speed':   'Speed violations',
      'admin.analytics.speedSub':'≥ 70 km/h in city',
      'admin.analytics.tripsChart':'Trips over the week',
      'admin.analytics.occChart':'Occupancy distribution',
      'admin.analytics.routePerf':'Route performance',
      'admin.analytics.topIncidents':'Most frequent incidents',
      'admin.analytics.deltaSub':'vs previous week',
      'admin.analytics.thRoute': 'Route',
      'admin.analytics.thTrips': 'Trips',
      'admin.analytics.thAccuracy':'On-time',
      'admin.analytics.thOccupancy':'Occupancy',

      'common.search':         'Search',

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
      'footer.copyrightLogin':'© 2026 Damascus Transit',
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
