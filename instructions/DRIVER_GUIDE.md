# دليل السائق — Driver Guide

سهل ومباشر: تسجّل دخولك، تبدأ الرحلة، والباقي تلقائي.
Simple: log in, start your trip — the rest is automatic.

You can use **the web console** (`/driver/` in any phone browser — installable as
an app from the browser menu) or **the mobile app** (iOS/Android, same login).

---

## 1. First login — أول تسجيل دخول

1. Your company gave you an **email + temporary password** (بريدك + كلمة مرور مؤقتة).
2. Open `/driver/` → enter them.
3. You will be **forced to set a new password** (8+ characters). The temporary
   one stops working — keep the new one to yourself. لا تشارك كلمة مرورك مع أحد.

## 2. Your screen — شاشتك

After login the header shows **your vehicle code** (e.g. `B-104`) and **your
route** (e.g. المرجة → المزة). If it shows:

* **"بانتظار تخصيص الخط"** — your company hasn't assigned a route yet. Call dispatch.
* **⏳ "مركبتك بانتظار اعتماد الإدارة"** (yellow banner) — the authority hasn't
  approved the vehicle yet. You cannot start trips until the banner disappears.
  This is normal for a new vehicle; it's not about you.

## 3. Driving — العمل

| Action | How |
|---|---|
| **بدء الرحلة / Start trip** | tap ▶ — allow GPS when the browser/app asks. Your position now updates the live map every few seconds |
| **عدّاد الركاب / Passenger counter** | tap **+** when passengers board, **−** when they leave — this feeds the occupancy shown to waiting passengers |
| **إنهاء الرحلة / End trip** | tap ■ at the terminus — the trip is recorded with duration, distance and passenger count |
| **🚨 الإبلاغ عن حادث / SOS** | one tap sends a **critical alert with your GPS position** straight to the operations room |

> GPS dropped in a tunnel or dead zone? Keep driving — the app reconnects and
> resumes automatically. If your vehicle has a hardware GPS unit, tracking
> continues even without your phone.

## 4. Getting paid — Sham Cash QR / الدفع بشام كاش

Once your vehicle is **approved**, the app shows your vehicle's payment QR
(**ادفع بمسح الرمز — شام كاش**) with the route fare under it.

* Passenger scans → pays the fare in their Sham Cash wallet → you see the fare
  amount on screen. The amount on fixed-fare routes **cannot be changed** by the
  passenger — the system enforces it.
* The QR is cryptographically tied to *your* vehicle — a sticker from another
  vehicle simply won't validate, so nobody can steal your fares with a fake code.
* **وضع التجربة (SBX):** while the yellow "test mode" tag is visible, payments
  are simulations — no real money moves yet.

## 5. If something goes wrong — حلول سريعة

| Problem | Fix |
|---|---|
| "بيانات الدخول غير صحيحة" | retype the email exactly as given; passwords are case-sensitive. Still stuck? `/admin/reset.html` → "نسيت كلمة المرور" |
| Yellow approval banner won't go away | your company must get the vehicle approved — call dispatch, not IT |
| **▶ بدء الرحلة** says no route assigned | dispatch must assign a route to your vehicle |
| Map doesn't see me | phone Settings → allow Location for the browser/app, turn GPS on |
| "تعذر بدء الرحلة" | no internet — move a few meters, retry; the app queues what it can |
| Logged out suddenly | your password was changed or the account was disabled — contact dispatch |
