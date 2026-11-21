# Security, accessibility, ethical limits and future work

## Controls already implemented

- Type and length validation with Pydantic; allow-listed workflow actions and explicit transitions.
- Signed same-site HTTP-only staff-session cookies; mandatory role + CSRF checks for officer status mutations and image uploads.
- Demo staff login with per-IP in-process failed-login throttling (12 attempts in 10 minutes).
- Content Security Policy and anti-sniff, frame-deny and referrer headers.
- Report descriptions rendered as escaped HTML strings in the client.
- Uploads limited to JPEG/PNG/WebP with header bytes checked, maximum 2MB, unpredictable filenames.
- No external model calls, no hardcoded commercial API keys and no personal contact fields required.
- pytest checks for unauthorized state changes and disguised media files.

## Unresolved risks (must fix before real municipal use)

1. **Public demonstration credentials**. Both accounts use a shared known password for judges. An openly deployed demo is writable by attendees; it is *not* safe for real case management. For a real organization, disable `DEMO_MODE`, implement proper identity provider, per-officer permissions and secure account recovery. Set `SESSION_SECRET` and secure cookies.
2. **Reporter verification is alias-based**. Anyone claiming the original reporter's alias may dispute/confirm a case. Production requires cryptographically verified report ownership and an appeals/review process.
3. **Spam and misinformation**. Rate limits currently only cover repeated failed staff login; public reporting and corroboration are not reliably anti-bot protected. Add network-aware rate limiting, abuse detection, content moderation and duplicate-review queues.
4. **Public data exposure**. Reports and aliases are readable publicly. Real launch requires minimization, consent, data retention, redaction of sensitive text, private reports when needed and publication review.
5. **Storage**. Filesystem uploads and SQLite are temporary on many free hosts. Replace with durable database/media storage, backups and secure access controls.
6. **Safety judgment**. Keyword rules cannot determine true emergency severity or reliably identify all languages, hazards and contexts. Human validation and emergency escalation channels are mandatory.
7. **Bias/fairness**. Token matching, limited Tamil examples, ward selection and unverified reports may systematically under-detect some communities. The capped popularity term is a design guardrail, **not evidence of fair impact**.
8. **Audit protection**. Event timelines are persisted but not tamper-evident or independently verified. Add append-only audit storage and administrator accountability.
9. **Testing scope**. API workflow tests pass, but cross-browser manual testing, load testing, accuracy calibration, penetration testing and assistive-tech audits have not been completed.

## Accessibility features included

- Semantic form labels and `aria-label`s on key icon buttons.
- Keyboard-accessible incident cards and visible focus outlines.
- Live-region success/error notices and status messages.
- Responsive sidebar and content, mobile-friendly card layout.
- Reduced-motion media query.

More robust focus trapping in dialogs, automated WCAG audits and screen-reader testing would be required for launch.

## Real-world roadmap

1. Authenticated citizen identities, proper municipal staff provisioning and case ownership.
2. Privacy-by-design, encrypted object storage, notifications and consent/retention management.
3. Expert-reviewed ML training data across languages and civic services; calibrated confidence and accuracy metrics.
4. Reliable location and multimodal evidence analysis with spoofing safeguards.
5. Formal SLAs, appeals, case reopening quorum and multi-reporter feedback policies.
6. Integration with municipality routing systems, anonymized open dashboards and independent audits.

> This is an educational hackathon prototype. It must not be marketed or relied on as a live official government or emergency service.
