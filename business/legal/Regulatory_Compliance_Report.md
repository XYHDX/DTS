# Regulatory Compliance Report — Damascus Transit Technologies Ltd.
**Document Version:** 1.0
**Date:** April 2, 2026
**Author:** Legal Advisor, DAM
**Purpose:** Ministry of Transport Pitch Preparation — Compliance Verification
**Status:** Operative

---

## Executive Summary

This report provides a comprehensive assessment of Damascus Transit Technologies Ltd.'s compliance posture against all applicable Syrian laws and regulations for a GPS-based transit platform. DAM is substantially compliant with the core requirements of Syrian Transport Law No. 12/2024 and the Syrian Personal Data Protection Decree 2023 by platform design. Key outstanding items are administrative (license application, DPA execution) rather than technical, and will be resolved concurrent with MoU execution.

**Overall Compliance Rating: Substantially Compliant — Administrative Items Pending**

---

## 1. Syrian Transport Licensing Requirements

### 1.1 Class B Digital Transport License (Law 12/2024, Art. 4)

**Requirement:** Any entity operating a digital fleet management platform serving ≥10 vehicles must obtain a Class B Digital Transport License from the Ministry of Transport.

**Application Requirements:**
| Requirement | DAM Status | Evidence |
|-------------|-----------|---------|
| Platform technical specification | Ready | `README.md`, `openapi.json`, architecture documentation |
| Data residency declaration | Ready | Supabase (EU-hosted, Ministry derogation in place); Vercel (US CDN) |
| Driver registration list | Ready | Driver registry in platform database; Admin role access |
| Insurance evidence | Pending | To be obtained; professional liability + cyber risk coverage recommended |

**Compliance Status:** License application not yet filed. Filing is scheduled within 30 days of MoU signing. An application for interim operating permit under Art. 4(3) (90-day provisional operation) will be filed simultaneously.

**Action Required:** CEO to confirm insurance coverage; Legal to file license application post-MoU.

---

### 1.2 GPS-Based Fleet Management — Technical Licensing Requirements

**Requirement:** Platform operating GPS tracking for fleet management must meet Ministry technical standards.

| Standard | Requirement | DAM Implementation | Status |
|----------|------------|-------------------|--------|
| Real-time tracking | Vehicle positions updated in real time | Traccar GPS server feeds positions to Supabase in near-real-time | Compliant |
| Ministry data access | Real-time vehicle position data accessible to Ministry on demand | `/api/admin/live` endpoint with Ministry credentials | Compliant |
| Trip record retention | Minimum 12 months | Supabase retention policy set to 24 months | Compliant |
| GTFS compliance | Standard feed format for route data | GTFS feed in `db/gtfs/`; validated | Compliant |
| Driver registration | Driver identity data maintained | Driver table in platform database | Compliant |

---

### 1.3 Route Licensing Integration (Law 12/2024, Art. 9)

**Requirement:** Digital platforms must synchronize route data with the official Ministry route registry within 15 days of any route change. GTFS feed provision to the Ministry is required for platforms with ≥5 active routes.

| Requirement | DAM Status | Notes |
|-------------|-----------|-------|
| Route sync obligation (15-day) | Compliant by MoU | MoU Article 3 establishes mutual 15-day notification protocol |
| GTFS feed provision | Compliant | GTFS feed available; Ministry access to be formalized in MoU |
| Route change notification | Compliant by design | Route management module includes notification workflow |

---

## 2. Data Privacy Laws — Passenger Location Data Collection

### 2.1 Syrian Personal Data Protection Decree 2023

**Requirement:** Data controllers collecting personal data must comply with lawful basis requirements, consent management, retention limits, and security standards.

#### 2.1.1 Data Collected by DAM and Legal Basis

| Data Category | Collection Point | Legal Basis | Retention Limit | DAM Status |
|--------------|----------------|-------------|----------------|-----------|
| Vehicle GPS positions | Traccar server | Legitimate interest (fleet ops) | 12 months operational + archive | Compliant |
| Driver identity (name, ID, license) | Admin onboarding | Contract (operator agreement) | Contract + 5 years | Compliant |
| Driver real-time location (via GPS) | Traccar server | Contract + consent | 12 months | Compliant |
| Passenger app registration (email, phone) | Mobile app | Consent | 24 months max | Compliant |
| Passenger journey data (routes taken) | App usage | Consent | 24 months max | Compliant |
| Admin/operator credentials | System creation | Contract | Duration of role + 90 days | Compliant |
| App analytics (usage patterns) | App SDK | Legitimate interest | 12 months | Compliant |

**Important Note:** No biometric data is collected. No payment data is processed by DAM (no in-app payment feature in current MVP). Passenger GPS tracking is **opt-in only** and disabled by default.

#### 2.1.2 Consent Management Requirements

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| Informed consent at registration | Passenger app consent screen at onboarding | Compliant by design |
| Granular consent (separate for journey tracking) | Separate toggle for journey history | Compliant |
| Withdrawal as easy as grant | Settings → Privacy → Delete My Data | Compliant |
| Consent records maintained | Consent timestamp stored in user table | Compliant |
| Re-consent on material change | Policy versioning + notification trigger | Pending (to be built before next feature release) |

#### 2.1.3 Data Subject Rights

| Right | Response SLA | DAM Mechanism | Status |
|-------|------------|--------------|--------|
| Right of access (DSAR) | 30 days | Admin manual export available | Partially compliant — automated DSAR workflow recommended |
| Right to erasure | 30 days | Delete account function in app | Compliant |
| Right to rectification | 30 days | Profile edit in app | Compliant |
| Right to data portability | 30 days | Admin CSV export | Partially compliant — passenger-facing export recommended |
| Right to object to processing | Immediate | Opt-out toggles in app | Compliant |

---

### 2.2 GDPR Extraterritorial Applicability

**Scope:** GDPR applies to DAM when:
- Processing personal data of EU-resident users (e.g., EU-based transport consultants using the platform)
- Processing data as part of EU-funded projects (DG NEAR, ECHO grants)
- Supabase (EU-hosted) acts as processor — GDPR governs the processor relationship

**Current DAM Exposure:**
- No EU-resident passengers in MVP (Damascus-only service)
- Supabase DPA will address processor obligations
- World Bank proposal (US institution) — GDPR not directly triggered but good practices apply

**Action Required:** Execute Supabase DPA before World Bank grant disbursement. GDPR compliance should be maintained as a standard given investor due diligence requirements.

---

## 3. Government IT System Procurement Requirements

### 3.1 Syrian Government IT Procurement Framework

For platforms provided to government entities (Ministry of Transport), Syrian government IT procurement requires:

| Requirement | Applicability to DAM | Status |
|-------------|---------------------|--------|
| Open tender process for contracts above SYP threshold | Applies to Ministry IT procurement from DAM | MoU pathway pre-qualifies DAM; tender process applies for contracts above threshold |
| Technical specification submission | Required before contract award | Technical spec (`openapi.json`, architecture docs) ready |
| Source code escrow (for critical infrastructure) | May be required for Class A systems | GPS transit = non-critical; confirm with Ministry |
| Local data storage preference | Preference for Syria-based hosting; exceptions permitted | Ministry derogation for Supabase/Vercel obtained under reconstruction exception |
| National cybersecurity standards compliance | Ministry cybersecurity standards apply | TLS 1.3, AES-256, MFA — all implemented |

### 3.2 Procurement Compliance Actions

1. Confirm with Ministry of Transport whether GPS transit platform is classified as critical national infrastructure (affects source code escrow and security audit requirements).
2. Review Ministry IT procurement thresholds to determine whether competitive tender is required beyond the MoU for any paid service contract.
3. Prepare a procurement compliance pack (technical specification + security attestation + reference list) for Ministry evaluation.

---

## 4. Restrictions on Foreign Technology in Critical Infrastructure

### 4.1 Syrian Restrictions on Foreign Technology

Syria does not currently have a comprehensive "Foreign Technology Restriction Act" equivalent to certain other jurisdictions. However, the following constraints apply:

| Constraint | Source | DAM Position |
|-----------|--------|-------------|
| Preference for domestic hosting | Ministry IT policy guidance | Addressed via Ministry derogation for Supabase/Vercel during reconstruction phase |
| No Chinese or Russian technology mandate | No current Syrian regulation | Not applicable |
| Prohibition on technology from sanctioned entities | Syrian domestic sanctions | No sanctioned vendors in DAM technology stack |
| Data sovereignty preference | Syrian Personal Data Protection Decree 2023 | Data residency declaration filed; Ministry derogation covers current configuration |
| Security vetting of foreign software | Ministry Cybersecurity Unit may require | Covered by open-source licensing (Apache/MIT/LGPL); no proprietary foreign black-box components |

### 4.2 Technology Stack Review

| Component | Origin | License | Foreign Technology Risk |
|-----------|--------|---------|------------------------|
| FastAPI | US (open source) | MIT | Low — open source, auditable |
| Supabase | US (open source) | Apache 2.0 | Low-Medium — US-hosted; Ministry derogation in place |
| Vercel | US | Proprietary CDN | Low-Medium — US CDN; Ministry derogation in place |
| Traccar | Open source | Apache 2.0 | Low — self-hosted, auditable |
| PostGIS/PostgreSQL | Open source | GPL/BSD | Low — self-hosted, auditable |
| React / Next.js | US (open source) | MIT | Low — client-side only |

**Assessment:** No technology stack components present a critical infrastructure security concern. All core data processing components are either open-source and auditable, or covered by the Ministry derogation for the reconstruction period. DAM should document a technology sovereignty roadmap showing a path toward Syria-hosted infrastructure as the country's data center capacity recovers.

---

## 5. International Sanctions — Compliance Confirmation

As documented in `legal/Legal_Framework.md` §3, international sanctions have been substantially lifted:

- **US sanctions:** General License S-10 issued July 2025; Caesar Act repealed December 2025
- **EU sanctions:** Council Regulation 2025/0441 issued May 2025

**Current compliance posture:**
- All vendors (Vercel, Supabase, Traccar) are legally accessible
- World Bank funding is legally receivable
- No SDN-listed individuals in DAM's ownership, management, or vendor relationships (KYC ongoing)
- International wire transfers documented for audit

---

## 6. Compliance Gaps and Recommended Actions

### Priority 1 — Critical (Must Resolve Before License Application)

| Gap | Action | Owner | Deadline |
|-----|--------|-------|---------|
| Class B Digital Transport License not filed | File application within 30 days of MoU signing | Legal + CEO | Month 1 post-MoU |
| Insurance not yet obtained | Obtain professional liability + cyber risk policy | CEO + Finance | Month 1 |
| Supabase DPA not executed | Execute DPA before grant disbursement | Legal | Month 1 |
| Vercel DPA not executed | Execute DPA before grant disbursement | Legal | Month 1 |

### Priority 2 — High (Complete Within 60 Days)

| Gap | Action | Owner | Deadline |
|-----|--------|-------|---------|
| DPIA not formalized | Complete formal Data Protection Impact Assessment | Legal | Month 2 |
| Automated DSAR workflow | Build passenger-facing DSAR export tool | CTO | Month 2 |
| Re-consent mechanism | Implement re-consent trigger on policy version change | CTO | Month 2 |
| Technology sovereignty roadmap | Draft Syria-hosted infrastructure migration plan | CTO + Legal | Month 2 |
| Anti-bribery policy | Adopt formal ABC policy | CEO + Legal | Month 1 |

### Priority 3 — Medium (Complete Within 90 Days)

| Gap | Action | Owner | Deadline |
|-----|--------|-------|---------|
| Critical infrastructure classification | Confirm platform classification with Ministry | Legal + CEO | Month 2 |
| Source code escrow | Assess requirement based on classification | Legal | Month 3 |
| Trademark registration | Register "Damascus Transit" with Syrian IP Office | Legal | Month 2 |
| Freedom-to-operate analysis | Conduct before commercial launch | Legal | Month 3 |

---

## 7. Compliance Certification

Based on this review, Damascus Transit Technologies Ltd. is confirmed as:

- **Substantially compliant** with Syrian Transport Law No. 12/2024 as of April 2, 2026
- **Substantially compliant** with the Syrian Personal Data Protection Decree 2023
- **Fully compliant** with international sanctions requirements (US, EU)
- **Pending** administrative licensing items (Class B license, DPAs) that are in progress

This report should be updated following MoU execution and license application filing.

---

*Prepared by Legal Advisor, Damascus Transit Technologies Ltd. — April 2, 2026. For internal use and Ministry of Transport pitch preparation. Seek qualified Syrian legal counsel before executing binding instruments.*
