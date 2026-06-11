# دليل المدير — Admin Guide

You are the transit authority. Operators prepare vehicles and drivers; **you decide
what operates**. Everything you do is recorded in the audit log.

أنت سلطة النقل: المشغّلون يجهّزون المركبات والسائقين، **وأنت من يقرر ما يعمل على الشبكة**.

---

## 1. Logging in — تسجيل الدخول

1. Open `/admin/login.html` and sign in with your admin email + password.
2. First time? Your account was created with a temporary password — you'll be
   forced to set a new one (8+ characters).
3. You land on **النظرة العامة / Overview**: live map, KPIs (active vehicles,
   trips today, occupancy, open alerts), and — when something is waiting for
   you — a **gold "بانتظار الموافقة / Pending approval" card**. Click it.

> Lost password? `/admin/reset.html` → enter your email → follow the link
> (valid 30 minutes).

## 2. Approving vehicles — اعتماد المركبات (your most important job)

Sidebar → **الموافقات / Approvals** (admins only; a live badge shows the pending count).

Each pending card shows: vehicle code + type (حافلة/ميكروباص/تكسي), the **driver
the operator assigned** (name + email), capacity, and registration date.

| Button | When | Effect |
|---|---|---|
| **اعتماد / Approve** | the vehicle is legitimate, driver assigned, GPS installed | it can start trips, stream GPS, and collect Sham Cash fares **immediately** |
| **رفض / Reject** (asks for a reason) | papers/hardware not right | blocked; the operator sees your reason and can fix + resubmit |
| **تعليق / Suspend** (on approved vehicles) | violations, expired licence, investigation | operations stop within ~60 seconds: trips blocked, GPS frames dropped, QR payments refused |
| **إعادة للانتظار / Resubmit** | a rejected/suspended vehicle fixed its issue | back to the pending queue |

**Checklist before approving — قائمة ما قبل الاعتماد:**

- [ ] The vehicle has an assigned driver (no driver = nothing to approve yet).
- [ ] The fleet code matches the physical plate.
- [ ] A GPS device ID is set if it carries your hardware (Vehicles page shows it).
- [ ] The operator is the one you expect — you only ever see your own operator's queue.

## 3. Users — المستخدمون

Sidebar → **المستخدمون**. You can create any role except super_admin:

* **dispatcher (مشغّل)** — operator company staff. They can register vehicles and
  create *driver* accounts only.
* **driver (سائق)** — usually the operator creates these, but you can too.
* **admin** — a colleague with the same powers as you. Create sparingly.

Every account you create gets a temporary password that **must be rotated on the
person's first login**. Disable any account instantly with **تعطيل / Disable** —
their session dies within 5 seconds.

## 4. Routes — الخطوط

Sidebar → **الخطوط**. Create/edit route code, Arabic/English names, type
(bus/microbus/taxi), distance, duration, and **الأجرة / fare (SYP)**.

> The fare matters: passengers paying by QR on a fixed-fare route **cannot pay a
> different amount** — the server enforces the fare you set here. Taxis (no fixed
> fare) accept the metered amount.

Route *geometry* (the line on the map) comes from the GTFS pipeline, not this page.

## 5. Alerts — التنبيهات

Sidebar → **التنبيهات**: speeding, route deviation, breakdowns, **driver SOS
(بلاغ سائق)** — drivers' incident reports land here as critical alerts with their
GPS position. Resolve (حلّ) when handled; reopen if needed. The Overview page
shows the 5 most recent unresolved ones.

## 6. Payments ledger — المدفوعات

Sidebar → **المدفوعات**: every Sham Cash QR transaction — vehicle, amount,
status (قيد الانتظار / مؤكدة / فاشلة), timestamp.

* **SBX badge** = sandbox (test) payment — no real money. While the system runs in
  sandbox you can simulate the Sham Cash confirmation with **تأكيد تجريبي**.
* Going live needs merchant credentials — see `docs/ARCHITECTURE_DECISIONS.md` §10.

## 7. Audit log — سجل التدقيق

Sidebar → **سجل التدقيق** (admins only): who approved/rejected/suspended which
vehicle and why, who created users and routes, who assigned drivers — newest first.
This is your accountability trail; it cannot be edited from the UI.

## 8. Analytics — التحليلات

Sidebar → **التحليلات**: trips per day, occupancy distribution, per-route
performance (trip counts, on-time %, average delay) over 24h/7d/30d.
Engineering health (latency, error rates, ingest rate) lives in **Grafana**
instead — see `instructions/HARDWARE_SETUP.md` §3.

## Emergency cheatsheet — ورقة الطوارئ

| Situation | Do this |
|---|---|
| Vehicle must stop operating NOW | Approvals → its card → **تعليق / Suspend** (takes effect ≤ 60 s) |
| Driver compromised / fired | Users → **تعطيل / Disable** (session dies ≤ 5 s) |
| Wrong fare being charged | Routes → edit the route's fare |
| Passengers report a fake QR sticker | impossible to exploit (signatures), but Suspend the vehicle and inspect |
| "Is the system itself healthy?" | Grafana dashboard / `/api/health/deep` |
