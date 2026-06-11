# دليل المشغّل — Operator (Dispatcher) Guide

You run a transport company (or depot) under the transit authority. You **prepare**
everything — vehicles, drivers, assignments — and the **admin approves** each
vehicle before it may operate.

أنت تجهّز كل شيء، والإدارة تعتمد. مركبتك لا تعمل قبل الموافقة.

Your account role is `dispatcher`. The admin sidebar shows you: Overview,
Vehicles, Users, Routes, Alerts, Payments, Analytics, Help — but **not**
Approvals or the Audit log (admin-only).

---

## The complete onboarding flow — التسلسل الكامل

```
1. سجّل المركبة          Register the vehicle            (you)
2. أنشئ حساب السائق      Create the driver's username     (you)
3. اربط السائق والخط     Link driver + route to vehicle   (you)
4. انتظر الاعتماد        Admin approves                   (admin)
5. السائق يبدأ العمل      Driver logs in and starts        (driver)
```

## Step 1 — Register a vehicle / تسجيل مركبة

`/admin/vehicles.html` → **+ إضافة مركبة**

| Field | Example | Notes |
|---|---|---|
| رقم اللوحة / Fleet code | `B-104` | unique within your fleet |
| Name (EN / AR) | `Bus 104` / `الحافلة ١٠٤` | both required |
| النوع / Type | `حافلة` (bus / microbus / taxi) | must match the route type you'll assign |
| السعة / Capacity | `60` | 1–200 |
| معرّف جهاز GPS | `DTS-GPS-0042` | the ID printed on the tracking unit installed in the vehicle — see [HARDWARE_SETUP.md](HARDWARE_SETUP.md) |

On save the vehicle appears with the badge **قيد الانتظار / Pending** — that's
normal. It cannot operate yet.

## Step 2 — Create the driver's account / إنشاء حساب السائق

`/admin/users.html` → **+ إضافة مستخدم**

As an operator you can only create **driver** accounts (that's by design).

* **Email = the username** the driver types into the app (e.g.
  `ahmad.khalil@yourcompany.sy`).
* **Initial password (كلمة المرور الأولى):** at least 8 characters. Hand it to
  the driver in person or by a channel you trust — **they are forced to change it
  on first login**, so it's a one-trip secret.
* **ربط بمركبة / Link to vehicle:** pick the vehicle from Step 1 right in the same
  form (only driver-less vehicles appear). This saves a separate trip to the
  Vehicles page.

## Step 3 — Assign route (and driver, if you skipped the link) / تعيين الخط

`/admin/vehicles.html` → the vehicle's row → **تعيين / Assign** → choose the
driver and/or the route. Rules the server enforces:

* The driver must be an **active driver account in your company**.
* You can link the driver first and the route later, or both at once.
* Need a new route? `/admin/routes.html` → **+ إضافة خط** (code, names, type,
  fare). The vehicle type must match the route type.

## Step 4 — Approval / الاعتماد

The admin sees your vehicle in their Approvals queue with the driver you assigned.

* **Approved (معتمدة):** the badge turns green — the vehicle can work. Tell the driver.
* **Rejected (مرفوضة):** open the vehicle on `/admin/approvals.html`… you can't —
  that page is admin-only. You'll see the state + the rejection reason on your
  **Vehicles** page badge and note. Fix the issue and ask the admin to resubmit,
  or re-register correctly.
* While pending: the driver can log in but the app shows
  **"مركبتك بانتظار اعتماد الإدارة"** and trip start stays locked.

## Step 5 — Verify it's alive / تحقق

1. Driver logs in at `/driver/` → rotates password → sees the vehicle code +
   route name in the header.
2. Driver taps **▶ بدء الرحلة** — within ~5 seconds the vehicle flips to
   نشطة/Active on your Vehicles page and moves on the Overview map.
3. If the vehicle carries your GPS hardware, it shows on the map even between
   trips — positions come from the device, not the phone.

## Day-to-day operations — التشغيل اليومي

| Task | Where |
|---|---|
| Take a vehicle out of service for maintenance | Vehicles → row → تعديل status to `صيانة` |
| Retire a vehicle permanently | admin does it (Retire button is admin-only); history is kept |
| Driver left the company | tell the admin to **Disable** the account (instant), then Assign a new driver to the vehicle |
| Check fare collections | **المدفوعات / Payments** — your company's QR transactions |
| Watch occupancy / delays | **التحليلات / Analytics** |
| A driver pressed SOS | it appears in **التنبيهات / Alerts** as critical, with GPS position |

## What you can NOT do — حدودك (by design)

* Approve, reject, or suspend vehicles — only the admin.
* Create dispatcher/admin/viewer accounts — only drivers.
* See or touch any other operator's vehicles, drivers, or payments.
* Read the audit log.

These limits are what makes the approval meaningful: provisioning and
authorisation are two different people.
