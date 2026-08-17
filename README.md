# CV Builder

CV Builder is an agent-first CLI for creating an editable HTML CV and rendering it as a verified, upload-ready PDF. The CLI provides a neutral default template and handles HTML iterations, Chromium rendering, mechanical checks, the preview, and the stable output filename. The agent writes vacancy-specific content and can apply a supplied or approved design.

It does not invent candidate evidence, contact employers, or submit applications.

## Choose the design first

If you give the agent no visual reference or design instructions, it will use the bundled default design. The result should be mechanically sound, but it will have the default appearance.

For a specific appearance, give the agent one or more of the following before creating application-specific CVs:

- an existing CV or approved baseline;
- a screenshot, image, or PDF showing the desired layout;
- written instructions covering columns, colours, typography, spacing, contact placement, portrait use, density, section structure, and whether section order may change between applications.

The agent should first create and verify one baseline CV, show it to the user, and obtain approval of the design. Design exploration and vacancy tailoring should not happen simultaneously. A baseline is created through the ordinary `new`, deliberate HTML and CSS editing, and `build` flow; it is not a separate CLI feature.

## Reuse the approved design

CV Builder is intended to make repeated job applications faster. Once a baseline design is approved:

1. preserve the approved HTML and CSS;
2. give the agent the exact job offer;
3. give it current authorized candidate evidence and the approved baseline or its path;
4. let it adjust emphasis, summary, and relevant evidence for that vacancy;
5. change section order only when the approved baseline leaves it flexible;
6. keep the established design unless the user explicitly requests a change.

A vacancy tells the agent what to emphasise. It does not tell the agent what is true, so the job offer alone is not sufficient evidence for candidate claims.

CV Builder does not currently remember a personal design between new workspaces. Give the agent the approved baseline or its path when starting another application.

## Give this repository to an agent

Paste this installation request into your agent:

> Install CV Builder from <https://github.com/TobyNoSkillSon/cv-builder>. Before changing anything, briefly explain that you intend to use uv to install an isolated CLI environment, its Python dependencies, and a private Playwright Chromium runtime, then ask for my explicit permission. If uv is unavailable, explain that the installer can instead use Python's standard-library venv and pip, and ask whether I accept that fallback. Do nothing until I approve. After approval, run the repository installer and verify that `cv-builder --help` works. Then manually install the bundled `SKILL.md` into this harness using its documented skill directory; the installer must not modify harness files. Tell me to refresh or restart the harness. After the refresh, load the `cv-builder` skill and confirm that it is visible. Do not create a CV during installation.

## Install the CLI

Clone the repository and run the installer:

```sh
git clone https://github.com/TobyNoSkillSon/cv-builder.git
cd cv-builder
python install.py
```

The installer uses uv when available. Without uv, it creates an isolated environment with the Python standard library's `venv` module and pip. It installs Playwright Chromium into CV Builder's own data directory, creates the `cv-builder` launcher, and verifies the command. It does not install or modify agent skills.

Python 3.11 or newer is required. If the reported launcher directory is not on `PATH`, add it using the normal mechanism for your operating system and restart the shell.

### Install the skill manually

Copy or symlink `SKILL.md` into the current harness's documented skill directory under the name `cv-builder/SKILL.md`. Do not guess among multiple harness profiles. Refresh or restart the harness, then load `cv-builder` to verify that the skill is visible.

## Use

```sh
cv-builder new "Employer" "Role"
cd "Employer-Role"
cv-builder build
```

`new` creates the workspace in the current directory. The normal agent edits are `offer.md` and `cv.html`. `build` preserves the current HTML in `iterations/`, verifies the rendered A4 PDF, overwrites `cv-preview.png`, and atomically updates:

```text
~/Downloads/APPLICANT NAME CV.pdf
```

A viewer-launch failure produces a warning; it does not invalidate or remove the verified PDF.

## Generated workspace

```text
Employer-Role/
├── offer.md
├── cv.html
├── cv.css
├── .cv-builder.json
├── cv-preview.png        # after a successful build
└── iterations/
    ├── cv-001.html
    └── ...
```

The browser runs offline with JavaScript disabled. Build verification checks page geometry, applicant identity, email and telephone links, minimum visible font size, bottom clearance, and suspicious white, transparent, microscopic, or off-page text.

## Uninstall

From the repository checkout:

```sh
python uninstall.py
```

The uninstaller removes only the recorded CV Builder tool environment, launcher, receipt, and private Chromium files. It does not remove the repository, shared browser installations, manually installed skills, or unrelated harness state.

## Tests

```sh
python -m unittest discover -s tests -v
```

The optional live Chromium test is enabled in CI. CV Builder is tested on Python 3.11 and 3.12.

## License

CV Builder is released under the [MIT license](LICENSE).
