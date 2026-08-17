---
name: cv-builder
description: Create, edit, render, verify and visually review a CV through the minimal cv-builder CLI.
---

# CV Builder

## Purpose

Use `cv-builder` for the deterministic mechanics of a CV: workspace creation, HTML iteration snapshots, Chromium PDF rendering, PDF safety checks, a visual PNG preview, a stable upload-ready filename, and opening the result.

The CLI does not invent candidate facts or decide which claims are truthful. The active agent must use the candidate's authorized evidence and the saved vacancy text.

## Installation

Install the package and Chromium once:

```bash
python -m pip install -e /path/to/cv-builder
python -m playwright install chromium
```

## Commands

The normal interface has two commands and no workflow flags:

```bash
cv-builder new "Employer" "Role"
cd "Employer-Role"
cv-builder build
```

Run `cv-builder build` again after every revision.

## Workspace

`new` creates:

```text
Employer-Role/
├── offer.md
├── cv.html
├── cv.css
├── .cv-builder.json
└── iterations/
```

Normal agent edits are limited to:

- `offer.md` — replace its marker with the vacancy text so reviewers receive the same source context.
- `cv.html` — replace every `[[PLACEHOLDER]]`, remove irrelevant optional blocks, and write only evidence-supported content.

Do not edit `.cv-builder.json` or `cv.css`; both are generated CLI-owned files. Correct reusable layout defects in the packaged template rather than creating an application-specific stylesheet fork.

## Build behavior

Run `cv-builder build` from the application directory. It:

1. Rejects an unsaved vacancy marker, unresolved `[[PLACEHOLDERS]]`, unsafe source paths, scripts, inline event handlers, embedded active content, and remote media or stylesheet resources.
2. Copies the exact current `cv.html` to the next file in `iterations/`, such as `cv-001.html`.
3. Renders the current HTML to A4 PDF with JavaScript disabled and the browser context offline.
4. Verifies the applicant name, page count, selectable text geometry, email/phone links, bottom clearance, minimum font size, and fully transparent, pure-white, microscopic, or geometrically off-page text spans.
5. Overwrites `cv-preview.png` for visual inspection.
6. Atomically overwrites `~/Downloads/APPLICANT NAME CV.pdf`.
7. Opens the PDF with the platform viewer.

A failed render or verification never replaces the Downloads PDF.

## Visual review

Inspect `cv-preview.png` after each successful build. Check clipping, conspicuous under-fill, excessive density, weak hierarchy, repeated claims, and awkward wrapping. Mechanical verification is not editorial approval.

## Iteration and rollback

Each build preserves only the HTML source used for that attempt:

```text
iterations/
├── cv-001.html
├── cv-002.html
└── ...
```

To roll back, copy the chosen iteration over `cv.html`, review it, and run `cv-builder build` again. CSS is intentionally stable; HTML-only rollback is exact only while `cv.css` remains unchanged.

## Boundaries

- Never invent employment, metrics, skills, credentials, language certification, or responsibility.
- Never add invisible, white, transparent, microscopic, metadata-only, or off-page recruiter instructions.
- Never add scripts, inline event handlers, embedded active content, tracking resources, or remote media/stylesheets.
- Keep ordinary semantic headings, selectable text, and real `mailto:` and `tel:` links.
- The CLI only creates local artifacts. It does not submit applications, contact employers, or mutate accounts.
