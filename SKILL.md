---
name: cv-builder
description: Create, edit, render, or review a vacancy-specific CV with the cv-builder CLI, using authorized evidence and an approved design baseline. Use for CVBuilder workspaces, HTML/CSS CVs, PDF builds, previews, or claim and link checks.
---

# CV Builder

Use `cv-builder` for workspace and PDF mechanics. Use the active agent and the user for evidence selection, truthful wording, design judgment, review, and approval. The [README](README.md) has the detailed interface and installation reference; `cv-builder --help` has the installed command summary.

## Workflow

1. Frame the application. Load the exact vacancy, the authorized evidence for the candidate, and the design baseline. The baseline may be the bundled neutral template, a supplied reference, or an already approved HTML/CSS workspace. Map each material claim to evidence before writing it.

   Completion: the vacancy source, evidence set, and design baseline are identified, and the intended claims have support.

2. Create or reuse a workspace. For a new application, run this from its parent directory:

   ```sh
   cv-builder new "Employer" "Role"
   ```

   `new` refuses to overwrite an existing path and creates a normalized `Employer-Role/` directory containing `offer.md`, `cv.html`, `cv.css`, `.cv-builder.json`, and an empty `iterations/` directory. Reuse an existing workspace only when its vacancy, evidence, and design baseline are the intended ones. Run later commands from the application directory.

   Completion: the application directory is selected and its CLI-owned configuration and required source files are present.

3. Edit complete sources. Replace the marker in `offer.md` with the saved vacancy. Complete `cv.html` and `cv.css` for the approved baseline and vacancy emphasis. Remove every `[[PLACEHOLDER]]`; put the applicant name in `h1 data-cv-applicant`; and provide real `mailto:` and `tel:` links. Keep `.cv-builder.json` under CLI control. Use authorized evidence for every factual claim, contribution boundary, date, metric, credential, and public link.

   Completion: `offer.md`, HTML, and CSS are complete, locally usable, evidence-backed, and ready for one integrated build.

4. Build the candidate.

   ```sh
   cv-builder build
   ```

   `build` snapshots the exact current `cv.html` as the next `iterations/cv-NNN.html`. It does not snapshot CSS. It renders a local A4 PDF with JavaScript disabled in an offline browser context, verifies the PDF, writes `cv-preview.png`, atomically replaces `~/Downloads/APPLICANT NAME CV.pdf`, and attempts to open that PDF. A viewer warning leaves the built PDF available at the reported path.

   Source validation happens before snapshotting. After a snapshot is written, a render or verification failure still consumes that iteration and preserves the attempted HTML, while the previous Downloads PDF remains in place.

   Completion: the command succeeds and reports the iteration, HTML snapshot, PDF, preview, hash, page report, and links.

5. Inspect the result. Review both `cv-preview.png` and the PDF. Check reading order, clipping, whitespace, density, hierarchy, wrapping, contact details, and the relevance of visible evidence. Verify every claim against the authorized evidence and check that visible contact details match the `mailto:` and `tel:` destinations. Check each public link against the implication made by the CV.

   The built-in checks cover one A4 page, the applicant name in the first 400 extracted characters, `mailto:` and `tel:` links, at least 10 mm bottom clearance, text of at least 7.5 pt, and suspicious extracted spans that are transparent, white, microscopic, or outside the page. They leave visual quality, link destinations, truth, claim support, ATS suitability, and submission readiness to inspection and human judgment.

   Completion: the build passes, the preview and PDF have been inspected, and factual, functional, and material presentation blockers are resolved.

6. Obtain user approval. Show the actual candidate and get explicit approval for that candidate, rather than treating a passing build or review as approval. If a later change alters evidence, wording, reading order, or the design baseline, return to the affected steps and build again.

   Completion: the user has approved the exact candidate under review.

7. Preserve the artifact and stop at the boundary. Keep the approved workspace, HTML snapshot, CSS, preview, and approved PDF. Confirm that the reported Downloads path contains the approved PDF, using the reported hash when useful. Submission, account changes, repository publication, and employer contact each require separate authorization.

   Completion: the approved artifact is preserved and no external submission or account action has been inferred from CV approval.

## Installation authority

CLI installation and optional harness-skill installation are separate actions. Obtain approval for each before mutating state.

From the repository checkout, `python install.py` installs the CLI into an isolated `uv tool` environment when `uv` is available, otherwise a standard Python `venv` with `pip`; it installs dependencies and CV Builder's private Chromium runtime. It changes CLI/runtime state only. It does not install this skill or modify harness files. Install `cv-builder/SKILL.md` separately through the current harness's documented skill mechanism, then refresh or restart the harness and verify that the skill is visible.

`python uninstall.py` reads the install receipt and removes the recorded CLI environment, owned launcher, receipt, and private Chromium files. It validates recorded paths and launcher ownership before removal, delegates `uv` cleanup to the recorded executable when applicable, and leaves the repository, shared browsers, manually installed skills, and unrelated files alone. A failed safety check leaves the relevant state in place. See the [README](README.md) for path overrides and installer details.

## Iteration rollback

To roll back, copy the chosen `iterations/cv-NNN.html` over `cv.html`, inspect it, and run `cv-builder build` again. The rollback is exact for HTML only while `cv.css` is unchanged. An iteration records the source used for an attempt, not an approval state.
