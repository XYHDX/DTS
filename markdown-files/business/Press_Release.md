# PRESS RELEASE

**FOR IMMEDIATE RELEASE**

---

## Damascus Transit Technologies Launches Syria's First Real-Time Public Transit Platform

*Open-source GPS fleet management system targets 6,000+ vehicles and 2.5 million daily commuters in Damascus; company eyes $50M World Bank Syria transport allocation*

---

**DAMASCUS, SYRIA — April 2026** — Damascus Transit Technologies Ltd. today announced the launch of the DAM Platform, Syria's first real-time GPS-based public transport management system. The platform enables operators, government authorities, and passengers to track Damascus's fleet of over 6,000 buses and microbuses in real time — for the first time in the country's history.

The announcement comes as Syria enters a new era of international engagement following the lifting of major US and EU sanctions in 2025, and as the World Bank deploys $50 million earmarked for Syria's transport infrastructure.

---

### A City-Scale Problem, A Scalable Solution

Damascus is home to more than 2.5 million daily transit commuters navigating a network of 6,000+ vehicles operated by over 200 private companies. Until now, every one of those vehicles has been managed entirely on paper — no GPS, no digital dispatch, no passenger information. The average wait time at a bus stop in Damascus is **45 minutes**.

The DAM Platform addresses this gap with a comprehensive technology stack:

- **Real-time fleet tracking** — GPS positions updated every 5 seconds across all enrolled vehicles
- **Passenger mobile app** — live arrival times accessible via any mobile browser, in Arabic and English, with no app download required
- **Operator dashboard** — a web-based portal for fleet managers to monitor vehicles, assign drivers, and track route performance
- **Government analytics** — a Ministry-grade analytics layer providing ridership estimates, on-time performance data, demand heatmaps, and GTFS-compatible feeds for integration with Google Maps and Apple Maps

"Damascus has 2.5 million people who depend on public transit every day and have been doing so with zero digital infrastructure," said the company's founding team. "The platform we've built doesn't require expensive servers, complex integrations, or years of deployment. It works with the GPS hardware that already exists, on the 4G networks that already cover Damascus, and it runs at near-zero operating cost."

---

### Open-Source by Design

The DAM Platform is published under the MIT open-source license and available at github.com/actuatorsos/SyrianTransitSystem. The company made this decision deliberately: any Syrian city — including Aleppo, Homs, and Lattakia — can deploy the same platform at zero licensing cost.

The platform is built on widely adopted open-source components: Python and FastAPI for the backend, PostgreSQL with PostGIS for spatial data, Traccar for GPS device integration, and React for the passenger-facing progressive web app. The entire system runs on free-tier cloud infrastructure, making it financially accessible for even the smallest operators.

---

### Government and International Partnerships

Damascus Transit Technologies is in active discussions with the Syrian Ministry of Transport and the Damascus Governorate for a framework partnership that would provide the government with exclusive analytics access and route data in exchange for official recognition and route licensing.

The company has also applied for initial funding under the World Bank's Syria Transport Infrastructure allocation, which designates $50 million for modernizing Syria's transport network as part of post-sanctions reconstruction investment.

"The timing of this platform aligns exactly with Syria's reconstruction moment," the company noted. "International donors have committed to Syria's infrastructure. The Ministry has a mandate to modernize. The technology is ready. The only thing missing was the platform — and now it exists."

---

### About the Platform: Technical Highlights

The DAM Platform's production MVP includes 26 API endpoints covering authentication, route management, vehicle tracking, driver management, administrative functions, analytics, and IoT device integration. The system supports real-time data via Server-Sent Events (SSE), hardware GPS devices via Traccar webhooks, and a GTFS feed ready for submission to Google Maps and Apple Maps.

An enterprise-grade version of the platform — featuring a Next.js dashboard, 58 endpoints, TimescaleDB for time-series data, and AWS infrastructure — is available for large-scale government deployments.

---

### Availability and Pricing

The DAM Platform is available for operator pilot enrollment immediately. Pricing is structured as follows:

- **Starter** (up to 50 vehicles): $500/month
- **Professional** (up to 200 vehicles): $1,500/month
- **Enterprise** (unlimited): $5,000+/month, custom government contracts available

Hardware installation cost is approximately $30 per vehicle for a GPS tracker plus $2–5/month per vehicle for SIM data. No server infrastructure is required on the operator's side.

---

### About Damascus Transit Technologies

Damascus Transit Technologies Ltd. is a Damascus-based technology company building open-source public transit infrastructure for Syria. The company's mission is to modernize Damascus public transport through technology — improving reliability, safety, and passenger experience — and to make that technology freely available to every Syrian city.

**Website:** damascustransit.com
**GitHub:** github.com/actuatorsos/SyrianTransitSystem
**Press contact:** press@damascustransit.com
**Government inquiries:** ministry@damascustransit.com
**Investor/donor inquiries:** grants@damascustransit.com

---

### Media Assets

High-resolution logos, platform screenshots, and brand assets are available on request from press@damascustransit.com.

---

*— END OF PRESS RELEASE —*

---

**Distribution targets:**

| Outlet | Category | Notes |
|--------|----------|-------|
| Syria Report | Syrian business/economy press | Primary target |
| Wamda | MENA startup media | Key regional tech outlet |
| Arab News (tech section) | Pan-Arab press | Mass audience |
| TechCrunch (MENA correspondent) | International tech | High-impact if picked up |
| Devex | International development press | Donor/NGO audience |
| Thomson Reuters Foundation | Development journalism | World Bank angle |
| Al-Monitor (Syria desk) | Policy/reconstruction | Government partnership angle |
| UNDP Syria communications | Donor stakeholder | Direct relationship |
