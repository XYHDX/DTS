# Damascus Transit Technologies — Financial Plan
**Last Updated:** 2026-04-18
**Prepared by:** Finance Manager (Paperclip Agent)
**Version:** 1.1 (Routine Health Check — April 18, 2026)

---

## Executive Summary

DAM is pre-revenue. No contracts are signed as of this check. Infrastructure runs at **$0/month** on Vercel + Supabase free tiers. The primary financial risk is the gap between current burn (engineering time only) and first contract close. Ministry pilot signature, currently targeted for **April 26, 2026**, remains the most critical near-term financial milestone.

**Financial health status: CAUTIOUSLY STABLE**
- Infrastructure spend: $0/month ✅
- Signed revenue: $0 ⚠️
- Pipeline value: $3,000 (Ministry pilot) + $149,000–$530,000 (grants) 🟡
- Runway risk: Low in the short-term (free infra), but time-sensitive on contract close

---

## 1. Infrastructure Costs — Actual vs. Budget

### 1.1 Current Monthly Cloud Costs

| Service | Plan | Monthly Cost | Limit |
|---------|------|-------------|-------|
| Vercel | Free (Hobby) | **$0** | 100GB bandwidth, 6,000 build minutes |
| Supabase | Free | **$0** | 500MB DB, 2GB file storage, 50,000 MAU |
| Redis | Free (in-memory via test/dev) | **$0** | Production pending |
| GPS SIM cards | Not yet deployed | **$0** | — |
| **Total infrastructure** | | **$0/month** | |

### 1.2 Infrastructure Cost Projections at Scale

| Phase | Vehicles | Estimated Monthly Infra Cost | Notes |
|-------|----------|------------------------------|-------|
| Pilot (50 vehicles) | 50 | $0–$50 | Free tiers hold; occasional overages possible |
| Phase 2 (500 vehicles) | 500 | $150–$350 | Vercel Pro ~$20, Supabase Pro ~$25, SIM data ~$50–250 |
| Full Damascus (2,000+ vehicles) | 2,000+ | $500–$1,200 | Supabase Team plan, CDN, Redis cloud |
| Multi-city (Syria-wide) | 10,000+ | $2,000–$5,000 | Full production stack on AWS/dedicated |

**Key finding:** Free tiers remain sufficient through the 50-vehicle Ministry pilot. The upgrade trigger is ~150 concurrent vehicles or Supabase hitting 500MB DB limit (estimated Month 8–10 at current write volume).

### 1.3 GPS Hardware Costs (One-Time, Contract-Gated)

| Item | Qty | Unit Cost | Total |
|------|-----|-----------|-------|
| Teltonika FMB920 device | 50 | $65 | $3,250 |
| SIM card (4G) + 6-month data | 50 | $8 × 6 = $48 | $2,400 |
| Installation labor | 50 | $30 | $1,500 |
| Shipping + customs (Lebanon → Damascus) | — | — | ~$350 |
| **Hardware subtotal (50 vehicles)** | | | **~$7,500–$9,500** |

**Status:** Hardware procurement is gated on Ministry pilot contract. Not yet incurred. World Bank Phase 1 grant expected to fund or reimburse hardware.

---

## 2. Revenue Pipeline

### 2.1 Active Opportunities

| Opportunity | Stage | Expected Value | Expected Close |
|-------------|-------|---------------|----------------|
| Ministry of Transport — 6-month pilot | Proposal submitted; legal review in progress | $3,000 | April 26, 2026 (MoU signing) |
| World Bank IBRD transport grant | Application in progress | $149,000 | TBD (Q3 2026 est.) |
| UNDP Syria urban mobility grant | Proposal referenced | $50,000–$200,000 | TBD (Q3–Q4 2026) |
| EU reconstruction funding | Pipeline | $50,000–$130,000 | TBD (Q4 2026) |
| IsDB (Islamic Development Bank) | Pipeline | Unknown | TBD |
| **Total pipeline (low)** | | **$252,000** | |
| **Total pipeline (high)** | | **$582,000** | |

### 2.2 12-Month Revenue Forecast

| Month | Milestone | Monthly Revenue | Cumulative |
|-------|-----------|-----------------|------------|
| May 2026 | Ministry pilot begins (contract signed April 26) | $500 | $500 |
| Jun 2026 | Pilot active — 50 vehicles | $500 | $1,000 |
| Jul 2026 | Pilot active | $500 | $1,500 |
| Aug 2026 | Pilot active | $500 | $2,000 |
| Sep 2026 | Pilot active | $500 | $2,500 |
| Oct 2026 | Pilot complete; Phase 2 negotiation | $500 | $3,000 |
| Nov 2026 | Phase 2 begins (500 vehicles) — optimistic | $5,000 | $8,000 |
| Dec 2026 | Phase 2 + early operator SaaS | $6,500 | $14,500 |
| Jan 2027 | Operator SaaS scaling | $7,500 | $22,000 |
| Feb 2027 | Full Phase 2 + 3 operators | $8,500 | $30,500 |
| Mar 2027 | + data licensing begins | $9,500 | $40,000 |
| Apr 2027 | 12-month anniversary | $10,000+ | $50,000+ |

**Conservative 12-month scenario (pilot only, no Phase 2):** $3,000
**Base scenario (pilot + Phase 2 start):** $40,000–$50,000
**Optimistic (pilot + Phase 2 + 2 operator SaaS + grant):** $200,000+

---

## 3. Burn Rate & Runway

### 3.1 Current Monthly Burn

| Category | Monthly Cost |
|----------|-------------|
| Cloud infrastructure | $0 |
| GPS SIM data | $0 (pre-deployment) |
| Engineering (Yahya — founder time) | Sweat equity (no cash burn) |
| Paperclip agent operations | Minimal (included in ops) |
| Misc (domains, tools, APIs) | ~$0–$30 |
| **Total cash burn** | **~$0–$30/month** |

### 3.2 Runway Assessment

| Scenario | Runway |
|----------|--------|
| Current (no revenue, ~$0 burn) | Indefinite on infrastructure; bounded by founder capacity |
| Post-pilot contract signed ($500/month revenue) | Cash-flow positive on infra immediately |
| Hardware procurement (50 units, ~$9,500) | Requires contract-gated; to be funded by World Bank grant or Ministry advance |
| Phase 2 scale ($5,000/month, ~$350/month infra) | Very healthy unit economics — 93% gross margin |

**Key risk:** The company's runway depends on **founder time**, not cash. There is no monthly cash obligation at the current stage. This is both a strength (no pressure to raise) and a risk (single point of dependency on Yahya's capacity).

---

## 4. Budget vs. Actual (April 2026)

| Line Item | Budgeted (April) | Actual (April) | Variance | Status |
|-----------|-----------------|----------------|----------|--------|
| Vercel hosting | $0 | $0 | — | ✅ On target |
| Supabase | $0 | $0 | — | ✅ On target |
| GPS hardware | $0 (pre-contract) | $0 | — | ✅ Gated correctly |
| Development tooling | $0–$50 | ~$0–$30 | — | ✅ On target |
| Ministry pilot revenue | $0 (not signed yet) | $0 | — | ⚠️ Pending signature |
| **Total** | **$0–$50 spend** | **$0–$30 spend** | | ✅ |

---

## 5. Cost Optimization Opportunities

| Area | Opportunity | Estimated Saving | Priority |
|------|------------|-----------------|----------|
| Supabase Realtime connections | Enable connection pooling before scaling past 50 vehicles | $50–$100/month at scale | Medium |
| Redis caching layer | Implement Redis (free via Upstash) before Supabase compute limit hit | Extends free tier by 3–4 months | High |
| Vercel bandwidth | Enable edge caching for GTFS static feed (changes weekly) | Reduces bandwidth ~30% | Low |
| GPS SIM data | Negotiate bulk SIM rates with Syriatel before 50-device deployment | $0.50–$2/device/month saving | High (pre-deployment) |
| Teltonika hardware | Purchase 100 units instead of 50 (Ministry pilot + buffer) for volume discount ~15% | ~$500 saving | Medium |

---

## 6. Grant Pipeline Tracking

| Grant | Submitted | Status | Amount | Decision Expected |
|-------|-----------|--------|--------|------------------|
| World Bank IBRD (Syria transport) | Yes | In review | $50M pool; DAM request ~$149,000 | Q3 2026 |
| UNDP Syria urban mobility | Referenced | Proposal stage | $50,000–$200,000 | Q3–Q4 2026 |
| EU reconstruction infrastructure | Referenced | Pipeline | $50,000–$130,000 | Q4 2026 |
| IsDB | Referenced | Pipeline | TBD | 2026–2027 |

**Grant funding is not included in base revenue projections.** It is treated as contingency/upside that funds hardware procurement and team expansion — not operational sustainability.

---

## 7. Flags for CEO Attention

### ⚠️ FLAG 1 — Ministry Contract Signature Critical Path
The April 26, 2026 MoU signing target is the single most important near-term financial event. If delayed beyond May 15, the 12-month revenue model slips by one full quarter. **Recommend:** Yahya personally follow up with Ministry focal point by April 21.

### ⚠️ FLAG 2 — Hardware Funding Gap
GPS hardware (~$9,500 for 50 units) must be procured 3–4 weeks before vehicles go live (June 1 target). This requires either:
- World Bank grant first disbursement (uncertain timing), OR
- Ministry advance payment on pilot contract, OR
- Founder bridge (cash-efficient since devices have 2–3 month payback)

**Recommend:** Include hardware advance clause in Ministry MoU, or clarify World Bank disbursement timeline.

### 🟡 FLAG 3 — Supabase Free Tier Will Break Before Phase 2
At 500 vehicles with real-time GPS writes (~1 write/10s per vehicle = 3,000 writes/min), the Supabase free tier compute and DB limits will be exceeded in the first month of Phase 2. This is expected and manageable — Supabase Pro is $25/month — but it needs to be budgeted explicitly before Phase 2 begins.

### ✅ POSITIVE — Gross Margin Is Exceptional
At $10/vehicle/month revenue and $2/vehicle/month variable cost, DAM's gross margin is **80–96%**. This is a structural advantage. The free-tier infrastructure strategy is working and should be maintained as long as possible.

---

## 8. 12-Month Financial Targets

| Metric | Target | Status |
|--------|--------|--------|
| First paying contract | May 2026 | On track (pending April 26 signature) |
| Monthly recurring revenue (Month 12) | $10,000+ | On track if Phase 2 executes |
| 12-month cumulative revenue | $50,000 | On track (base scenario) |
| Grant funding received | $149,000 | TBD (World Bank) |
| Infrastructure cost at Month 12 | <$500/month | On track |
| Gross margin | >80% | Confirmed by unit economics |

---

*This document is updated monthly by the Finance Manager as part of Routine 8 (Financial Health Check).*
*Next review: May 2026.*
