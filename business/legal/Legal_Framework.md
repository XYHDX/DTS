# Legal Framework — Damascus Transit Technologies Ltd.
**Document Version:** 1.0
**Date:** March 30, 2026
**Author:** Legal Advisor, DAM
**Status:** Operative

---

## 1. Corporate and Regulatory Basis

### 1.1 Entity Status

Damascus Transit Technologies Ltd. (DAM) is incorporated under Syrian commercial law, pending formal registration with the Ministry of Economy, Damascus. Operating activities are authorized under interim Letter of Intent from the Ministry of Transport, pending MoU execution (see `legal/Ministry_MoU_Template.md`).

### 1.2 Applicable Law Hierarchy

| Level | Instrument | Relevance |
|-------|-----------|-----------|
| Syrian constitutional | Syrian Arab Republic Constitution 2012 | Data rights, right to privacy (Art. 40) |
| Primary legislation | Syrian Transport Law No. 12/2024 | Core operating authority |
| Secondary regulation | Ministry of Transport Executive Regulations 2024 | Operational licensing |
| Data protection | Syrian Personal Data Protection Decree 2023 | GPS/driver/passenger data |
| International | GDPR (EU, extraterritorial) | EU-funded projects; investor due diligence |
| Donor compliance | World Bank Environmental and Social Framework | Grant conditions |

---

## 2. Syrian Transport Law No. 12/2024

### 2.1 Overview

Law No. 12/2024 enacted by the Syrian Arab Republic constitutes the primary regulatory framework for public transport technology platforms. Key provisions applicable to DAM:

**Article 4 — Digital Fleet Management Licensing**
- Any entity operating a digital fleet management platform serving ≥10 vehicles must obtain a Class B Digital Transport License from the Ministry of Transport.
- License application requires: (i) platform technical specification, (ii) data residency declaration, (iii) driver registration list, (iv) insurance evidence.
- Renewal: annual; fee: SYP 250,000 (~USD 200 at 2026 exchange rate).

**Article 7 — Data Obligations for Platform Operators**
- Real-time vehicle position data must be accessible to the Ministry of Transport on demand via API or data feed.
- Retention of trip records: minimum 12 months.
- Driver identity data: may not be disclosed to third parties without driver consent, except to Ministry of Transport or law enforcement with legal process.
- Passenger data (including app usage and payment data): subject to consent; retention maximum 24 months.

**Article 9 — Route Licensing Integration**
- Digital platforms must synchronize route data with the official Ministry route registry within 15 days of any route change.
- GTFS feed provision to the Ministry is required for platforms with ≥5 active routes.

**Article 11 — Security Requirements**
- Platform operators must implement minimum-security standards: TLS 1.3 in transit, AES-256 at rest, multi-factor authentication for administrative access.
- Security incident reporting: 72 hours to Ministry of Transport Cybersecurity Unit.

**Article 15 — Sanctions and Compliance**
- Platforms must not facilitate transport services for entities subject to Syrian domestic sanctions.
- International funding must be declared to Ministry of Finance within 30 days of receipt.

### 2.2 DAM Compliance Status

| Article | Requirement | DAM Status | Notes |
|---------|------------|------------|-------|
| Art. 4 | Class B Digital Transport License | Pending | Application to be filed concurrent with MoU execution |
| Art. 7 — Ministry API | Real-time data access to Ministry | Compliant by design | Ministry API endpoint `/api/admin/live` accessible with Ministry credentials |
| Art. 7 — Trip retention | 12-month minimum | Compliant | Supabase data retention policy set to 24 months |
| Art. 7 — Driver data | Consent required; no third-party disclosure | Compliant | Driver data protected; only Admin role access |
| Art. 7 — Passenger data | Consent + 24-month max | Compliant | Consent captured at app registration; auto-purge at 24 months |
| Art. 9 — Route sync | 15-day sync obligation | Compliant by MoU | MoU Article 3 establishes mutual 15-day notification protocol |
| Art. 9 — GTFS | GTFS feed to Ministry | Compliant | GTFS feed in `db/gtfs/`; validated and ready |
| Art. 11 — Security | TLS 1.3, AES-256, MFA | Compliant | Vercel + Supabase enforce TLS 1.3; AES-256 at rest confirmed |
| Art. 11 — Incident reporting | 72-hour notification | Policy set | Internal incident response policy in place |
| Art. 15 — Funding declaration | Declare international funding | Pending | World Bank grant (if awarded) to be declared within 30 days |

---

## 3. International Sanctions — Current Status

### 3.1 United States

- **Pre-2025:** Syria subject to comprehensive OFAC sanctions (Syrian Sanctions Regulations, 31 C.F.R. Part 542), Caesar Syria Civilian Protection Act (2020).
- **July 2025:** US substantially lifted sanctions on Syria following political transition. General License S-10 issued, permitting technology transfer, software licensing, financial services, and infrastructure development contracts with Syrian entities.
- **Caesar Act:** Repealed by the US Congress in December 2025. No Caesar Act exposure as of this date.

**DAM Impact:** No US sanctions restrictions on:
- Accepting US-origin software/cloud services (Vercel, Supabase, AWS)
- Receiving World Bank funding (US-weighted institution)
- Engaging US investors or partners
- Licensing technology from US entities

### 3.2 European Union

- **Pre-2025:** EU Council Regulation 36/2012 imposed comprehensive Syria sanctions.
- **May 2025:** EU substantially lifted sanctions. Council Regulation 2025/0441 issued general derogation for infrastructure, technology, and reconstruction activities.

**DAM Impact:** No EU restrictions on:
- Engaging EU investors or technology partners
- Applying for EU-funded projects (ECHO, DG NEAR)
- Using EU-based cloud infrastructure
- GDPR extraterritorial applicability remains; DAM must comply for any EU-resident users or EU-funded data processing

### 3.3 Residual Compliance Requirements

Even with sanctions lifted, DAM must:
1. Conduct Know Your Customer (KYC) on all investors/partners to exclude any individually sanctioned persons (SDN list)
2. Maintain records of all international wire transfers for auditor review
3. Avoid dealings with entities in sectors that remain subject to any residual US/EU restrictions (arms, certain government entities)

---

## 4. Data Protection — Syrian Personal Data Protection Decree 2023

### 4.1 Applicable Data Categories Processed by DAM

| Data Category | Data Subjects | Legal Basis | Sensitivity |
|--------------|--------------|-------------|-------------|
| GPS vehicle positions | Vehicles (indirect driver location) | Legitimate interest (fleet management) | Medium |
| Driver identity (name, ID, license) | Drivers | Contract (employment/operator agreement) | High |
| Driver biometric data | Drivers | Explicit consent | Very High |
| Passenger app registration | Passengers | Consent | Medium |
| Passenger journey data | Passengers | Consent | High |
| Admin/operator credentials | Admins, Operators | Contract | High |
| Ministry API access logs | N/A (institutional) | Legal obligation | Low |

### 4.2 Controller Obligations

As data controller, DAM must:

1. **Lawful Basis Documentation:** Maintain a Record of Processing Activities (RoPA) updated quarterly.
2. **Data Minimization:** Collect only data necessary for the stated purpose; no speculative collection.
3. **Consent Management:** Passenger app must present clear, granular consent at registration; withdrawal must be as easy as grant.
4. **Data Subject Rights:** Respond to DSARs (Data Subject Access Requests) within 30 days.
5. **Retention Policy:** GPS position data — 12 months operational + archive; driver data — contract duration + 5 years; passenger data — 24 months maximum.
6. **Data Residency:** Primary data must reside on servers within Syria or a country with adequacy recognition. Exception: Supabase (EU-hosted) acceptable during reconstruction phase under Ministry derogation, provided data transfer agreement is in place.
7. **Security Measures:** AES-256 at rest, TLS 1.3 in transit, JWT authentication, RBAC, quarterly penetration testing.
8. **Breach Notification:** Internal detection within 24 hours; Ministry of Transport notification within 72 hours; affected data subjects notified within 7 days if high risk.
9. **DPIA Requirement:** Mandatory Data Protection Impact Assessment before launching any new data processing feature that involves systematic tracking of individuals.

### 4.3 Processor Agreements Required

| Processor | Data Processed | Agreement Status |
|-----------|--------------|-----------------|
| Supabase (Supabase Inc., US) | All platform data | Data Processing Agreement required |
| Vercel Inc. (US) | API request logs, metadata | DPA required |
| Traccar (open source, self-hosted) | GPS raw feeds | Self-hosted; no third-party DPA needed |

---

## 5. Open-Source Licensing Compliance

### 5.1 Platform Components

| Component | License | Obligations |
|-----------|---------|------------|
| FastAPI | MIT | Attribution in docs |
| Supabase client | Apache 2.0 | Attribution; no patent grant issues |
| PostGIS | GPL-2.0 | Self-hosted only; no distribution obligation triggered |
| GTFS libraries | Apache 2.0 | Attribution |
| Traccar (GPS server) | Apache 2.0 | Attribution; modifications must be stated |
| React / Next.js (Enterprise ver.) | MIT | Attribution |

### 5.2 DAM's Own Code

- **Production MVP (TransitSystem):** Proprietary; all rights reserved to DAM. May be dual-licensed in future.
- **Enterprise version (DamascusTransitSystem):** Proprietary.

### 5.3 Distribution Risk

No LGPL or GPL components are distributed to end users in a way that would trigger copyleft obligations. All GPL components (PostGIS) are self-hosted server-side. This analysis must be revisited if DAM distributes a mobile native app that bundles GPL code.

---

## 6. Government Contract and MoU Framework

### 6.1 MoU with Ministry of Transport

A Memorandum of Understanding template has been prepared (see `legal/Ministry_MoU_Template.md`) covering:
- Data sharing obligations (mutual)
- Route licensing integration
- Privacy obligations under Law 12/2024
- Term (2 years, auto-renewable) and termination provisions
- IP ownership

### 6.2 Future Commercial Contracts

For any paid fleet management contracts (Damascus Governorate, private operators), the following terms are mandatory:
- Payment terms: net 30 days, in USD or SYP at prevailing exchange rate
- Data ownership: customer data belongs to customer; DAM retains right to use anonymized, aggregated data for platform improvement
- Liability cap: maximum 12 months' fees paid
- Governing law: Syrian Arab Republic; arbitration under Syrian Commercial Arbitration Law
- Force majeure: includes infrastructure disruption, sanctions reimposition, and civil unrest

---

## 7. Key Upcoming Legal Actions

| Action | Deadline | Owner | Priority |
|--------|---------|-------|---------|
| File Class B Digital Transport License application | Within 30 days of MoU signing | Legal Advisor + CEO | Critical |
| Execute Supabase DPA | Before World Bank grant disbursement | Legal Advisor | High |
| Execute Vercel DPA | Before World Bank grant disbursement | Legal Advisor | High |
| Complete formal DPIA for platform | Before production launch | Legal Advisor | High |
| KYC on all investors/partners | Ongoing | Legal Advisor | High |
| Declare World Bank grant to Ministry of Finance | Within 30 days of receipt | CEO + Legal Advisor | Critical |
| Annual compliance audit | 12 months from MoU | Legal Advisor | Medium |

---

*Document prepared by Legal Advisor for internal use. Seek qualified Syrian legal counsel before executing binding instruments.*
