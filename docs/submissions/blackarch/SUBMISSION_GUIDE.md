# Conduit-Browser: BlackArch Linux Submission Guide

This guide walks through every step required to get `conduit-browser` accepted
into the BlackArch Linux repository. Read it end-to-end before starting; the
BlackArch team is strict and incomplete submissions are closed without comment.

---

## What is BlackArch?

BlackArch is an Arch Linux-based distribution and package overlay aimed at
penetration testers and security researchers. Packages live in the
`blackarch/packages/` tree on GitHub and are built by the BlackArch CI system
from PKGBUILD files. Acceptance criteria:

- The tool must have genuine security research utility.
- The PKGBUILD must build cleanly in a clean Arch chroot.
- The `sha512sums` field must be real (never `SKIP` in a final PR).
- Groups must include at least one `blackarch-*` sub-group.

---

## Step 1 — Prerequisites

You need a working Arch Linux environment (VM, container, or bare metal).

```bash
# Install build tools
sudo pacman -S base-devel python python-pip git

# Install BlackArch keyring (if using a plain Arch install)
curl -O https://blackarch.org/strap.sh
chmod +x strap.sh
sudo ./strap.sh
```

---

## Step 2 — Fork the BlackArch Repository

1. Go to https://github.com/BlackArch/blackarch
2. Click **Fork** (top-right).
3. Clone your fork locally:

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/blackarch.git
cd blackarch
```

---

## Step 3 — Create the Package Directory

BlackArch stores one package per directory under `packages/`.

```bash
mkdir packages/conduit-browser
cp /path/to/this/PKGBUILD packages/conduit-browser/PKGBUILD
```

The directory name **must** match `pkgname` exactly: `conduit-browser`.

---

## Step 4 — Generate the Real sha512sum

The PKGBUILD ships with `sha512sums=('SKIP')` as a placeholder.  Before
submitting, replace it with the real checksum.

```bash
cd packages/conduit-browser

# Download the source tarball
makepkg --nobuild --noprepare

# Generate the checksum
makepkg -g
# Output looks like:
# sha512sums=('abc123...longstring...')

# Paste that line into PKGBUILD, replacing the SKIP line
```

Alternatively, compute it manually:

```bash
curl -L -o conduit-browser-0.2.1.tar.gz \
  https://github.com/bkauto3/Conduit/archive/refs/tags/v0.2.1.tar.gz
sha512sum conduit-browser-0.2.1.tar.gz
```

---

## Step 5 — Test the Build in a Clean Chroot

BlackArch CI builds in a clean chroot. You must replicate this locally before
submitting. A dirty host environment will produce a PKGBUILD that passes on
your machine but fails in CI.

### Option A — devtools (recommended)

```bash
# Install devtools
sudo pacman -S devtools

# Build in a clean chroot
mkarchroot /tmp/archroot base-devel
cd packages/conduit-browser
makechrootpkg -c -r /tmp/archroot
```

### Option B — plain makepkg (quicker, less accurate)

```bash
cd packages/conduit-browser
makepkg -si --cleanbuild
```

A successful build produces a `.pkg.tar.zst` file in the directory.  Verify
the installed files look correct:

```bash
# List files installed by the package
tar -tvf conduit-browser-*.pkg.tar.zst | head -40
```

Expected to see:
- `usr/lib/python3.x/site-packages/` — Python modules
- `usr/share/licenses/conduit-browser/LICENSE`
- `usr/bin/conduit` (if the entry point script installed)

---

## Step 6 — Validate the Installed Tool

After `makepkg -si`, confirm the tool is functional:

```bash
# Verify the package installed
pacman -Qi conduit-browser

# Run a basic smoke test
python -c "import audit; import tools.conduit_proof; print('imports OK')"

# If an entry-point script was installed:
conduit --help
```

---

## Step 7 — Commit and Push

```bash
cd /path/to/blackarch-fork

git checkout -b add-conduit-browser
git add packages/conduit-browser/PKGBUILD
git commit -m "Add conduit-browser: headless browser with cryptographic audit trails"
git push origin add-conduit-browser
```

Commit message conventions BlackArch uses:
- `Add <pkgname>: <one-line description>`
- No period at the end.
- Keep it under 72 characters.

---

## Step 8 — Open the Pull Request

Go to your fork on GitHub and open a PR against `BlackArch/blackarch:master`.

**PR Title:**
```
Add conduit-browser: headless browser with cryptographic audit trails
```

**PR Body — copy/paste template:**

```
## New Tool: conduit-browser

**Description:**
Headless browser with SHA-256 hash-chained audit trails and Ed25519-signed
proof bundles. Every browser action (navigate, click, fill, eval, screenshot,
PDF) is written to a tamper-evident SQLite log whose entries chain via
SHA-256 so any deletion or modification is detectable. The tool exports
self-verifiable `.tar.gz` proof bundles containing a stdlib-only `verify.py`
that a recipient can run without installing conduit-browser itself.

**Security research relevance:**
- Document web vulnerabilities with cryptographic evidence that survives
  chain-of-custody scrutiny
- `eval` action stores the full JavaScript source verbatim in the audit chain
  — proof of exactly what code executed, not just its output
- Forensic session replay: every action is signed with Ed25519; replays are
  byte-for-byte reproducible
- SSRF protection built in — RFC-1918 and loopback addresses are blocked at
  the navigation layer, making it safe to point at untrusted targets
- Evidence collection for incident response workflows
- MCP server interface for integration with AI agent pipelines (Claude, GPT,
  etc.) during automated security assessments

**Groups:** blackarch-webapp, blackarch-forensics

**License:** MIT
**Source:** https://github.com/bkauto3/Conduit
**PyPI:** https://pypi.org/project/conduit-browser/
**Version:** 0.2.1

**Build tested on:** Arch Linux (kernel 6.x, Python 3.12, clean chroot via devtools)
```

---

## Step 9 — Respond to Maintainer Feedback

BlackArch maintainers commonly request:

| Issue | Fix |
|---|---|
| `sha512sums=SKIP` left in | Replace with real checksum (Step 4) |
| Binary in package tree | Use approach 2 in the PKGBUILD NOTE (system Chromium) |
| Missing `checksum` for patchright Chromium download | Add a dedicated `source+=` entry for the browser tarball |
| Group spelling | Must be `blackarch-webapp`, not `blackarch-web-app` |
| `pkgrel` bump | Change `pkgrel=1` to `pkgrel=2` if they ask for a rebuild |

---

## Alternative — Email Submission

If the GitHub PR workflow is not practical:

1. Email `team@blackarch.org`
2. Subject: `[NEW PACKAGE] conduit-browser 0.2.1`
3. Attach the PKGBUILD as a plain-text file.
4. Include the PR body text above in the email body.

Response time is typically 1–4 weeks.

---

## Additional Security Tool Directory Submissions

### ToolsWatch / Black Hat Arsenal

ToolsWatch (toolswatch.org) runs the annual Black Hat Arsenal call for tools.
The submission window opens roughly February each year for the summer event.

**Submission URL:** https://www.toolswatch.org/blackhat-arsenal-tools-submission/

**Template:**

```
Tool Name: Conduit Browser
Tool Version: 0.2.1
Tool URL: https://github.com/bkauto3/Conduit
Tool Category: Forensics / Web Application Testing
Programming Language: Python
Open Source: Yes
License: MIT

Short Description (< 100 words):
Conduit is a headless browser that produces cryptographically verifiable
evidence of every action it takes. Each navigate, click, fill, screenshot,
and JavaScript eval is written to a SHA-256 hash-chained SQLite audit log
signed with an Ed25519 identity key. Tampered or deleted entries break the
chain and are immediately detectable. Self-contained proof bundles (`.tar.gz`
with a stdlib-only `verify.py`) let recipients confirm integrity without
installing Conduit. SSRF protection blocks RFC-1918/loopback targets. Designed
for vulnerability documentation, forensic session replay, and incident response
evidence collection.

Presenter(s): BKAuto3
Contact: bullrushinvestments@gmail.com
```

---

### Kali Linux (Debian packaging)

Kali uses a full Debian packaging workflow. This is more involved than
BlackArch but gives access to `kali-tools-web` and `kali-tools-forensics`
meta-packages.

**Repository:** https://gitlab.com/kalilinux/packages

**Steps:**

1. Fork https://gitlab.com/kalilinux/packages
2. Create `conduit-browser/` branch off `kali/master`
3. Add a `debian/` directory containing:
   - `control` — package metadata
   - `rules` — build instructions (`pybuild` helper)
   - `copyright` — DEP-5 copyright format
   - `changelog` — Debian changelog format
   - `install` — file list

**Minimal `debian/control`:**

```
Source: conduit-browser
Section: net
Priority: optional
Maintainer: Kali Developers <devel@kali.org>
Build-Depends: debhelper-compat (= 13),
               dh-python,
               python3-all,
               python3-build,
               python3-installer,
               python3-wheel,
               python3-hatchling
Standards-Version: 4.6.2
Homepage: https://github.com/bkauto3/Conduit
Vcs-Browser: https://gitlab.com/kalilinux/packages/conduit-browser
Vcs-Git: https://gitlab.com/kalilinux/packages/conduit-browser.git

Package: conduit-browser
Architecture: all
Depends: ${python3:Depends}, ${misc:Depends}, python3-pip, sqlite3
Description: Headless browser with cryptographic audit trails
 Conduit is a headless browser that produces cryptographically verifiable
 evidence of every action. Each action is written to a SHA-256 hash-chained
 SQLite log signed with Ed25519. Self-contained proof bundles let recipients
 verify integrity without installing Conduit. SSRF protection blocks
 RFC-1918/loopback targets. Suitable for vulnerability documentation,
 forensic session replay, and incident response evidence collection.
```

**Minimal `debian/rules`:**

```makefile
#!/usr/bin/make -f
%:
	dh $@ --with python3 --buildsystem=pybuild

override_dh_auto_configure:
	export PYBUILD_NAME=conduit-browser

override_dh_auto_test:
	# Tests require a live browser; skip in package build
```

**Submission:**
Open a merge request to `kalilinux/packages` with your branch and link to the
tool's GitHub page. Include the same security-relevance description used for
BlackArch above.

---

### OWASP Tool Inventory

OWASP does not maintain a centralized tool repository, but tools can be
submitted as an **OWASP Project Proposal**.

**Process:**
1. Read the proposal requirements: https://owasp.org/www-committee-project/
2. Open an issue in https://github.com/OWASP/www-project-conduit-browser
   (create the repo under your account first, then OWASP staff can transfer it)
3. Submit the project proposal form at:
   https://owasp.org/projects/newproject.html

**Project Proposal Template:**

```
Project Name: OWASP Conduit Browser

Project Type: Tool

Project Leader: BKAuto3 <bullrushinvestments@gmail.com>

Description:
OWASP Conduit Browser is a headless browser automation tool that produces
cryptographically verifiable evidence of every action taken during a web
security assessment. It is designed to close the gap between "I found a
vulnerability" and "I can prove with court-admissible evidence what happened."

Key Features:
- SHA-256 hash-chained audit log: every action links to the previous one;
  deletion or modification of any entry breaks the chain.
- Ed25519 signatures: the entire session is signed with an identity key
  stored at ~/.cato/conduit_identity.key.
- JavaScript eval audit: the full source of every eval() call is stored
  verbatim in the chain, not just the return value.
- Self-verifiable proof bundles: exported as .tar.gz with a stdlib-only
  verify.py that requires no external dependencies.
- SSRF protection: RFC-1918 and loopback addresses are blocked at the
  navigation layer.
- MCP server interface: integrates with AI agent pipelines for automated
  security assessments.

Security Research Use Cases:
1. Documenting SQL injection, XSS, SSRF, and other web vulnerabilities with
   evidence that survives chain-of-custody review.
2. Forensic session replay for incident response — reproduce exactly what an
   attacker (or test tool) did, with every step signed.
3. Automated compliance evidence collection (GDPR data-handling checks,
   authentication flow audits).
4. Red team reporting: attach a proof bundle to a finding report; the client
   can verify independently without trusting the tester's screenshots.

License: MIT
Source: https://github.com/bkauto3/Conduit
PyPI: https://pypi.org/project/conduit-browser/
```

---

## File Checklist Before Any Submission

- [ ] `sha512sums` replaced with real checksum (not `SKIP`)
- [ ] `makepkg -si` passes in a clean chroot
- [ ] Installed binary/script runs without errors
- [ ] `pkgdesc` is under 80 characters
- [ ] `groups` includes at least one `blackarch-*` group
- [ ] `license` field matches the SPDX identifier (`MIT`)
- [ ] `url` points to the upstream source, not PyPI
- [ ] Email address in `# Maintainer:` is reachable
