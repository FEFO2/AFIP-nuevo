# AFIP Nuevo

Python automation for AFIP/ARCA, Arancia/Bookit, Newsan and Gmail invoice review.
The canonical setup guide and command reference are in [README.md](README.md).

Use Python 3.11, create a local virtual environment, install `requirements-dev.txt`
and run `python -m playwright install chromium`. Copy `.env.example` to `.env`
and fill in credentials locally. Install commit checks with
`python -m pre_commit install --install-hooks`.
The secret check also requires the official Gitleaks executable on `PATH`;
see the main README for the version and alternative local path.

The repository no longer tracks Python environments, credentials, OAuth tokens
or invoice documents. These files must be configured or transferred privately
on each computer. Invoice issuing now requires an explicit `--fecha DD/MM/YYYY`.

**Credentials exist in older commits. Rotate the AFIP, Arancia and PGA passwords
before reuse. This branch does not erase Git history.** See [SECURITY.md](SECURITY.md).
