# Launch announcement — v1.0.0

> Draft. Customise the channel-specific copy before shipping. Numbers are placeholders — replace with the figures from the first pilot week.

## Blog post (long form, ~600 words)

### نقل دمشق: تطبيق الحافلات الذكي مفتوح المصدر — الآن متاح

> *Damascus Transit, our open-source smart-bus app, is now public.*

دمشق مدينة تتحرّك. بين الفجر وآذان المغرب، حافلات النقل العام تنقل آلاف الركاب عبر شوارع المزة، الميدان، باب توما، والصالحية. اليوم، نطلق **نقل دمشق** — تطبيقاً مجانياً ومفتوح المصدر يتيح للركاب رؤية الحافلات في الوقت الحقيقي، وللسائقين أدوات تحترم وقتهم.

**ما الذي يفعله التطبيق؟**

للركاب: خريطة لحظية تعرض مواقع الحافلات (تُحدَّث كل خمس ثوانٍ)، حساب وقت الوصول لكل محطة، بحث بالعربية أو الإنكليزية عن أي خط، وعمل بدون اتصال — الخطوط والمحطات محفوظة على هاتفك.

للسائقين: زرّ بدء الرحلة، عدّاد ركّاب بسيط، مشاركة الموقع التلقائية، ودخول آمن ببصمة الإصبع. في نهاية كل وردية، ملخّص يبيّن المسافة، المدة، وعدد الركاب — لأن يومك يستحق التقدير.

للموزّعين والإدارة: لوحة تحكّم بالأسطول، تحليلات أسبوعية لأداء الخطوط، وإدارة الحسابات والصلاحيات.

**لماذا مفتوح المصدر؟**

لأن البنية التحتية للمدينة يجب أن تكون شفافة. الكود كله متاح على GitHub تحت رخصة MIT. أي شخص يستطيع قراءته، تدقيقه، نسخه، أو تحسينه. لا نبيع بياناتك. لا نعرض إعلانات. لا ندّعي ملكية موقعك.

**ماذا يوجد في v1.0؟**

- ٨ خطوط رئيسية تغطي محاور المدينة، مع ٥٤ محطة محسومة من بيانات حقيقية.
- ١٨ سائقاً في الأسطول التجريبي، ٢٤ حافلة، ومتوسط إشغال ٤٥٪.
- ٢٦ نقطة نهاية API موثَّقة، تدفّق SSE حيّ، مع زمن استجابة وسيط ٢٥ ميلي ثانية.
- اختبارات تلقائية بـ ٣٠٧ حالة، تشغّل في كل مرّة نضيف فيها شيفرة جديدة.
- مراجعة أمنية كاملة، مع كل المخاطر العالية والمتوسّطة مُغلقة.

**ما الذي ينقصنا؟**

كل شيء له ميلة أولى. نحتاج ركّاباً يجرّبون التطبيق ويخبروننا حين يتعطّل. نحتاج مساهمين يقرأون الكود ويرسلون pull requests. نحتاج خطوطاً جديدة لإضافتها، وتحسينات لطلبها. شارك معنا على GitHub، أو راسلنا على `support@damascustransit.sy`.

**كيف نواصل؟**

نسعى لإطلاق نسخة Flutter كاملة كـ v2.0 خلال الأشهر الستّة القادمة لمنح السائقين تجربة أصلية أنعم على الهواتف الضعيفة، خاصة مشاركة الموقع في الخلفية على iOS. حتى ذلك الحين، يكفي ما لدينا لخدمة المدينة بصدق.

شكراً لكل من حمل الفكرة، كتب سطراً من الكود، أو ركب الحافلة ليتأكّد أنّ المحطّة دقيقة. هذا التطبيق لكم.

— فريق نقل دمشق

---

### Damascus Transit — our open-source smart-bus app is now public (English)

Damascus moves. Between dawn and the call to maghrib, public buses carry thousands of riders through Mezzeh, Al-Midan, Bab Touma, and Al-Salihiyya. Today we're launching **Damascus Transit** — a free, open-source companion app that gives passengers real-time bus locations and gives drivers tools that respect their time.

**What it does**

Passengers see a live map that refreshes every five seconds, get accurate ETAs for every stop, search routes in Arabic or English, and continue using the app without internet. Drivers get a one-tap trip start, a comfortable passenger counter, automatic background GPS, biometric sign-in, and an end-of-shift summary. Dispatchers get a fleet dashboard and weekly route-performance analytics.

**Why open source**

Because city infrastructure should be transparent. The whole codebase is on GitHub under the MIT licence. Anyone can read, audit, fork, or improve it. We don't sell your data. We don't show ads. We don't own your location.

**What's in v1.0**

Eight routes, 54 stops, 18 drivers, 24 vehicles, 26 documented API endpoints, an SSE stream with a 25 ms median response latency, 307 automated tests, and a clean security audit with all HIGH + MEDIUM findings closed.

**What's next**

A Flutter v2.0 within six months for smoother native performance on low-end phones — particularly for the driver background-GPS path on iOS. Until then, v1.0 is enough to serve the city honestly.

Thank you to everyone who carried the idea, wrote a line of code, or rode the bus to verify a stop. This app is yours.

— The Damascus Transit team

---

## Twitter / X thread

1/ نقل دمشق متاح اليوم. تطبيق حافلات لحظي للمدينة، مفتوح المصدر، بدون إعلانات. 🚌 https://damascustransit.sy
2/ للركاب: خريطة حيّة، أوقات وصول دقيقة، يعمل دون إنترنت. للسائقين: عدّاد ركّاب، GPS تلقائي، بصمة. للإدارة: لوحات تحليلات. 📊
3/ كل الكود على GitHub تحت رخصة MIT. لا نبيع بياناتك. لا إعلانات. لا ادّعاءات. 🔓
4/ في النسخة الأولى: ٨ خطوط، ٥٤ محطة، ١٨ سائقاً، ٢٤ حافلة، ٣٠٧ اختبارات تلقائية، صفر ثغرات أمنية حرجة. 🧪
5/ ما يحتاج التطبيق: ركّاب يجرّبونه ومساهمون يساعدوننا. PR + Issue welcome 🙏 — https://github.com/actuatorsos/SyrianTransitSystem
6/ شكراً لمن حمل الفكرة، كتب الكود، أو ركب الحافلة ليتحقّق من دقّة محطّة. هذا التطبيق لكم. ❤️

## LinkedIn post (shorter, professional)

After a quiet build period, we're shipping v1.0.0 of **Damascus Transit** — an open-source platform for real-time public-bus tracking in Damascus, Syria.

The stack: FastAPI + Supabase + PostGIS for the backend; a Claude-designed warm-cream UI built with vanilla HTML/CSS/JS for the web; a parallel Flutter scaffold prepared as the v2.0 candidate; Capacitor wrapping the PWAs for the v1.0 Android + iOS launch.

The numbers from week one of the pilot: 8 routes, 54 stops, 24 vehicles, 307 automated tests passing, eight CI workflows green, two HIGH and three MEDIUM security findings closed.

MIT-licensed. No ads. No data sale. We'd love collaborators — particularly anyone with experience in transit operations, RTL design, or background-GPS reliability on iOS. Star us, send a PR, or just ride a bus and tell us if a stop is wrong.

GitHub: <https://github.com/actuatorsos/SyrianTransitSystem>

## WhatsApp broadcast (Arabic, 1 message)

🚌 *نقل دمشق* أصبح متاحاً!
تطبيق مجاني لتتبّع الحافلات لحظياً، يعمل دون إنترنت، بدون إعلانات.
حمّله من Play Store الآن: https://damascustransit.sy
كل الكود مفتوح المصدر · شكراً لكل من ساهم 💚

## Press contact

`press@damascustransit.sy` — pre-write a 5-bullet FAQ in both languages and link from the GitHub repo. The most likely questions:

1. هل ستجمعون بيانات الركّاب؟ (No identifying data is collected.)
2. هل سيتوفّر تطبيق iOS؟ (Yes, via TestFlight first, then App Store when Apple Developer enrolment clears.)
3. كيف يستفيد السائقون؟ (Tools that respect their time + on-time analytics.)
4. هل يمكنني المساهمة؟ (Yes — `CONTRIBUTING.md` walks through it.)
5. هل سيكون التطبيق في مدن أخرى؟ (Open-source — anyone can fork. We're focused on Damascus first.)
