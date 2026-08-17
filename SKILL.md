---
name: cv-builder
description: Create, tailor, render, verify and visually review an evidence-backed, upload-ready CV through the minimal cv-builder CLI. Use for vacancy-specific CV work, HTML-to-PDF iteration, safety checks, rollback and acceptance review.
---

# CV Builder

## Purpose

Use `cv-builder` for the deterministic mechanics of a CV: workspace creation, HTML iteration snapshots, Chromium PDF rendering, PDF safety checks, a visual PNG preview, a stable upload-ready filename, and opening the result.

The CLI does not invent candidate facts or decide which claims are truthful. The active agent must use the candidate's authorized evidence and the saved vacancy text.

## Recommended workflow gates

Use this external editorial checklist around the CLI. These states are not stored or enforced by `cv-builder`:

```text
draft -> mechanically verified -> reviewer-ready -> user-approved -> delivered
```

A successful build advances only the mechanical state. It does not make the wording true, the design persuasive, or the document approved.

Before the first build, as recommended editorial discipline:

1. **Lock the evidence and vacancy.** Save the exact job description. Map every intended claim to a primary record or current direct confirmation. Prefer current primary evidence over summaries, previous CV wording, reviewer assumptions, and phrases copied from the vacancy. Confirm dates, titles, durations, metrics, credentials, language levels, authorship, contribution boundaries, and publication status when they affect recruiter inference.
2. **Lock the copy.** Review the unstyled text in final reading order. Use concrete verbs and specific evidence. Remove repetition, unsupported keywords, inflated seniority, defensive audit language, and qualifications that do not materially change the claim. Clearly distinguish direct work, team support, and tool-assisted execution.
3. **Lock the visual direction.** Confirm that the copied template's hierarchy, density, column structure, contact placement, portrait policy, and minimum legibility fit the intended CV. If a materially different layout is required, stop and request approval for a separate, versioned CSS or packaged-template change before resuming vacancy-specific copy. Do not infer repository-mutation authority from an application-tailoring request, and do not interleave basic information-architecture discovery with content edits.

After those gates, make one integrated revision and build it. Reopen an earlier gate when a later change alters facts, contribution boundaries, publication status, reading order, or the approved visual premise.

## Installation

Before installing or updating the CLI, briefly explain that installation will create an isolated uv tool environment, install Python dependencies and a private Playwright Chromium runtime, and expose a `cv-builder` launcher. Ask the user for explicit permission and do nothing until approved. If uv is unavailable, disclose the standard-library `venv` and pip fallback before proceeding.

From the repository, run:

```bash
python install.py
```

The installer changes only CLI package/runtime state. Install this skill manually through the current harness's documented skill mechanism, then ask the user to refresh or restart the harness and load `cv-builder` to verify visibility.

To remove the CLI runtime without touching the repository, shared browsers, or manually installed skills:

```bash
python uninstall.py
```

## Commands

The normal interface has two commands and no workflow flags:

```bash
cv-builder new "Employer" "Role"
cd "Employer-Role"
cv-builder build
```

Run `cv-builder build` after each integrated revision that is ready for mechanical and visual review. Do not render repeatedly while facts, copy, or the basic design premise are still unresolved.

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

Normal vacancy-specific edits are:

- `offer.md`: replace its marker with the vacancy text so later review uses the same source context.
- `cv.html`: replace every `[[PLACEHOLDER]]`, remove irrelevant optional blocks, and write only evidence-supported content.

Do not edit `.cv-builder.json`; it is CLI-owned configuration. `new` copies the packaged `cv.css` into the workspace once, and `build` reads the current workspace CSS without regenerating or snapshotting it. Keep CSS stable during ordinary content iterations. If a design change genuinely requires CSS, preserve or version that CSS separately and review it as a deliberate design change. Reusable theme fixes belong in the packaged template, but template maintenance is a repository task rather than a public CLI command.

## Build behavior

Run `cv-builder build` from the application directory. It:

1. Requires non-symlink regular files for `offer.md`, `cv.html`, and `cv.css`; rejects an unsaved vacancy marker, unresolved `[[PLACEHOLDERS]]`, scripts, iframes, objects, embeds, base elements, inline event handlers, remote `src` values on media elements, and remote `@import` or `url(...)` resources in `cv.css`.
2. Copies the exact current `cv.html` to the next file in `iterations/`, such as `cv-001.html`.
3. Renders the current HTML to A4 PDF with JavaScript disabled and the browser context offline.
4. Checks the applicant name, one-page output, PyMuPDF-extracted text geometry, the presence of at least one `mailto:` and one `tel:` PDF link, bottom clearance, minimum font size, and extracted spans that are fully transparent, pure white, microscopic, or geometrically off-page.
5. Overwrites `cv-preview.png` for visual inspection.
6. Atomically overwrites `~/Downloads/APPLICANT NAME CV.pdf`.
7. Attempts to open the PDF with the platform viewer.

Snapshotting happens before rendering and verification, so a failed attempt still consumes an HTML iteration number and preserves that attempted source. A failed render or verification never replaces the Downloads PDF. A missing viewer, file association, `xdg-open`, or graphical session produces a warning only: the verified PDF remains successfully built and can be opened manually from the reported path.

## Visual and editorial review

Inspect `cv-preview.png` and the opened PDF after each successful build. Extracted text and page count cannot prove that the rendered page is visually sound. Check:

- clipping, missing paint, unintended blank regions, and off-page content;
- conspicuous under-fill, excessive density, weak hierarchy, and awkward wrapping;
- contact readability, section balance, date alignment, and consistent spacing;
- whether the most relevant evidence is visible in a quick recruiter scan;
- repeated claims, synthetic wording, unsupported implications, and link destinations.

When optional external review is useful, freeze one candidate: do not mutate its source or artifacts while it is being reviewed. Give the reviewer the saved vacancy and underlying evidence, then classify findings consistently:

- **BLOCKED:** a factual, functional, or materially misleading presentation defect;
- **READY:** no blocker remains;
- **OPTIONAL:** taste or future improvement that must not trigger another revision automatically.

Verify review claims against the actual source, PDF, and preview rather than treating agreement as proof. Manually check that visible contact details match the `mailto:` and `tel:` destinations and that every public link supports the implication made by the CV. Mechanical verification and external review readiness are not user approval.

## Iteration and rollback

Each build preserves only the HTML source used for that attempt:

```text
iterations/
├── cv-001.html
├── cv-002.html
└── ...
```

To roll back, copy the chosen iteration over `cv.html`, review it, and run `cv-builder build` again. CSS is intentionally stable; HTML-only rollback is exact only while `cv.css` remains unchanged.

The iteration number is mechanical history, not an approval state. Keep disposable copy or layout experiments outside the application workspace when possible, and call `build` only when a complete revision is ready for mechanical review. Once called, the attempt enters history even if rendering or verification fails. Preserve a user-approved artifact before reopening it for a new requirement.

## Acceptance and delivery

Before calling a CV final:

1. verify the rendered candidate and all links;
2. separate blockers from optional taste;
3. obtain explicit user approval of the actual candidate;
4. confirm the reported Downloads path contains the approved bytes;
5. keep submission, account mutation, repository publication, and employer contact as separately authorized actions.

If no blocker remains and the user accepts the candidate, stop. A passing build, positive review, or optional suggestion does not independently authorize another revision.

## Boundaries

- Never invent employment, dates, metrics, skills, credentials, language certification, seniority, responsibility, public-source status, or unaided authorship.
- A vacancy changes selection and emphasis, not the underlying facts.
- Do not add age, birth date, portrait, marital status, or other demographic information unless the user explicitly approves it and the application context genuinely requires it.
- Use plain recruiter-facing language. Prefer concrete actions and outcomes over compliance vocabulary, inflated abstractions, or keyword-shaped prose.
- Keep material limitations visible when omitting them would mislead, but do not make defensive disclaimers the visual centre of the document.
- Never add invisible, white, transparent, microscopic, metadata-only, or off-page recruiter instructions.
- Never add scripts, inline event handlers, embedded active content, tracking resources, or remote media/stylesheets.
- Keep ordinary semantic headings, selectable text, and real `mailto:` and `tel:` links. Verify every public link and ensure its destination supports the implication made by the CV.
- The CLI only creates local artifacts. It does not submit applications, contact employers, publish repositories, or mutate accounts.
