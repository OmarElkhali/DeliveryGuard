# Security policy

v0.1.0 is pilot software; no security audit or production certification is claimed.
Only the current v0.1 line is maintained. Do not expose synthetic demo mode publicly
or load company data into it. Company mode requires a strong environment-provided
API key and administrator-managed HTTPS/network restrictions.

Do not post credentials, company records or exploitable details in public issues.
For a vulnerability, use the repository's private GitHub vulnerability reporting
if the maintainer enables it. No monitored security inbox or guaranteed response
SLA is claimed. If private reporting is unavailable, open only a generic contact
request without sensitive details, then agree on a private channel. No report is
sent by this application.

Do not load untrusted joblib/pickle models or replace local artifacts with external
ones. There is no model upload endpoint. Treat filesystem/DB/Docker access as
privileged. Keep backups and volumes private, rotate leaked keys and passwords,
and check dependency updates before operating a real pilot. See
[operations](docs/operations.md) for rotation and backup guidance.
