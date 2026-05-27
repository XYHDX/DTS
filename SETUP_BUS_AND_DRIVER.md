# الإعداد لمرّة واحدة — حافلة + سائق من لوحة الإدارة
# One-time setup — bus + driver from the admin dashboard

> **قبل البدء / Before you start:** Phase A migrations (`011→017`)
> must already be applied. If you've just done that, push the latest
> code: `bash "./Push to GitHub.command"`. The new "Assign to vehicle"
> dropdown in the Add-User modal needs the latest deploy.

---

## ١. أنشئ خطّاً (اختياري إذا كان موجوداً) / Create a route (optional, skip if already exists)

1. `/admin/login.html` → login as **admin** with the password from `DEMO_CREDENTIALS.md`.
2. Side nav → **الخطوط / Routes**.
3. Top-right → **+ إضافة خط / Add route**.
4. Fill in:
   - Code: `R103` (any unique 2–16 char code)
   - Name (English): `Bab Sharqi → Mezzeh`
   - Name (Arabic): `باب شرقي → المزة`
   - Type: `Bus`
   - Color: e.g. `#0E5650`
5. **Save** → the route appears in the list.

---

## ٢. أنشئ حافلة / Create a bus

1. Side nav → **الحافلات / Vehicles**.
2. Top-right → **+ إضافة مركبة / Add vehicle**.
3. Fill in:

| Field | Example | Notes |
|---|---|---|
| Plate / Fleet ID | `B-104` | 2–16 chars; must be unique |
| Name (English) | `Bus 104` | required |
| Name (Arabic) | `الحافلة ١٠٤` | optional |
| Type | `Bus` | `bus`, `microbus`, or `taxi` |
| Capacity | `60` | 1–200 |
| Assigned route | pick `R101 — Marjeh to Mezzeh` (or your new R103) | route type MUST match vehicle type |
| Status | `Idle` | the bus stays parked until a driver starts a trip |

4. **Save** → the new bus shows up in the table with status `Idle` and route `R101`.

> الـ"Status" يبقى `Idle` لأنّ المركبة بدون سائق وبدون رحلة قيد التنفيذ.
> Status stays `Idle` until a driver logs into the driver app and taps Start Trip.

---

## ٣. أنشئ حساب سائق + اربطه بالحافلة بشكل ذرّي / Create a driver and link them to the bus in one step

1. Side nav → **المستخدمون / Users**.
2. Top-right → **+ إضافة مستخدم / Add user**.
3. Fill in:

| Field | Example | Notes |
|---|---|---|
| Email | `ahmad.khalil@damascus-transit.demo` | must be unique |
| Name (English) | `Ahmad Khalil` | required |
| Name (Arabic) | `أحمد خليل` | optional |
| **Role** | `DRIVER` | **must be `driver` for the vehicle link to apply** |
| Phone | `+963900123456` | optional |
| **Assign to vehicle (drivers only)** | pick **`B-104`** from the dropdown | only unassigned vehicles appear here |
| Initial password | `Driver-Ahmad-2026` | ≥ 10 chars; the driver is forced to rotate it on first login |

4. **Save**. Two API calls happen automatically:
   1. `POST /api/admin/users` creates the driver row.
   2. `PATCH /api/admin/vehicles/<B-104-id>` sets `assigned_driver_id` to the new driver.
5. Refresh `/admin/vehicles.html` — `B-104` now shows the driver column populated.

> إن لم تظهر المركبة في القائمة المنسدلة، فهي إمّا مرتبطة بسائق آخر أو
> مُعطَّلة (`is_active=false`). أوقف الربط القديم أو فعّل المركبة أولاً.
>
> If the vehicle doesn't show up in the dropdown, it's either already
> bound to another driver or marked inactive. Unbind the previous
> driver or reactivate the vehicle first.

---

## ٤. اختبر الدورة الكاملة / End-to-end test

1. Open an incognito window → `https://dts-brown.vercel.app/driver/`.
2. Login with the new driver email + initial password.
3. **First login forces a password rotation** — set a new password ≥ 10 chars.
4. After rotation, the driver app should now show:
   - Top bar: bus code (`B-104`) and route name (`R101 — Marjeh to Mezzeh`).
   - Big **▶ بدء الرحلة / Start Trip** button.
5. Tap Start Trip → the bus's status flips from `Idle` to `Active` in `/admin/vehicles.html` within ~5 seconds.
6. Allow GPS in the browser → vehicle position starts updating on the admin live map and the passenger app.

---

## ٥. ماذا لو أردت تغيير المركبة المعيّنة للسائق لاحقاً / Reassigning later

There's no "edit user" form yet (the next wave will add one), but two
shortcuts work today:

- **Move a driver to a different bus.** Go to `/admin/vehicles.html`,
  click the row of the OLD bus, change its `assigned_driver_id` to
  `null` via the Add modal's edit mode (or PATCH it directly), then
  add the new driver to the NEW bus via the same Add-user flow.
- **Take a bus offline.** Go to `/admin/vehicles.html`, click **Delete**
  on the row. Wave-6 6.2-C now cancels any in-progress trip on that
  vehicle so the driver app doesn't get stuck.

---

## ٦. سرعة التحقّق / Quick sanity check

After all the steps:

```bash
HOST=https://dts-brown.vercel.app
TOKEN="..."  # your admin JWT, full-scope

curl -s -H "Authorization: Bearer $TOKEN" "$HOST/api/admin/vehicles" \
  | python3 -m json.tool | grep -E '"vehicle_id"|"assigned_driver_id"' | head -20
```

You should see `B-104` with a non-null `assigned_driver_id`.
