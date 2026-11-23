# AFIP Nuevo

Python automation for AFIP/ARCA, Arancia/Bookit, Newsan and Gmail invoice review.
The canonical setup guide and command reference are in [README.md](README.md).

With Python 3.11 installed, run `py -3.11 setup_env.py` on Windows or
`python3.11 setup_env.py` on macOS/Linux. This creates `.venv`, installs the exact
package versions in `requirements-lock.txt`, checks dependencies and downloads
Chromium. It creates `.env` from the template only when missing; fill in credentials
locally. Install commit checks using the new environment's Python with
`python -m pre_commit install --install-hooks`.
The secret check also requires the official Gitleaks executable on `PATH`;
see the main README for the version and alternative local path.

The repository no longer tracks Python environments, credentials, OAuth tokens
or invoice documents. These files must be configured or transferred privately
on each computer. Invoice issuing requires explicit `--fecha`, `--desde` and
`--hasta` dates in `DD/MM/YYYY` format and confirms them before issuing.
The default point of sale is `2`; its minimum dates are `31/10/2026` for A and
`30/10/2026` for B invoices.
Consumer-final exports containing `Monto (ARS)`, `Razon Social`, `categoria`,
`Column 10`, and `DOC` are locked to invoice B, point of sale 2, ARS, and
`30/10/2026`. November dates are rejected before opening ARCA and rechecked before
the final confirmation. Explicitly rejected documents are recorded as skipped and
the batch continues.
`--solo-revisar` validates the first row in ARCA without issuing it. A local journal
under `~/Downloads/AFIP_Facturas` prevents duplicate retries after confirmation.

**Credentials exist in older commits. Rotate the AFIP, Arancia and PGA passwords
before reuse. This branch does not erase Git history.** See [SECURITY.md](SECURITY.md).
