# دليل الاستخدام — Damascus Transit Instructions

Everything needed to **run** the system, organised by who you are.
كل ما تحتاجه لتشغيل النظام، مرتباً حسب دورك.

| Guide | Who it's for | What's inside |
|---|---|---|
| **[ADMIN_GUIDE.md](ADMIN_GUIDE.md)** | the transit-authority **admin** (المدير) | approving vehicles, managing users/routes, alerts, payments ledger, audit log |
| **[OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)** | the **operator** company staff (المشغّل — dispatcher) | registering vehicles, creating driver usernames+passwords, linking driver↔vehicle↔route, getting approved |
| **[DRIVER_GUIDE.md](DRIVER_GUIDE.md)** | the **driver** (السائق) | first login, password rotation, starting/ending trips, the Sham Cash QR, reporting incidents |
| **[HARDWARE_SETUP.md](HARDWARE_SETUP.md)** | whoever builds/installs the **GPS units** | the exact data contract, HTTP bridge vs MQTT, broker topics, Grafana/monitoring, firmware references |
| **[GPS_TO_APP_ROADMAP.md](GPS_TO_APP_ROADMAP.md)** | **you** — end-to-end | the complete path: unbox a GPS unit → vehicle approved → live on the iOS & Android app |

## The 4 roles in 30 seconds — الأدوار الأربعة

```
super_admin  →  platform owner (across all operators)
admin        →  transit authority: APPROVES vehicles, manages everything   المدير: يعتمد المركبات
dispatcher   →  operator company: registers vehicles + driver accounts     المشغّل: يسجّل ويجهّز
driver       →  drives, streams GPS, shows the payment QR                  السائق
```

**The golden rule / القاعدة الذهبية:** an operator can prepare everything, but
**no vehicle carries passengers before an admin clicks Approve** on
`/admin/approvals.html`. لا تعمل أي مركبة قبل موافقة الإدارة.

## Where things live

| Surface | URL |
|---|---|
| Public live map | `/` |
| Passenger PWA | `/passenger/` |
| Driver console | `/driver/` |
| Staff login | `/admin/login.html` |
| Admin dashboard | `/admin/` (9 pages, sidebar adapts to your role) |
| Mobile app (iOS + Android) | `flutter_app/` — see [GPS_TO_APP_ROADMAP.md](GPS_TO_APP_ROADMAP.md) §7 |

Technical background (why the system is built this way):
[`docs/ARCHITECTURE_DECISIONS.md`](../docs/ARCHITECTURE_DECISIONS.md).
Deployment: [`docs/DEPLOY.md`](../docs/DEPLOY.md) ·
Database migrations: [`docs/APPLY_MIGRATIONS.md`](../docs/APPLY_MIGRATIONS.md).
