# CV Builder

CV Builder is a small Python CLI that creates editable HTML CV workspaces, renders them to one-page PDFs, and performs bounded PDF checks. It uses the bundled neutral HTML/CSS template unless you edit the workspace.

The CLI handles document mechanics. It does not decide whether a statement is true, whether the writing is good, whether a layout suits an ATS, or whether a CV is ready to submit.

## Requirements

- Python 3.11 or newer
- Playwright and PyMuPDF, installed by the repository installer
- Chromium, installed into CV Builder's private data directory

The package metadata pins Playwright to `>=1.49,<2` and PyMuPDF to `>=1.24,<2`.

## Install

Run the installer from a checkout, with permission to create the local CLI environment and download its private Chromium runtime:

```sh
git clone https://github.com/TobyNoSkillSon/cv-builder.git
cd cv-builder
python install.py
```

The installer prefers `uv tool`. If `uv` is unavailable, it creates a Python `venv` and uses `pip`. It installs the package, dependencies, and Chromium, then checks that `cv-builder --help` runs. It records the installation so the uninstaller can remove the same paths.

The installer itself does not grant permission or install a skill. It changes CLI/runtime state only. By default, private data is stored under `~/.local/share/cv-builder` on Unix-like systems and the launcher is placed under `~/.local/bin`. `CV_BUILDER_HOME` and `CV_BUILDER_BIN_DIR` can override those locations. Add the launcher directory to `PATH` if the installer reports that it is missing, then restart the shell.

### Optional skill installation

`SKILL.md` is separate from the CLI. If you use a harness with a skill mechanism, install it separately through that harness's documented procedure as `cv-builder/SKILL.md`, then refresh or restart the harness. Do this only if you want the accompanying workflow guidance; the CLI does not require it, and the installer does not modify harness files.

## Commands

The command-line interface has two subcommands:

```text
cv-builder new EMPLOYER ROLE
cv-builder build
```

Run `cv-builder --help` for the installed command summary.

### `new`

```sh
cv-builder new "Employer" "Role"
```

Run this in the directory that should contain the application. `new` creates a normalized `Employer-Role/` directory and refuses to overwrite an existing path. It writes:

```text
Employer-Role/
├── offer.md
├── cv.html
├── cv.css
├── .cv-builder.json
└── iterations/
```

`offer.md` contains the vacancy heading and `[[PASTE_JOB_DESCRIPTION_HERE]]`. `cv.html` and `cv.css` are copies of the packaged default template. `.cv-builder.json` stores the employer, role, and configuration schema. `iterations/` starts empty. The command reports the new absolute path and the files normally edited.

Before building, replace the marker in `offer.md` with the vacancy text. Edit `cv.html` for the CV content and edit `cv.css` when changing its design. Remove every `[[PLACEHOLDER]]` from the HTML. Keep `.cv-builder.json` under CLI control. The HTML must contain the applicant's name in an `<h1 data-cv-applicant>` element and should contain real `mailto:` and `tel:` links, because the PDF checks require both link types.

### `build`

Run it from an application directory:

```sh
cd "Employer-Role"
cv-builder build
```

`build` performs these steps:

1. Reads `.cv-builder.json` and requires regular, non-symlink files named `offer.md`, `cv.html`, and `cv.css`.
2. Rejects an empty vacancy or the vacancy marker, unresolved HTML placeholders, active or embeddable HTML (`script`, `iframe`, `object`, `embed`, or `base`), inline event handlers, remote media, and remote CSS resources.
3. Copies the exact current `cv.html` to the next file in `iterations/`, such as `iterations/cv-001.html`. CSS is not copied.
4. Renders the current HTML with Chromium as an A4 PDF.
5. Verifies the PDF. Details are below.
6. Replaces `cv-preview.png` with a PNG of the first PDF page.
7. Atomically replaces the PDF in `~/Downloads`.
8. Attempts to open that PDF with the platform's default viewer.

A successful command reports the iteration number, snapshot path, PDF path, preview path, SHA-256 hash, page report, and extracted links. A viewer failure is a warning after the PDF has been built; open the reported path manually.

The snapshot is written before rendering and verification. A failed build therefore consumes an iteration number and preserves the attempted HTML, but it does not replace the previous Downloads PDF. Temporary render files are removed.

## Verification contract and limits

The PDF verification checks:

- exactly one page;
- A4 page dimensions within the implementation tolerance;
- the applicant name in the first 400 characters of extracted PDF text;
- at least one `mailto:` link and one `tel:` link in the PDF;
- at least 10 mm of bottom clearance;
- no extracted text span smaller than 7.5 pt;
- no extracted text span that is transparent, pure white, or outside the page bounds.

These checks use Chromium output and PyMuPDF text and geometry extraction. They do not prove that the visible design is attractive or readable, that links go to the right destinations, that the wording is truthful, that claims are supported, that the CV is suitable for an ATS, or that it is ready for submission. Inspect `cv-preview.png` and the PDF yourself, and check the visible contact details and link destinations.

### Offline rendering

Chromium renders a local HTML file in an offline browser context with JavaScript disabled. The page therefore needs to work with its HTML and local CSS alone. Scripts do not run, network resources cannot be fetched, and source validation rejects active content and remote resources. This is intentional: the PDF should not depend on a network connection or JavaScript side effects.

## Tailoring and design

Save the exact vacancy in `offer.md` and use current, authorized evidence for the applicant. Adapt emphasis and ordering only where the evidence supports it. A vacancy can change what is prominent; it cannot establish a new fact.

Use the bundled template as the default design. If a supplied CV, screenshot, PDF, or written specification is the design reference, make the required HTML/CSS changes first and review one built result. For later applications, keep the approved HTML/CSS baseline and change the vacancy-specific content deliberately. Review both the PDF and preview after each successful build. Design review and factual review remain human decisions outside the CLI.

## Uninstall

Run this from the repository checkout:

```sh
python uninstall.py
```

The uninstaller reads the install receipt and removes the recorded CLI environment, its owned launcher, the receipt, and CV Builder's private Chromium files. It refuses unexpected paths and refuses to remove an unowned launcher. With a `uv` installation it delegates environment removal to the recorded `uv` executable before cleaning up remaining owned files.

It does not remove the repository, shared browser installations, manually installed skills, or unrelated files. If no installation receipt exists, it reports that there is nothing to remove. A failed safety check leaves the relevant files in place.

## Tests

Run the unit tests with:

```sh
python -m unittest discover -s tests -v
```

The live Chromium render test is enabled in CI with `CV_BUILDER_LIVE_RENDER=1`. CI runs the suite on Python 3.11 and 3.12 and builds the package.

## License

CV Builder is released under the [MIT License](LICENSE).
