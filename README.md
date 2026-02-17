# Alberto Jaramillo-Jimenez - Personal Website
https://alberto-jj.github.io

This website started from the original **Hacker - Free Portfolio Website Template**, but has been **extensively modified and adapted**. The current version includes substantial layout and styling changes and an automated publications feed generated from ORCID via Crossref.

---

## Credits

Base template:

**Hacker - Free Portfolio Website Template**  
Created by OSSPH  
https://ossph.org

This repository contains a heavily modified and extended implementation built on top of that original structure.

---

## Major Modifications in this Fork

- Reworked layout and navigation
- Custom terminal-style section labels and interactions
- Styling and UI adjustments (Vue/Vuetify)
- Publications section fed from an auto-generated `publications.json`
- Added ORCID -> Crossref publications parser (`scripts/build_publications.py`)
- Added GitHub Actions workflow to keep publications updated automatically

---

## Publications Feed (ORCID -> Crossref)

The website reads publications from:

- `publications.json` (generated file)

That file is produced by a script that queries Crossref using the ORCID iD, extracts title/authors/year/journal, cleans formatting (for example HTML entities like `&amp;`), and outputs a JSON list consumed by the frontend.

### Automatic updates (recommended)

`publications.json` is refreshed automatically by **GitHub Actions**:

- Runs weekly (cron)
- Can also be triggered manually via **workflow_dispatch**
- Commits and pushes updates only when `publications.json` changes

Workflow file:

- `.github/workflows/update_publications.yml`

### Run locally (optional)

```bash
python -m pip install --upgrade pip
pip install requests
python scripts/build_publications.py
```
