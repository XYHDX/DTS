# Data Privacy Policy — Damascus Transit Platform (Passenger App)
**Document Version:** 1.0
**Effective Date:** April 2, 2026
**Author:** Legal Advisor, Damascus Transit Technologies Ltd.
**Status:** Draft — Pending Final Review Before App Publication

---

## 1. Introduction

Damascus Transit Technologies Ltd. ("DAM", "we", "us") operates the Damascus Transit passenger application (the "App") and the associated transit platform. We are committed to protecting the privacy of passengers who use our App and to complying with the Syrian Personal Data Protection Decree 2023, Syrian Transport Law No. 12/2024, and applicable international privacy standards.

This Privacy Policy explains:
- What personal data we collect about you
- Why we collect it and on what legal basis
- How we store, process, and protect it
- How long we keep it
- Your rights regarding your data
- How to contact us or withdraw your consent

By creating an account and using the App, you confirm that you have read and understood this policy. We will ask for your explicit consent before collecting any optional data.

---

## 2. Who We Are

**Data Controller:**
Damascus Transit Technologies Ltd. (DAM)
Damascus, Syrian Arab Republic
Company registration: Pending formal registration with Ministry of Economy
Email: privacy@damascustransit.sy *(placeholder — update before publication)*

---

## 3. Data We Collect

### 3.1 Account Registration Data (Required)

When you create an account, we collect:

| Data | Purpose | Legal Basis |
|------|---------|-------------|
| Mobile phone number or email address | Account creation and login | Contract (to provide the service) |
| Name (optional at registration) | Personalization | Consent |
| Account creation timestamp | Security logging | Legitimate interest |
| Device identifier (for push notifications) | Service notifications | Contract |

We do **not** collect: national ID number, passport details, date of birth, financial information, or any government-issued identifiers for passengers.

### 3.2 Journey and Location Data (Optional — Consent Required)

If you enable journey tracking in your App settings, we collect:

| Data | Purpose | Legal Basis |
|------|---------|-------------|
| Your current location (GPS) | Show nearby buses and your position on the map | Consent (opt-in only) |
| Routes you have taken | Improve route recommendations | Consent (opt-in only) |
| Departure and arrival stops | Journey history | Consent (opt-in only) |
| Journey timestamps | Service quality analysis | Consent (opt-in only) |

**Journey tracking is disabled by default.** You must actively enable it in Settings → Privacy → Journey Tracking.

We do **not** collect your location when the App is closed or running in the background (unless you have enabled background location, which requires a separate permission).

### 3.3 App Usage Analytics (Collected Automatically)

We collect anonymous usage data to improve the App:

| Data | Purpose | Legal Basis |
|------|---------|-------------|
| Screens visited in the App | Identify usability issues | Legitimate interest |
| App crash reports | Fix technical bugs | Legitimate interest |
| Device type and operating system | Ensure App compatibility | Legitimate interest |
| General city-level location (not precise GPS) | Regional usage statistics | Legitimate interest |

This analytics data **cannot be linked back to you individually** — it is collected in aggregate form only.

### 3.4 Communications

If you contact us for support, we collect:
- Your name and contact details (as provided)
- The content of your support request

We use this only to respond to your inquiry. We do not use support communications for marketing.

---

## 4. What We Do NOT Collect

We want to be clear about data we do **not** collect:

- Payment information (no in-app payments in current version)
- Biometric data (fingerprints, facial recognition)
- National ID or government-issued identification numbers
- Contacts or call history from your device
- SMS messages
- Photos or files from your device
- Information about other apps on your device
- Data about passengers from third-party sources

---

## 5. How We Use Your Data

| Use | Data Used | Legal Basis |
|-----|-----------|-------------|
| Provide real-time bus tracking and route information | App analytics, location (if enabled) | Contract |
| Send service notifications (delays, route changes) | Account contact data | Contract |
| Improve App features and fix bugs | Anonymous usage analytics | Legitimate interest |
| Comply with Ministry of Transport reporting obligations | Aggregated, anonymized route usage data only | Legal obligation |
| Respond to your support requests | Support communications | Contract |
| Safety and fraud prevention | Login and security logs | Legitimate interest |
| Comply with legal process (court orders, law enforcement) | As required by applicable law | Legal obligation |

We do **not** use your data for:
- Selling to third-party advertisers
- Profiling for credit, insurance, or employment purposes
- Monitoring individual driver or passenger behavior beyond fleet management

---

## 6. How We Store and Process Your Data

### 6.1 Infrastructure

| System | Role | Location |
|--------|------|---------|
| Supabase (PostgreSQL database) | Primary data storage | EU-hosted (Amsterdam), covered by Ministry derogation for reconstruction phase |
| Vercel | App API and content delivery | Global CDN; EU/US nodes; request logs only |
| Traccar (GPS server) | Vehicle tracking (not passenger data) | Self-hosted; no passenger data processed |

All passenger personal data is stored in Supabase's EU-hosted PostgreSQL database. Data is not stored on local servers in Syria during the current reconstruction phase, pursuant to a Ministry of Transport derogation allowing overseas processing. A Syria-hosted data residency plan is in development.

### 6.2 Security Measures

| Measure | Implementation |
|---------|--------------|
| Encryption in transit | TLS 1.3 for all data transmitted between your device and our servers |
| Encryption at rest | AES-256 encryption for all stored data |
| Authentication | JWT-based authentication; no passwords stored in plaintext |
| Access controls | Role-based access control (RBAC); passenger data accessible only to authorized Admin roles |
| Penetration testing | Quarterly automated security scanning; annual manual penetration test |
| Breach detection | 24-hour internal detection monitoring with automated alerts |

### 6.3 Who Has Access to Your Data

| Role | Access Level |
|------|-------------|
| Passengers (you) | Your own account data and journey history only |
| DAM Admin staff | Account management and support purposes only; no bulk access |
| Ministry of Transport | Aggregated, anonymized route usage data only; no individual passenger data |
| Supabase (processor) | Infrastructure processing only; governed by Data Processing Agreement |
| Vercel (processor) | API request metadata only; no personal data content; governed by DPA |
| Law enforcement | Only with valid legal process (court order or equivalent) |

We do **not** share your personal data with:
- Advertisers or marketing companies
- Other passengers
- Third-party analytics companies (beyond anonymous aggregate data)
- Any entity outside Syria without appropriate legal safeguards in place

---

## 7. Data Retention Periods

| Data Category | Retention Period | After Retention Period |
|--------------|----------------|----------------------|
| Account registration data | Duration of account + 24 months after deletion | Permanently deleted |
| Journey history (if enabled) | 24 months from collection | Permanently deleted |
| App usage analytics (anonymous) | 12 months | Permanently deleted |
| Support communications | 24 months from resolution | Permanently deleted |
| Security and login logs | 12 months | Permanently deleted |
| Consent records | Duration of account + 5 years | Archived, then deleted |

When your account is deleted:
1. Your personal data is immediately flagged for deletion
2. Deletion is completed within 30 days
3. Anonymous and aggregated data derived from your usage may be retained as it cannot identify you

---

## 8. Your Rights

Under the Syrian Personal Data Protection Decree 2023, you have the following rights regarding your personal data:

### 8.1 Right of Access
You can request a copy of all personal data we hold about you. We will provide this within **30 days** of your request.

**How to exercise:** Settings → Privacy → Download My Data, or email privacy@damascustransit.sy

### 8.2 Right to Erasure ("Right to be Forgotten")
You can request that we delete your account and all associated personal data.

**How to exercise:** Settings → Account → Delete Account, or email privacy@damascustransit.sy

**Exceptions:** We may retain certain data if required by law (e.g., legal proceedings, Ministry of Transport reporting obligations) but will inform you of any retention.

### 8.3 Right to Rectification
If your data is inaccurate, you can correct it.

**How to exercise:** Settings → Profile → Edit, or contact support

### 8.4 Right to Restrict Processing
You can ask us to stop using your data for certain purposes (e.g., analytics) while retaining your account.

**How to exercise:** Settings → Privacy → Privacy Controls, or email privacy@damascustransit.sy

### 8.5 Right to Data Portability
You can request your data in a machine-readable format (JSON or CSV).

**How to exercise:** Settings → Privacy → Download My Data (JSON export)

### 8.6 Right to Withdraw Consent
For any data processing based on your consent (journey tracking, personalization), you can withdraw consent at any time. Withdrawal does not affect processing that occurred before withdrawal.

**How to exercise:** Settings → Privacy → Consent Settings

### 8.7 Right to Object
You can object to processing based on legitimate interest at any time. We will stop unless we can demonstrate compelling legitimate grounds.

**How to exercise:** Email privacy@damascustransit.sy with subject "Objection to Processing"

---

## 9. Opt-Out Mechanisms

| Feature | How to Opt Out |
|---------|--------------|
| Journey tracking | Settings → Privacy → Journey Tracking → Off |
| Push notifications | Settings → Notifications → Off |
| Analytics data collection | Settings → Privacy → Analytics → Off |
| Personalized route suggestions | Settings → Privacy → Personalization → Off |
| All optional processing | Settings → Privacy → Opt Out of All Optional Processing |

---

## 10. Children's Privacy

The Damascus Transit App is not intended for children under 13 years of age. We do not knowingly collect personal data from children under 13. If you believe a child under 13 has provided us with personal data, please contact us immediately at privacy@damascustransit.sy and we will delete it.

Passengers aged 13–17 may use the App with parental consent. If you are a parent or guardian concerned about your child's use of the App, please contact us.

---

## 11. Changes to This Policy

We may update this Privacy Policy from time to time. When we make significant changes:
1. We will notify you via the App (push notification or in-app banner)
2. We will update the "Effective Date" at the top of this document
3. For material changes affecting your rights or how we use your data, we will ask for your renewed consent before the change takes effect

Your continued use of the App after a non-material change constitutes acceptance of the updated policy. For material changes, we require explicit re-consent.

---

## 12. Contact Us

**Privacy Officer:**
Damascus Transit Technologies Ltd.
Email: privacy@damascustransit.sy *(update before publication)*
Address: Damascus, Syrian Arab Republic

**For Syrian regulatory matters:**
Ministry of Transport, Data Protection Unit
Damascus, Syrian Arab Republic

**Response time:** We aim to respond to all privacy inquiries within 5 business days and to formal rights requests within 30 calendar days.

If you believe we have not adequately addressed your privacy concern, you may lodge a complaint with the Syrian Ministry of Transport or the competent data protection authority.

---

## 13. Technical Glossary

| Term | Definition |
|------|-----------|
| GPS | Global Positioning System — satellite-based technology that determines geographic location |
| TLS 1.3 | Transport Layer Security version 1.3 — encryption protocol for data in transit |
| AES-256 | Advanced Encryption Standard with 256-bit key — encryption for data at rest |
| JWT | JSON Web Token — secure method for transmitting authentication data |
| RBAC | Role-Based Access Control — restricting data access based on user role |
| DSAR | Data Subject Access Request — a formal request to access your personal data |
| DPA | Data Processing Agreement — contract with third-party processors defining data handling obligations |

---

*This Privacy Policy was prepared by the Legal Advisor of Damascus Transit Technologies Ltd. and is effective as of April 2, 2026. It is subject to revision as Syrian data protection regulations are further developed. For questions, contact privacy@damascustransit.sy.*
