# Alquist Insight — Privacy Notice

**Version 1.0 — effective 1 October 2026**

Information under Articles 13 and 14 of Regulation (EU) 2016/679 (GDPR).

---

## 1. Who is responsible

| Role                                                                                | Party                                                                                                                         |
|-------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| **Controller** for Customer Content and end-user questions                          | the organisation operating the particular deployment (the **Customer**) — identified in the Client                            |
| **Processor** acting on the Customer's instructions                                 | Czech Technical University in Prague – CIIRC, Jugoslávských partyzánů 1580/3, 160 00 Praha 6, IČO 68407700 (the **Provider**) |
| **Controller** for operational logs, security monitoring and administrator accounts | the Provider                                                                                                                  |

Data protection contact: dpo@cvut.cz
Supervisory authority: Úřad pro ochranu osobních údajů, Pplk. Sochora 27,
170 00 Praha 7, Czech Republic — uoou.gov.cz. You may also complain to the
authority in your own EU member state.

## 2. What we process

**Client (anonymous question interface)**

| Data                                                                       | Purpose                                                                          | Legal basis                                                                                        |
|----------------------------------------------------------------------------|----------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Random session identifier, newly generated for each session and not reused | maintaining conversational context across follow-up questions within one session | Art. 6(1)(f) — legitimate interest in a functioning service / Art. 6(1)(b) where a contract exists |
| Question text and generated answer                                         | producing the answer; quality and traffic monitoring by the operator             | Art. 6(1)(f) — legitimate interest of the operator                                                 |
| Timestamp of each message                                                  | traffic monitoring, capacity planning, abuse detection                           | Art. 6(1)(f)                                                                                       |
| Operational/error logs, excluding IP addresses                             | security, troubleshooting                                                        | Art. 6(1)(f)                                                                                       |

**We do not record IP addresses.** The Client stores no network identifier
alongside your questions, and no IP address is written to the session records or
to the application logs. This is a deliberate choice: an IP address would be a
persistent identifier capable of linking your separate sessions together, which
would undo the protection described in section 2.1.

We do **not** ask for your name, e-mail address or any account. We do not build
advertising profiles, we do not sell data, and no automated decision-making
under Article 22 GDPR that produces legal effects for you takes place.

### 2.1 The session identifier, and why we cannot find you

The session identifier is a random value with no connection to your identity, and
**a new one is generated every time a session starts**. It is not stored
persistently, not reused, and never linked to a previous or subsequent session.

The practical consequences are these:

- We cannot recognize you as a returning user.
- We cannot assemble a history or profile of one person across visits. The only
  grouping we can perform is of the questions asked **within a single session**,
  while the application is open in the browser.
- Once your session ends, **no identifier exists anywhere in our systems that
  points to you.** The records become a standalone sequence of questions,
  answers and timestamps, detached from any means of attribution.
- We do not record your IP address (see the note in the table above), so there is
  no network-level identifier that could be used to reconnect the records to you
  or to correlate one session with another.

We nevertheless continue to treat session records as **personal data** rather
than anonymous data, and apply the full GDPR safeguards to them, because the text
of a question can itself reveal who wrote it (for example if you mention your
name, address or circumstances). We chose the cautious classification
deliberately. Its limits are set out honestly in section 5.

**Cookies / local storage.** The session identifier exists only in the memory of
the page / in sessionStorage for the duration of the session and is discarded
when it ends. No persistent cookie or localStorage entry is used for it. To
the extent any browser storage is used, it is strictly necessary for the service
you have requested and is therefore exempt from consent under § 89(3) of Czech
Act No. 127/2005 Coll. and Article 5(3) of Directive 2002/58/EC. If any
analytics or non-essential storage is added, consent must be obtained first.

**Administration Console**

| Data                                                   | Purpose                                        | Legal basis              |
|--------------------------------------------------------|------------------------------------------------|--------------------------|
| Administrator name, e-mail, role, Keycloak identifiers | authentication, access control, accountability | Art. 6(1)(b) and 6(1)(f) |
| Audit log of administrative actions                    | security, traceability of ingestion changes    | Art. 6(1)(c) and 6(1)(f) |

**Customer Content.** Ingested documents may contain personal data. The Customer
decides what is ingested and is the controller for it. Customers are instructed
not to ingest special categories of data (Art. 9 GDPR) without a documented
lawful basis and a prior assessment.

## 3. Where data is processed, and recipients

| Recipient                           | Role                                                           | Location                          | Safeguard                                                                                                        |
|-------------------------------------|----------------------------------------------------------------|-----------------------------------|------------------------------------------------------------------------------------------------------------------|
| Hetzner Online GmbH                 | hosting of the Server                                          | Germany / Finland — EU            | EU/EEA, no transfer                                                                                              |
| OpenAI Ireland Ltd / OpenAI, L.L.C. | generation of answers from the question and retrieved extracts | EU where available; otherwise USA | Data Processing Addendum with EU Standard Contractual Clauses (Decision 2021/914) / EU–US Data Privacy Framework |
| Keycloak                            | administrator authentication                                   | self-hosted on the Server         | no separate transfer                                                                                             |

**Transfers outside the EEA.** Where answers are generated by an OpenAI endpoint
outside the EEA, the transfer relies on the safeguard named above, supported by
a transfer impact assessment. Under the Provider's API terms, submitted data is
**not used to train OpenAI's models**. A copy of the safeguards is available on
request to the contact in section 1.

Data may also be disclosed to public authorities where the Provider is legally
obliged to do so, and to professional advisers under duties of confidentiality.

## 4. How long we keep it

| Data                                                         | Retention                                                                                                                                                                                                                                            |
|--------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Session records (questions, answers, timestamps, session ID) | 90 days, then deleted or irreversibly aggregated into statistics. Deletion is **age-based and applied to all records alike**; because no persistent identifier exists, individual records cannot be singled out for earlier deletion (see section 5) |
| Operational logs (no IP addresses)                           | 30 days                                                                                                                                                                                                                                              |
| Administrator accounts                                       | for the term of the account, plus 6 months                                                                                                                                                                                                           |
| Administrative audit logs                                    | 12 months                                                                                                                                                                                                                                            |
| Customer Content                                             | for the term of the contract, deleted within 30 days of termination                                                                                                                                                                                  |
| Backups                                                      | 30 days rolling                                                                                                                                                                                                                                      |

Retention periods are set by the Customer as controller; the values above are
the Provider's defaults and may be shortened or extended by written instruction.

### 4.1 Storage volume cap

In addition to the time limit above, the administrator configures a **maximum
size for stored session data**. This limit **must not exceed 100 MB** and cannot
be raised beyond that ceiling; the administrator may set any lower value. When
stored data reaches the configured limit, the **oldest records are deleted first**
to stay within it.

The cap therefore acts as a second, independent deletion trigger: records are
removed either when the retention period expires **or** when the volume limit is
reached, whichever happens first. It places a hard upper bound on how much
question text can exist on the Server at any time.

The cap is a volume control, not a substitute for the time limit — at low traffic
a record could remain until the retention period expires. Both mechanisms apply
together.

## 5. Your rights

You have the right to request **access** (Art. 15), **rectification** (Art. 16),
**erasure** (Art. 17), **restriction** (Art. 18), **data portability** (Art. 20),
and to **object** to processing based on legitimate interest (Art. 21). You may
lodge a complaint with a supervisory authority (Art. 77). Exercising these rights
is free of charge, and we will respond within one month.

### Important limitation for anonymous Client users — please read

**We cannot erase your questions on request, and we want to be direct about
that rather than imply otherwise.**

Because the session identifier is regenerated for every session and is not
retained, we hold nothing that connects any stored question to any person. When
you ask us to delete, correct, show or export "your" data, we have no means of
determining which records are yours. There is no lookup we can perform, no
account to match against, and no identifier that survives your session. Asking
us for the identifier afterward does not help, since it no longer exists on our
side as a key to those records.

This means that, in relation to Client session records:

- **Erasure (Art. 17)** — we cannot carry out a targeted erasure. All session
  records are instead deleted automatically when the retention period in section
  4 expires, or sooner when the storage cap in section 4.1 is reached, without any
  request being needed.
- **Access (Art. 15) and portability (Art. 20)** — we cannot retrieve your
  records to provide a copy.
- **Rectification (Art. 16) and restriction (Art. 18)** — we cannot isolate your
  records in order to amend or restrict them.
- **Objection (Art. 21)** — you can stop the processing at any time simply by
  closing the application; no further data about you is collected. We will also
  act on an objection prospectively.

Article 11 GDPR addresses exactly this situation. Where a controller is not in a
position to identify the data subject, Article 11(2) provides that Articles 15 to
20 do not apply, unless you supply additional information enabling
identification. We hold no such information, and **we will not ask you to provide
identifying data merely so that a request can be processed** — collecting more
data about you in order to honor a privacy request would defeat the purpose of
the design. If you are able to demonstrate which records are yours, we will act on
your request.

We consider this an acceptable trade-off, because the same architecture that
prevents us from finding your data also prevents anyone else — including the
operator, our staff, and any future acquirer of the service — from building a
profile of you. **The protection comes from us not holding the data, rather than
from a promise to handle it well.** The corresponding cost is the loss of
targeted erasure, and the practical safeguard is section 14.2 of the EULA: do not
type anything into the question field that you would later want removed.

Your right to lodge a complaint with a supervisory authority under Article 77 is
unaffected, as is your right to a judicial remedy.

**Administrator accounts and Customer Content are different.** Those records are
identifiable, and all rights above can be exercised in full — for administrators
via the Provider, and for personal data inside ingested content via the Customer
as controller.

For Client and Customer Content data, requests are decided by the **Customer** as
controller. Send your request either to the operator identified in the Client or
to the Provider's contact above; the Provider will forward it.

## 6. Security

Measures include encryption in transit (TLS), encryption at rest where
applicable, role-based access control via Keycloak, multifactor
authentication for administrators if enabled, network isolation of the
Server, least-privilege access for Provider personnel bound by confidentiality,
logging of administrative actions, and regular patching and backups.
`[Reference to the full Annex of technical and organisational measures in the
DPA.]`

## 7. Automated content generation

Answers are produced by a large language model and may be inaccurate. No decision
about you is made on the basis of this processing. Under Article 50 of Regulation
(EU) 2024/1689 (AI Act), you are informed that you are interacting with an AI
system; the Client displays this notice.

## 8. Changes

Material changes to this notice will be published in the Client and notified to
Customers at least 30 days in advance. The version and effective date appear at
the top.
