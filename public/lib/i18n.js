/**
 * Damascus Transit i18n Framework
 * Supports Arabic (RTL) and English (LTR) for all frontend apps.
 *
 * Usage:
 *   HTML: <span data-i18n="key">fallback text</span>
 *         <input data-i18n-placeholder="key" placeholder="fallback">
 *   JS:   t('key')          — returns translated string
 *         i18n.t('key', { speed: 60 })  — with interpolation
 *         i18n.toggleLanguage()          — switch between ar/en
 *         i18n.getCurrentLang()          — returns 'ar' or 'en'
 *
 * The current language is persisted in localStorage under 'dt_lang'.
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'dt_lang';
  const DEFAULT_LANG = 'ar';

  /* ─────────────────────────────────────────────────────────────────────
   * TRANSLATIONS
   * Each key maps to { ar: '...', en: '...' }.
   * Keys are namespaced by app prefix for clarity:
   *   (no prefix)  — shared across all apps
   *   dash.*       — main dashboard (index.html)
   *   drv.*        — driver app
   *   adm.*        — admin dashboard
   *   pax.*        — passenger app
   * ───────────────────────────────────────────────────────────────────── */
  const dict = {

    /* ── Shared ───────────────────────────────────────────────── */
    loading:                 { ar: 'جاري التحميل...', en: 'Loading...' },
    loading_short:           { ar: 'جاري التحميل', en: 'Loading' },
    connected:               { ar: 'متصل', en: 'Connected' },
    disconnected:            { ar: 'غير متصل', en: 'Disconnected' },
    route:                   { ar: 'الخط', en: 'Route' },
    speed:                   { ar: 'السرعة', en: 'Speed' },
    direction:               { ar: 'الاتجاه', en: 'Direction' },
    source:                  { ar: 'المصدر', en: 'Source' },
    simulation:              { ar: 'محاكاة', en: 'Simulation' },
    type_bus:                { ar: 'حافلة', en: 'Bus' },
    type_microbus:           { ar: 'ميكروباص', en: 'Microbus' },
    type_taxi:               { ar: 'تاكسي', en: 'Taxi' },
    filter_all:              { ar: 'الكل', en: 'All' },
    filter_buses:            { ar: 'حافلات', en: 'Buses' },
    filter_microbuses:       { ar: 'ميكروباص', en: 'Microbuses' },
    filter_taxis:            { ar: 'تاكسي', en: 'Taxis' },
    cancel:                  { ar: 'إلغاء', en: 'Cancel' },
    save:                    { ar: 'حفظ', en: 'Save' },
    close:                   { ar: 'إغلاق', en: 'Close' },
    refresh:                 { ar: 'تحديث', en: 'Refresh' },
    email:                   { ar: 'البريد الإلكتروني', en: 'Email' },
    password:                { ar: 'كلمة المرور', en: 'Password' },
    login_btn:               { ar: 'دخول', en: 'Sign In' },
    logout:                  { ar: 'تسجيل الخروج', en: 'Logout' },
    status_active:           { ar: 'نشطة', en: 'Active' },
    status_idle:             { ar: 'خامدة', en: 'Idle' },
    status_maintenance:      { ar: 'صيانة', en: 'Maintenance' },
    actions:                 { ar: 'الإجراءات', en: 'Actions' },
    action:                  { ar: 'الإجراء', en: 'Action' },
    status:                  { ar: 'الحالة', en: 'Status' },
    type_col:                { ar: 'النوع', en: 'Type' },
    vehicle:                 { ar: 'المركبة', en: 'Vehicle' },
    name_col:                { ar: 'الاسم', en: 'Name' },
    trips:                   { ar: 'الرحلات', en: 'Trips' },
    lang_toggle:             { ar: 'English', en: 'عربي' },

    /* ── Main Dashboard (index.html) ─────────────────────────── */
    dash_active_vehicles:    { ar: 'مركبات نشطة', en: 'Active Vehicles' },
    dash_routes:             { ar: 'خطوط', en: 'Routes' },
    dash_vehicles:           { ar: 'المركبات', en: 'Vehicles' },
    dash_no_vehicles:        { ar: 'لا توجد مركبات', en: 'No Vehicles' },
    dash_error_load:         { ar: 'فشل في تحميل البيانات الأولية', en: 'Failed to load initial data' },
    dash_error_disconnect:   { ar: 'فقدان الاتصال بالخادم', en: 'Lost server connection' },
    dash_powered_by:         { ar: 'مدعوم من قبل DamascusTransit', en: 'Powered by DamascusTransit' },
    dash_passenger_app:      { ar: 'تطبيق الركاب', en: 'Passenger App' },
    dash_route_label:        { ar: 'الخط:', en: 'Route:' },
    dash_speed_label:        { ar: 'السرعة:', en: 'Speed:' },
    dash_direction_label:    { ar: 'الاتجاه:', en: 'Direction:' },
    dash_source_label:       { ar: 'المصدر:', en: 'Source:' },

    /* ── Driver App ──────────────────────────────────────────── */
    drv_title:               { ar: '🚌 نقل دمشق', en: '🚌 Damascus Transit' },
    drv_subtitle:            { ar: 'تطبيق السائق', en: 'Driver App' },
    drv_email_ph:            { ar: 'البريد الإلكتروني', en: 'Email' },
    drv_password_ph:         { ar: 'كلمة المرور', en: 'Password' },
    drv_login_btn:           { ar: 'دخول — Sign In', en: 'Sign In — دخول' },
    drv_fill_all:            { ar: 'يرجى ملء جميع الحقول', en: 'Please fill all fields' },
    drv_logging_in:          { ar: 'جاري الدخول...', en: 'Signing in...' },
    drv_login_failed:        { ar: 'فشل تسجيل الدخول', en: 'Login failed' },
    drv_connection_error:    { ar: 'خطأ في الاتصال', en: 'Connection error' },
    drv_driver_label:        { ar: 'سائق', en: 'Driver' },
    drv_no_trip:             { ar: 'لا رحلة', en: 'No Trip' },
    drv_on_route:            { ar: 'على المسار', en: 'On Route' },
    drv_off_route:           { ar: 'خارج المسار!', en: 'Off Route!' },
    drv_speed_unit:          { ar: 'كم/س', en: 'km/h' },
    drv_stopped:             { ar: 'متوقف · Stopped', en: 'Stopped · متوقف' },
    drv_moving:              { ar: 'متحرك · Moving', en: 'Moving · متحرك' },
    drv_trip_time:           { ar: 'وقت الرحلة', en: 'Trip Time' },
    drv_km_covered:          { ar: 'كم مقطوع', en: 'Km Covered' },
    drv_on_time:             { ar: 'الالتزام', en: 'On Time' },
    drv_next_stop:           { ar: 'المحطة التالية · Next Stop', en: 'Next Stop' },
    drv_min_abbrev:          { ar: 'د', en: 'min' },
    drv_passengers:          { ar: 'ركاب · Passengers', en: 'Passengers · ركاب' },
    drv_trip_idle:           { ar: 'ابدأ رحلة جديدة للبدء بتتبع التوقفات', en: 'Start a trip to begin tracking stops' },
    drv_trip_idle_sub:       { ar: 'Start a trip to begin tracking stops', en: 'ابدأ رحلة جديدة للبدء بتتبع التوقفات' },
    drv_start_new_trip:      { ar: 'بدء رحلة جديدة · Start New Trip', en: 'Start New Trip' },
    drv_select_route_msg:    { ar: 'اختر الخط قبل بدء الرحلة · Select route before starting', en: 'Select route before starting' },
    drv_line_a:              { ar: 'خط أ — Line A (المرجة ← الغربية)', en: 'Line A (Al-Marjeh ← Western Station)' },
    drv_line_b:              { ar: 'خط ب — Line B (القابون ← المزة)', en: 'Line B (Al-Qaboun ← Mazzeh)' },
    drv_line_c:              { ar: 'خط ج — Line C (الميدان ← ركن الدين)', en: 'Line C (Al-Midan ← Rukn Al-Din)' },
    drv_cancel:              { ar: 'إلغاء · Cancel', en: 'Cancel' },
    drv_start:               { ar: 'بدء · Start', en: 'Start' },
    drv_end_trip_title:      { ar: 'إنهاء الرحلة · End Trip', en: 'End Trip' },
    drv_confirm_end:         { ar: 'هل تريد إنهاء الرحلة الحالية؟ · End the current trip?', en: 'End the current trip?' },
    drv_back:                { ar: 'رجوع · Back', en: 'Back' },
    drv_end:                 { ar: 'إنهاء · End', en: 'End' },
    drv_action_start:        { ar: 'بدء رحلة · Start Trip', en: 'Start Trip · بدء' },
    drv_action_end:          { ar: 'إنهاء الرحلة · End Trip', en: 'End Trip · إنهاء' },
    drv_action_arrived:      { ar: 'وصلت · Arrived', en: 'Arrived · وصلت' },
    drv_action_report:       { ar: 'بلاغ · Report', en: 'Report · بلاغ' },
    drv_speed_warning:       { ar: '⚠️ تجاوز الحد المسموح! {speed} كم/س — Speed limit exceeded!', en: '⚠️ Speed limit exceeded! {speed} km/h' },
    drv_approaching:         { ar: '🚏 اقتراب من {nameAr} — Approaching {name}', en: '🚏 Approaching {name} — اقتراب من {nameAr}' },
    drv_off_route_alert:     { ar: '⚠️ خارج المسار المحدد! — You are off the designated route!', en: '⚠️ You are off the designated route! — خارج المسار!' },
    drv_km_ahead:            { ar: '{dist} كم · km ahead', en: '{dist} km ahead' },

    /* ── Admin Dashboard ─────────────────────────────────────── */
    adm_resolve:             { ar: 'حل', en: 'Resolve' },
    adm_resolved:            { ar: 'تم الحل', en: 'Resolved' },
    adm_assign:              { ar: 'تعيين', en: 'Assign' },
    adm_edit:                { ar: 'تحرير', en: 'Edit' },
    adm_no_data:             { ar: 'لا بيانات', en: 'No data' },
    adm_all_alerts_tab:      { ar: 'جميع التنبيهات', en: 'All Alerts' },
    adm_no_alerts_active:    { ar: 'لا توجد تنبيهات نشطة', en: 'No active alerts — all systems normal' },
    adm_no_alerts_short:     { ar: 'لا توجد تنبيهات', en: 'No alerts' },
    adm_no_vehicles_reg:     { ar: 'لا توجد مركبات مسجّلة', en: 'No vehicles registered' },
    adm_add_vehicle_hint:    { ar: 'أضف مركبة جديدة باستخدام زر الإضافة', en: 'Add a vehicle using the add button' },
    adm_no_routes_def:       { ar: 'لا توجد مسارات مُعرَّفة', en: 'No routes defined' },
    adm_add_routes_hint:     { ar: 'أضف مسارات عبر واجهة إدارة الشبكة', en: 'Add routes via the network management interface' },
    adm_no_drivers_reg:      { ar: 'لا يوجد سائقون مسجّلون', en: 'No drivers registered' },
    adm_add_driver_hint:     { ar: 'أضف سائقاً جديداً باستخدام زر الإضافة', en: 'Add a driver using the add button' },
    adm_driver_active:       { ar: 'نشط', en: 'Active' },
    adm_driver_inactive:     { ar: 'غير نشط', en: 'Inactive' },
    adm_chart_active:        { ar: 'نشطة', en: 'Active' },
    adm_chart_idle:          { ar: 'خاملة', en: 'Idle' },
    adm_chart_hour:          { ar: 'الساعة:', en: 'Hour:' },
    adm_vehicle_count:       { ar: 'عدد المركبات', en: 'Vehicle Count' },
    adm_route_type:          { ar: 'النوع:', en: 'Type:' },
    adm_route_stops:         { ar: 'عدد المحطات:', en: 'Stops:' },
    adm_route_distance:      { ar: 'المسافة:', en: 'Distance:' },
    adm_route_frequency:     { ar: 'التكرار:', en: 'Frequency:' },
    adm_general_type:        { ar: 'عام', en: 'General' },
    adm_role_admin:          { ar: 'مدير النظام', en: 'System Admin' },
    adm_role_super:          { ar: 'مدير عام', en: 'General Manager' },
    adm_role_dispatcher:     { ar: 'مشغّل', en: 'Dispatcher' },
    adm_connection_timeout:  { ar: 'انتهت مهلة الاتصال بالخادم', en: 'Connection timed out. Check your network.' },
    adm_connection_lost:     { ar: 'تعذّر الاتصال — جارٍ إعادة المحاولة', en: 'Connection lost, retrying...' },
    adm_no_data_drivers:     { ar: 'لا بيانات سائقين', en: 'No driver data' },
    adm_urban:               { ar: 'حضر', en: 'Urban' },
    adm_speed_unit:          { ar: 'كم/س', en: 'km/h' },
    adm_logo:                { ar: 'نقل دمشق', en: 'Damascus Transit' },
    adm_panel:               { ar: 'Damascus Transit Admin Panel', en: 'Damascus Transit Admin Panel' },
    adm_email_ph:            { ar: 'البريد الإلكتروني', en: 'Email' },
    adm_password_ph:         { ar: 'كلمة المرور', en: 'Password' },
    adm_login_btn:           { ar: 'دخول', en: 'Sign In' },
    adm_subtitle:            { ar: 'Admin Panel', en: 'لوحة تحكم' },
    adm_system_admin:        { ar: 'مدير النظام', en: 'System Admin' },
    adm_nav_dashboard:       { ar: 'لوحة التحكم', en: 'Dashboard' },
    adm_nav_vehicles:        { ar: 'المركبات', en: 'Vehicles' },
    adm_nav_routes:          { ar: 'المسارات', en: 'Routes' },
    adm_nav_alerts:          { ar: 'التنبيهات', en: 'Alerts' },
    adm_nav_drivers:         { ar: 'السائقون', en: 'Drivers' },
    adm_nav_analytics:       { ar: 'التحليلات', en: 'Analytics' },
    adm_page_dashboard:      { ar: 'لوحة التحكم', en: 'Dashboard' },
    adm_total_vehicles:      { ar: 'إجمالي المركبات', en: 'Total Vehicles' },
    adm_all_vehicles:        { ar: '📍 جميع المركبات', en: '📍 All Vehicles' },
    adm_active_vehicles:     { ar: 'المركبات النشطة', en: 'Active Vehicles' },
    adm_in_service:          { ar: '🟢 في الخدمة', en: '🟢 In Service' },
    adm_idle_vehicles:       { ar: 'مركبات خامدة', en: 'Idle Vehicles' },
    adm_stopped_vehicles:    { ar: '🔴 متوقفة', en: '🔴 Stopped' },
    adm_maintenance:         { ar: 'الصيانة', en: 'Maintenance' },
    adm_under_maintenance:   { ar: '🔧 قيد الصيانة', en: '🔧 Under Maintenance' },
    adm_trips_today:         { ar: 'الرحلات اليوم', en: 'Trips Today' },
    adm_schedule_adherence:  { ar: 'الالتزام بالجدول', en: 'Schedule Adherence' },
    adm_active_alerts:       { ar: 'التنبيهات النشطة', en: 'Active Alerts' },
    adm_add_vehicle:         { ar: '+ إضافة مركبة', en: '+ Add Vehicle' },
    adm_manage_vehicles:     { ar: 'إدارة المركبات', en: 'Manage Vehicles' },
    adm_manage_routes:       { ar: 'إدارة المسارات', en: 'Manage Routes' },
    adm_all_alerts:          { ar: 'جميع التنبيهات', en: 'All Alerts' },
    adm_all_types:           { ar: 'جميع الأنواع', en: 'All Types' },
    adm_all_statuses:        { ar: 'جميع الحالات', en: 'All Statuses' },
    adm_all_levels:          { ar: 'جميع المستويات', en: 'All Levels' },
    adm_critical:            { ar: 'حرج', en: 'Critical' },
    adm_warning:             { ar: 'تحذير', en: 'Warning' },
    adm_info_level:          { ar: 'معلومة', en: 'Info' },
    adm_fuel:                { ar: 'وقود', en: 'Fuel' },
    adm_speed_alert:         { ar: 'السرعة', en: 'Speed' },
    adm_bus_filter:          { ar: 'باص', en: 'Bus' },
    adm_vehicle_num_col:     { ar: 'رقم المركبة', en: 'Vehicle No.' },
    adm_vehicle_type_col:    { ar: 'النوع', en: 'Type' },
    adm_vehicle_status_col:  { ar: 'الحالة', en: 'Status' },
    adm_vehicle_route_col:   { ar: 'المسار', en: 'Route' },
    adm_vehicle_gps_col:     { ar: 'جهاز GPS', en: 'GPS Device' },
    adm_vehicle_name_col:    { ar: 'الاسم', en: 'Name' },
    adm_severity_col:        { ar: 'مستوى الخطورة', en: 'Severity' },
    adm_time_col:            { ar: 'الوقت', en: 'Time' },
    adm_add_driver:          { ar: '+ إضافة سائق', en: '+ Add Driver' },
    adm_manage_drivers:      { ar: 'إدارة السائقين', en: 'Manage Drivers' },
    adm_driver_id_col:       { ar: 'رقم السائق', en: 'Driver No.' },
    adm_driver_email_col:    { ar: 'البريد الإلكتروني', en: 'Email' },
    adm_driver_phone_col:    { ar: 'رقم الهاتف', en: 'Phone' },
    adm_assigned_vehicle:    { ar: 'المركبة المخصصة', en: 'Assigned Vehicle' },
    adm_analytics_title:     { ar: 'التحليلات والإحصائيات', en: 'Analytics & Statistics' },
    adm_fleet_utilization:   { ar: 'استخدام الأسطول', en: 'Fleet Utilization' },
    adm_avg_speed:           { ar: 'متوسط السرعة', en: 'Avg Speed' },
    adm_daily_trips:         { ar: 'الرحلات اليومية', en: 'Daily Trips' },
    adm_gps_points_24h:      { ar: 'نقاط GPS (24 ساعة)', en: 'GPS Points (24h)' },
    adm_fleet_util_chart:    { ar: 'استخدام الأسطول — المركبات النشطة مقابل الخاملة (24 ساعة)', en: 'Fleet Utilization — Active vs Idle Vehicles (24h)' },
    adm_no_trip_data:        { ar: 'لا بيانات رحلات في آخر 24 ساعة', en: 'No trip data in last 24 hours' },
    adm_route_perf_title:    { ar: 'أداء المسارات — نسبة الالتزام بالمواعيد ومتوسط التأخير (7 أيام)', en: 'Route Performance — On-Time Rate & Avg Delay (7 days)' },
    adm_avg_delay_col:       { ar: 'متوسط التأخير (د)', en: 'Avg Delay (min)' },
    adm_on_time_col:         { ar: 'الالتزام بالمواعيد', en: 'On Time' },
    adm_route_col:           { ar: 'المسار', en: 'Route' },
    adm_driver_scoreboard:   { ar: 'لوحة السائقين — الرحلات المكتملة والتزام المسار (30 يوماً)', en: 'Driver Scoreboard — Completed Trips & Route Adherence (30 days)' },
    adm_total_distance:      { ar: 'المسافة الكلية (كم)', en: 'Total Distance (km)' },
    adm_route_adherence:     { ar: 'الالتزام بالمسار', en: 'Route Adherence' },
    adm_driver_col:          { ar: 'السائق', en: 'Driver' },
    adm_gps_heatmap:         { ar: 'خريطة تغطية GPS — كثافة إشارة المركبات (24 ساعة)', en: 'GPS Coverage Map — Vehicle Signal Density (24h)' },
    adm_high_coverage:       { ar: 'تغطية عالية', en: 'High Coverage' },
    adm_mid_coverage:        { ar: 'تغطية متوسطة', en: 'Medium Coverage' },
    adm_low_coverage:        { ar: 'تغطية منخفضة', en: 'Low Coverage' },
    adm_no_gps_data:         { ar: 'لا بيانات GPS متاحة', en: 'No GPS data available' },
    adm_edit_vehicle:        { ar: 'تحرير المركبة', en: 'Edit Vehicle' },
    adm_vehicle_id_label:    { ar: 'رقم المركبة', en: 'Vehicle ID' },
    adm_name_ar_label:       { ar: 'الاسم (عربي)', en: 'Name (Arabic)' },
    adm_type_label:          { ar: 'النوع', en: 'Type' },
    adm_status_label:        { ar: 'الحالة', en: 'Status' },
    adm_assigned_route:      { ar: 'المسار المخصص', en: 'Assigned Route' },
    adm_no_route:            { ar: 'لا يوجد', en: 'None' },
    adm_gps_device_label:    { ar: 'رقم GPS Device', en: 'GPS Device ID' },
    adm_gps_device_ph:       { ar: 'رقم الجهاز', en: 'Device number' },
    adm_add_driver_modal:    { ar: 'إضافة سائق', en: 'Add Driver' },
    adm_full_name_label:     { ar: 'الاسم الكامل', en: 'Full Name' },
    adm_driver_name_ph:      { ar: 'اسم السائق', en: 'Driver name' },
    adm_email_label:         { ar: 'البريد الإلكتروني', en: 'Email' },
    adm_email_ph:            { ar: 'بريد إلكتروني', en: 'Email address' },
    adm_phone_label:         { ar: 'رقم الهاتف', en: 'Phone Number' },
    adm_phone_ph:            { ar: 'رقم الهاتف', en: 'Phone number' },
    adm_password_label:      { ar: 'كلمة المرور', en: 'Password' },
    adm_strong_password_ph:  { ar: 'كلمة مرور قوية', en: 'Strong password' },
    adm_assign_vehicle:      { ar: 'تعيين المركبة', en: 'Assign Vehicle' },
    adm_no_assignment:       { ar: 'بدون تعيين', en: 'No assignment' },
    adm_create_btn:          { ar: 'إنشاء', en: 'Create' },
    adm_vehicle_name_ph:     { ar: 'اسم المركبة', en: 'Vehicle name' },
    adm_unknown_route:       { ar: 'خط غير معروف', en: 'Unknown Route' },

    /* ── Passenger App ───────────────────────────────────────── */
    pax_connection_lost_bar: { ar: '🔄 انقطع الاتصال — جارٍ إعادة الاتصال بالبيانات المباشرة...', en: '🔄 Connection lost, retrying live data...' },
    pax_active_vehicle_s:    { ar: 'مركبة نشطة', en: 'active vehicle' },
    pax_next_arrival:        { ar: 'أقرب وصول', en: 'Next Arrival' },
    pax_estimated:           { ar: 'تقدير', en: 'Est.' },
    pax_push_unsupported:    { ar: 'إشعارات الدفع غير مدعومة في هذا المتصفح', en: 'Push notifications not supported in this browser.' },
    pax_enable_notif:        { ar: 'تفعيل الإشعارات', en: 'Enable Notifications' },
    pax_disable_notif:       { ar: 'إيقاف الإشعارات', en: 'Disable Notifications' },
    pax_push_failed:         { ar: 'فشل تفعيل الإشعارات', en: 'Failed to enable push notifications.' },
    pax_loading_fleet:       { ar: 'جاري تحميل بيانات الأسطول...', en: 'Loading fleet data...' },
    pax_reconnecting:        { ar: 'جاري إعادة الاتصال بالبيانات المباشرة...', en: 'Reconnecting to live data...' },
    pax_live_badge:          { ar: 'مباشر', en: 'Live' },
    pax_search_ph:           { ar: 'ابحث عن خطوط...', en: 'Search routes...' },
    pax_nearby_routes:       { ar: 'الخطوط القريبة', en: 'Nearby Routes' },
    pax_back_to_routes:      { ar: '→ العودة إلى الخطوط', en: '← Back to Routes' },
    pax_nav_map:             { ar: 'الخريطة', en: 'Map' },
    pax_nav_routes:          { ar: 'الخطوط', en: 'Routes' },
    pax_nav_stops:           { ar: 'المحطات', en: 'Stops' },
    pax_nav_alerts:          { ar: 'التنبيهات', en: 'Alerts' },
    pax_press_to_view:       { ar: 'اضغط لعرض المواعيد ←', en: 'Tap to view times →' },
    pax_unknown_route:       { ar: 'خط غير معروف', en: 'Unknown Route' },
    pax_real_gps:            { ar: 'GPS حقيقي', en: 'Real GPS' },
    pax_min_label:           { ar: 'د', en: 'min' },
    pax_routes_suffix:       { ar: 'خطوط', en: 'routes' },
    pax_stops_label:         { ar: 'محطة', en: 'stops' },
    pax_km:                  { ar: 'كم', en: 'km' },
    pax_buses_label:         { ar: 'حافلة', en: 'bus' },
    pax_buses_label_pl:      { ar: 'حافلات', en: 'buses' },
    pax_no_vehicles_on_route: { ar: 'لا مركبات على هذا الخط', en: 'No vehicles on this route' },
    pax_eta_loading:          { ar: 'جاري تحميل المواعيد...', en: 'Loading arrivals...' },
    pax_eta_no_arrivals:      { ar: 'لا حافلات متاحة حاليًا', en: 'No buses available now' },
    pax_eta_arriving_soon:    { ar: 'وصول الآن', en: 'Arriving now' },
    pax_eta_source_real:      { ar: 'GPS حقيقي', en: 'Real GPS' },
    pax_eta_source_est:       { ar: 'تقدير', en: 'Est.' },
    pax_eta_countdown_min:    { ar: 'دقيقة', en: 'min' },
    pax_eta_tap_stop:         { ar: 'اضغط على محطة لعرض مواعيد الوصول', en: 'Tap a stop to see arrival times' },

    /* ── Driver Analytics Page ───────────────────────────────── */
    da_title:                { ar: 'تحليلات أداء السائقين', en: 'Driver Performance Analytics' },
    da_subtitle:             { ar: 'مقاييس الأداء التشغيلي لكل سائق', en: 'Operational performance metrics per driver' },
    da_leaderboard:          { ar: 'قائمة السائقين', en: 'Driver Leaderboard' },
    da_trips_col:            { ar: 'الرحلات', en: 'Trips' },
    da_on_time_col:          { ar: 'الالتزام', en: 'On-Time %' },
    da_avg_speed_col:        { ar: 'متوسط السرعة', en: 'Avg Speed' },
    da_distance_col:         { ar: 'المسافة (كم)', en: 'Distance (km)' },
    da_active_hrs_col:       { ar: 'ساعات العمل', en: 'Active Hrs' },
    da_status_col:           { ar: 'الحالة', en: 'Status' },
    da_driver_col:           { ar: 'السائق', en: 'Driver' },
    da_on_time_chart:        { ar: 'أداء الالتزام بالمواعيد — أعلى 10 سائقين', en: 'On-Time Performance — Top 10 Drivers' },
    da_sparkline_title:      { ar: 'عدد الرحلات اليومية (آخر 30 يوماً)', en: 'Daily Trip Count (Last 30 Days)' },
    da_period_7d:            { ar: '7 أيام', en: '7 Days' },
    da_period_30d:           { ar: '30 يوماً', en: '30 Days' },
    da_no_data:              { ar: 'لا بيانات متاحة', en: 'No data available' },
    da_loading:              { ar: 'جاري تحميل البيانات...', en: 'Loading data...' },
    da_active_badge:         { ar: 'نشط', en: 'Active' },
    da_inactive_badge:       { ar: 'غير نشط', en: 'Inactive' },
    da_back_admin:           { ar: '← لوحة الإدارة', en: '← Admin Panel' },
    da_km_h:                 { ar: 'كم/س', en: 'km/h' },
    da_total_drivers:        { ar: 'إجمالي السائقين', en: 'Total Drivers' },
    da_active_drivers:       { ar: 'سائقون نشطون', en: 'Active Drivers' },
    da_total_trips:          { ar: 'إجمالي الرحلات', en: 'Total Trips' },
    da_fleet_avg_ontime:     { ar: 'متوسط الالتزام', en: 'Fleet On-Time Avg' },
  };

  /* ─────────────────────────────────────────────────────────────────────
   * ENGINE
   * ───────────────────────────────────────────────────────────────────── */

  let currentLang = localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG;

  /**
   * Returns translated string for `key` in current language.
   * Supports simple interpolation: t('drv_speed_warning', { speed: 70 })
   * If key not found, returns the key itself.
   */
  function t(key, vars) {
    const entry = dict[key];
    if (!entry) return key;
    let str = entry[currentLang] || entry[DEFAULT_LANG] || key;
    if (vars) {
      str = str.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : '{' + k + '}'));
    }
    return str;
  }

  /** Switch to the given language ('ar' or 'en'). */
  function setLanguage(lang) {
    if (lang !== 'ar' && lang !== 'en') return;
    currentLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    applyToDocument();
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: currentLang } }));
  }

  /** Toggle between Arabic and English. */
  function toggleLanguage() {
    setLanguage(currentLang === 'ar' ? 'en' : 'ar');
  }

  /** Returns the current language code ('ar' or 'en'). */
  function getCurrentLang() { return currentLang; }

  /**
   * Applies translations to the DOM.
   * Processes all elements with data-i18n, data-i18n-placeholder,
   * data-i18n-title attributes.
   */
  function applyToDocument() {
    const lang = currentLang;
    const isRTL = lang === 'ar';

    /* Document direction */
    document.documentElement.lang = lang;
    document.documentElement.dir = isRTL ? 'rtl' : 'ltr';

    /* Text content */
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const translated = t(key);
      if (translated !== key) el.textContent = translated;
    });

    /* Input placeholders */
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      const translated = t(key);
      if (translated !== key) el.placeholder = translated;
    });

    /* Title attributes (tooltips) */
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      const translated = t(key);
      if (translated !== key) el.title = translated;
    });

    /* Update language toggle buttons */
    document.querySelectorAll('.dt-lang-toggle').forEach(btn => {
      btn.textContent = t('lang_toggle');
    });
  }

  /**
   * Creates and returns a styled language toggle button.
   * The button is given the class `dt-lang-toggle` so applyToDocument()
   * can update its label automatically.
   */
  function createToggleButton(extraStyle) {
    const btn = document.createElement('button');
    btn.className = 'dt-lang-toggle';
    btn.textContent = t('lang_toggle');
    btn.style.cssText = [
      'background:rgba(255,255,255,0.12)',
      'color:inherit',
      'border:1px solid rgba(255,255,255,0.25)',
      'border-radius:6px',
      'padding:5px 12px',
      'font-size:12px',
      'font-weight:600',
      'cursor:pointer',
      'font-family:inherit',
      'letter-spacing:0.3px',
      'transition:background 0.2s',
      'white-space:nowrap',
      extraStyle || '',
    ].join(';');
    btn.addEventListener('mouseover', () => { btn.style.background = 'rgba(255,255,255,0.22)'; });
    btn.addEventListener('mouseout',  () => { btn.style.background = 'rgba(255,255,255,0.12)'; });
    btn.addEventListener('click', toggleLanguage);
    return btn;
  }

  /* ── Init ── */
  function init() {
    applyToDocument();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* ── Public API ── */
  global.i18n = { t, setLanguage, toggleLanguage, getCurrentLang, applyToDocument, createToggleButton };
  global.t = t; // shorthand

}(window));
