# Memorandum of Understanding
## Ministry of Transport, Syrian Arab Republic
## and Damascus Transit Technologies Ltd.

**Document Status:** Template — For Negotiation
**Version:** 1.0
**Prepared by:** Legal Advisor, Damascus Transit Technologies Ltd.
**Date:** March 30, 2026

---

## MEMORANDUM OF UNDERSTANDING

**Between:**

The **Ministry of Transport, Syrian Arab Republic**, represented by the Director General of Land Transport, hereinafter referred to as the "Ministry";

**and**

**Damascus Transit Technologies Ltd.** (DAM), a company incorporated under Syrian commercial law, with its principal place of business in Damascus, Syrian Arab Republic, represented by its Chief Executive Officer, hereinafter referred to as "DamascusTransit";

collectively referred to as the "Parties".

---

## ARTICLE 1 — PURPOSE AND SCOPE

**1.1** This Memorandum of Understanding (MoU) establishes a framework for cooperation between the Ministry and DamascusTransit in the deployment, operation, and regulation of a GPS-based real-time public transit management platform in Damascus, Syrian Arab Republic.

**1.2** The objectives of this cooperation are:

(a) To modernize Damascus public transport through real-time vehicle tracking and passenger information technology;

(b) To enable the Ministry to exercise its statutory oversight functions under Syrian Transport Law No. 12/2024 through digital data access;

(c) To establish the legal and data-sharing framework within which DamascusTransit may commercially operate its platform;

(d) To facilitate DamascusTransit's integration with the Ministry's official route registry and licensing systems.

**1.3** This MoU does not constitute a commercial contract, grant of subsidy, or exclusive license. Each Party retains its full legal and administrative independence.

---

## ARTICLE 2 — DATA SHARING TERMS

**2.1 Ministry Data Provided to DamascusTransit**

The Ministry agrees to provide DamascusTransit, on a non-exclusive basis and subject to applicable law, the following data to support platform operations:

(a) **Official Route Registry:** Current, official route definitions including route numbers, start/end points, authorized stops, and geographic coordinates, updated within 15 days of any official change;

(b) **Vehicle Licensing Data:** Confirmation of licensing status for vehicles registered on the DamascusTransit platform, provided via API query on a per-vehicle basis (not bulk disclosure);

(c) **Schedule Data:** Published transport schedules for Damascus routes to the extent these are held by the Ministry in machine-readable form;

(d) **Regulatory Notices:** Any regulatory notices, directives, or legal changes relevant to digital fleet management platforms, provided with minimum 30 days' advance notice where operationally feasible.

**2.2 DamascusTransit Data Provided to the Ministry**

DamascusTransit agrees to provide the Ministry, on an ongoing basis:

(a) **Real-Time Fleet Dashboard Access:** Read-only Ministry-credentialed access to the administrative interface showing live vehicle positions, active routes, and fleet status for all registered vehicles;

(b) **GTFS Static Feed:** A current, validated GTFS feed of all active routes, stops, and schedules operated through the platform, updated within 15 days of any route change;

(c) **Aggregated Analytics:** Monthly statistical reports on fleet utilization, route adherence rates, average headways, and incident counts — presented in aggregate form, without identifying individual vehicles, drivers, or passengers;

(d) **Incident Reports:** Notification of any significant service disruptions (affecting ≥10% of the active fleet for ≥2 hours) within 24 hours of occurrence.

**2.3 Data Restrictions**

The following data may not be disclosed by either Party without the explicit written consent of the relevant data subjects:

(a) Individual driver location histories or personal data, except to the extent required by law or lawful legal process;

(b) Raw passenger app usage data or journey histories;

(c) Bulk position data streams, except via the credentialed Ministry dashboard interface.

**2.4 Data Accuracy**

Each Party warrants that data it provides to the other is accurate to the best of its knowledge at the time of provision. Neither Party guarantees real-time accuracy of data provided on a periodic or batch basis.

---

## ARTICLE 3 — ROUTE LICENSING INTEGRATION

**3.1** DamascusTransit agrees to operate its platform only on routes that are officially registered in the Ministry's route registry or that have received written interim authorization from the Ministry.

**3.2** DamascusTransit shall synchronize its active route set with the Ministry route registry within **15 calendar days** of any route addition, removal, or material modification in the registry.

**3.3** DamascusTransit shall provide the Ministry with its current GTFS static feed via an authenticated API endpoint, updated within 15 days of any route change. The Ministry may use this GTFS feed for official transport planning purposes.

**3.4** Where DamascusTransit identifies discrepancies between its platform data and the Ministry's official registry (e.g., route coordinates, stop locations), it shall notify the Ministry's competent department in writing within 7 days and cooperate in resolving the discrepancy.

**3.5** The Ministry agrees to notify DamascusTransit of any planned route changes with a minimum of **15 calendar days' advance notice** where operationally feasible, to allow platform updates.

---

## ARTICLE 4 — PRIVACY AND DATA PROTECTION OBLIGATIONS

**4.1 DamascusTransit Obligations**

DamascusTransit, as the data controller for personal data processed through its platform, agrees to:

(a) **Lawful Basis:** Process personal data only on a lawful basis as defined under the Syrian Personal Data Protection Decree 2023 and applicable law;

(b) **Data Minimization:** Collect and retain only personal data strictly necessary for the stated purposes of fleet management and passenger information;

(c) **Consent:** Obtain explicit, granular consent from all passenger app users and all registered drivers before collecting their personal data;

(d) **Data Subject Rights:** Respond to Data Subject Access Requests within **30 calendar days** of receipt;

(e) **Retention Limits:** Retain GPS position data for a maximum of **12 months** for operational purposes; driver personal data for the duration of the operating agreement plus **5 years**; passenger data for a maximum of **24 months**;

(f) **Data Residency:** Maintain primary data within Syria or a country recognized as adequate by the Syrian data protection authority, or as otherwise permitted by Ministry derogation during the reconstruction phase;

(g) **Security Standards:** Implement and maintain at minimum: AES-256 encryption at rest; TLS 1.3 encryption in transit; JWT authentication with role-based access control; quarterly automated security scanning;

(h) **Breach Notification:** Notify the Ministry of Transport Cybersecurity Unit within **72 hours** of detecting any personal data breach; notify affected data subjects within **7 days** where the breach poses high risk to their rights;

(i) **DPIA:** Conduct a Data Protection Impact Assessment before deploying any new data processing feature that involves systematic tracking or profiling of individuals;

(j) **Processor Agreements:** Execute Data Processing Agreements with all third-party data processors (including cloud infrastructure providers) before processing any personal data through such processors.

**4.2 Ministry Obligations**

The Ministry, as recipient of data from DamascusTransit, agrees to:

(a) Use DamascusTransit-provided data only for the Ministry's statutory transport regulation and planning functions;

(b) Not disclose DamascusTransit-provided data to third parties without DamascusTransit's prior written consent, except as required by law;

(c) Implement appropriate technical and organizational measures to protect the confidentiality and integrity of data received from DamascusTransit;

(d) Notify DamascusTransit within **72 hours** of detecting any security incident affecting data received from DamascusTransit.

---

## ARTICLE 5 — TERM, RENEWAL, AND TERMINATION

**5.1 Initial Term**

This MoU shall enter into force on the date of last signature by both Parties and shall remain in effect for an initial term of **two (2) years** ("Initial Term").

**5.2 Renewal**

Upon expiry of the Initial Term, this MoU shall automatically renew for successive **one (1) year** terms unless either Party provides written notice of non-renewal at least **60 calendar days** before the end of the then-current term.

**5.3 Termination for Cause**

Either Party may terminate this MoU for material breach by the other Party upon **30 calendar days' written notice**, provided that:

(a) The notifying Party has described the alleged breach in the notice with reasonable specificity;

(b) The breaching Party has failed to cure the breach within the 30-day notice period.

**5.4 Termination for Convenience**

Either Party may terminate this MoU for convenience upon **90 calendar days' written notice** to the other Party, without cause and without liability.

**5.5 Effect of Termination**

Upon termination of this MoU:

(a) DamascusTransit shall continue to provide the Ministry API access for **30 days** after the termination effective date to allow for data extraction and transition;

(b) Each Party shall return or destroy the other Party's confidential data within **60 days** of the termination effective date;

(c) DamascusTransit's Class B Digital Transport License (if granted) remains subject to separate Ministry licensing proceedings independent of this MoU.

**5.6 Survival**

The following provisions shall survive termination of this MoU: Article 4 (Privacy and Data Protection), Article 6 (IP Ownership, §6.4 confidentiality), and any payment obligations accrued before termination.

---

## ARTICLE 6 — INTELLECTUAL PROPERTY OWNERSHIP

**6.1 DamascusTransit Platform IP**

DamascusTransit retains sole and exclusive ownership of all intellectual property rights in:

(a) The DamascusTransit platform, including all source code, algorithms, software architecture, and technical documentation;

(b) All data analytics, reports, and derived data products generated from the platform;

(c) The DamascusTransit brand, trademarks, and trade dress.

The Ministry receives no license to DamascusTransit's proprietary IP except the limited data access rights expressly granted in Article 2.

**6.2 Ministry Official Data**

The Ministry retains sole and exclusive ownership of all intellectual property rights in:

(a) The official route registry and all official transport data;

(b) Vehicle licensing records;

(c) All ministerial publications, maps, and official data sets.

DamascusTransit receives a non-exclusive, non-transferable, royalty-free license to use Ministry data solely for the purpose of operating the platform as contemplated by this MoU.

**6.3 Open-Source Components**

DamascusTransit acknowledges that certain components of the platform are based on open-source software licensed under permissive licenses (MIT, Apache 2.0). These components remain subject to their respective open-source licenses. DamascusTransit warrants that its use of open-source components complies with all applicable license terms.

**6.4 Future Joint Work**

If the Parties undertake any future collaboration that produces jointly developed intellectual property (e.g., a custom Ministry transport data standard), ownership, licensing, and commercialization terms for such joint work shall be agreed in a separate written instrument before development commences.

---

## ARTICLE 7 — GENERAL PROVISIONS

**7.1 Governing Law**

This MoU shall be governed by and construed in accordance with the laws of the Syrian Arab Republic.

**7.2 Dispute Resolution**

Any dispute arising from or relating to this MoU shall first be subject to good-faith negotiation between senior representatives of both Parties for a period of **30 days**. If unresolved, disputes shall be referred to arbitration under the Syrian Commercial Arbitration Law, with proceedings conducted in Damascus in Arabic.

**7.3 Confidentiality**

Each Party agrees to treat as confidential all non-public information received from the other Party in connection with this MoU and to use such information only for the purposes of this MoU.

**7.4 No Exclusivity**

This MoU does not grant DamascusTransit any exclusive right to operate digital fleet management services in Syria, nor does it restrict the Ministry from entering into similar arrangements with other technology providers.

**7.5 Amendments**

This MoU may be amended only by a written instrument signed by authorized representatives of both Parties.

**7.6 Entire Agreement**

This MoU constitutes the entire agreement between the Parties with respect to its subject matter and supersedes all prior understandings, representations, and agreements relating to the same subject matter.

**7.7 Notices**

All notices under this MoU shall be in writing, in both Arabic and English, and delivered to:

*Ministry of Transport, Syrian Arab Republic:*
Director General of Land Transport
[Address — to be confirmed]
Damascus, Syrian Arab Republic

*Damascus Transit Technologies Ltd.:*
Chief Executive Officer
[Address — to be confirmed]
Damascus, Syrian Arab Republic

---

## SIGNATURES

**For and on behalf of the Ministry of Transport, Syrian Arab Republic:**

Name: ___________________________

Title: Director General of Land Transport

Signature: ___________________________

Date: ___________________________

Official Seal: ___________________________

---

**For and on behalf of Damascus Transit Technologies Ltd.:**

Name: ___________________________

Title: Chief Executive Officer

Signature: ___________________________

Date: ___________________________

---

*This template has been prepared by the Legal Advisor of Damascus Transit Technologies Ltd. for negotiation purposes. Both Parties should seek independent legal counsel before execution. Arabic translation must be verified by a certified translator; in case of conflict between Arabic and English versions, the Arabic version shall prevail for Ministry purposes.*
