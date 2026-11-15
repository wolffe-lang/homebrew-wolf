# homebrew-wolf

Homebrew formulae for the [wolf](https://github.com/wolffe-lang/wolf-lang)
language, its reference interpreter, and the lobo web server.

```sh
brew trust wolffe-lang/wolf
brew tap   wolffe-lang/wolf
brew install wolf
```

**The `brew trust` line is required, and skipping it produces a
misleading error.** Homebrew refuses to load formulae from an
untrusted third-party tap, and reports it as:

```
Refusing to load formula wolffe-lang/wolf/wolf from untrusted tap wolffe-lang/wolf.
Error: Cannot tap wolffe-lang/wolf: invalid syntax in tap!
```

There is no syntax error — the formulae pass `ruby -c`. The second
line is Homebrew's generic failure message for a tap it declined to
read. Trust the tap first and it taps cleanly.

| formula | what it is | upstream |
|---|---|---|
| `wolf` | the compiler — a compiled systems language with tiered region memory, no lifetime annotations | [wolf-lang](https://github.com/wolffe-lang/wolf-lang) |
| `lupin` | the reference interpreter, and the compiler's differential oracle | [wolf-interp](https://github.com/wolffe-lang/wolf-interp) |
| `lobo` | web server with nginx-compatible configs and prefork workers | [lobo](https://github.com/wolffe-lang/lobo) |

## Your first program

```sh
printf 'fn main() {\n  print("hello, wolf")\n}\n' > hello.lu
wolf run hello.lu
```

## The version string means something

The wolf and lupin formulae build from a **tagged git source**, not a release tarball,
and that is deliberate. `wolf --version` is stamped by the builder: it
names the version *and the commit it was built from*.

```
wolf 0.2.40 (wolfgang, pin b333b9d)
paired with lupin 0.1.62 (reference interpreter), pin 5f1f1c949582f53121e4047bc83c86f23ff72240
```

A build made any other way — a plain `cargo build`, or a build from an
archive with no `.git` — carries a `+dev` suffix instead. Unverifiable
is dev. If your `wolf --version` prints a bare version and a pin, the
binary can tell you exactly what it is.

Each formula's `test` block asserts that, so a formula that would ship
an unstamped binary fails before it reaches you.

## Platform support

Native codegen (`wolf build`, `wolf run`) serves **macOS arm64** and
**linux x86-64** today. On other hosts the native tier refuses **by
name** — never silently — and the checked tier still runs your program:

```sh
wolf test hello.lu
```

The per-host ledger is
[docs/platforms.md](https://github.com/wolffe-lang/wolf-lang/blob/trunk/docs/platforms.md).

## What runs before a bump reaches you

The formula checks answer two different questions.

`doors.yml` runs on every push to `trunk` and every pull request that
touches a formula: it installs each one on a macOS runner,
prints its version line, and runs its `test` block. Wolf and lupin are
source builds; lobo uses its published archive and is also checked on
Linux. A formula whose
`tag:` and `revision:` disagree, or whose build breaks at a new tag,
goes red here instead of in your terminal.

`doors-fresh.yml` runs daily and asks the other question: whether each
formula still names the current upstream release. A package does not
break when a version is cut — it quietly keeps serving the old one.

## Reusable tool releases

`tool-release.yml` is a reusable, **draft-only** release workflow for macOS
arm64 and Linux x86-64. A tool supplies `.github/release.json`, a local
`workflow_call` release-gate adapter, and a tag-triggered caller. Pin both
`uses: wolffe-lang/homebrew-wolf/.github/workflows/tool-release.yml@...` and
its `infrastructure-revision` input to the same full commit SHA. The caller
runs its adapter first and passes that adapter's `tested-sha` output.

Generate the adapter with `python3 -I tools/release-adapter --root TOOL --write`.
It retains the complete gate commands, omits development commentary, normalizes
an informational Unicode notice, removes the cron-only issue job, binds the run
to the exact tag and applies the explicitly selected release
profile. Run it without `--write` to refuse drift from the current CI; a tool's
lightweight release-wiring workflow checks that on every PR. Normal CI is not
rewritten to accommodate the release adapter. Supported profiles are `all`,
`full-every-suite`, `every-gate-leaf` and `full`; unsupported profiles refuse.

The config names the package manifest, gate workflow and explicit gate profile,
build argv, installed binary map, version arguments/pattern and smoke argv.
The version regex must contain a named `version` group. Optional fields are
`experimental`, `extra_files`, the `provenance_source`/`provenance_function` pair,
and `version_exemptions`. The
last field names commands whose compatible operand grammar has no version option;
each needs an explicit reason, and at least one family version must still be
observed. Unavailable options are printed and recorded in `BUILD.json`, never
counted as version measurements. Each smoke command starts
with an archived executable using `{bin}/NAME`; it runs from an empty working
directory with a scratch home and `SHELL=/bin/sh`. Python 3.11 or newer is needed.

A stable `vX.Y.Z` tag must resolve to the tested checkout commit. Its version
must agree with `wolf.pkg`, the observed version of every version-capable executable,
and a nonempty `CHANGELOG.md` section headed `## X.Y.Z`. The tool's own complete
release gate runs first; profiles are repository-specific, not interchangeable.
Builds fetch the digest-pinned toolchain, verify its actual identity and pack
reproducible archive headers twice. Archives contain executables, license,
README, release notes, toolchain pins and `BUILD.json` provenance. Den can request
an inline compiler-provenance literal stamped into an existing documented
function; the rest of the source file is preserved. Ordinary source builds remain honest
about an unrecorded compiler rather than embedding a stale version.

The workflow uploads exactly two archive/SHA-256 pairs to one draft, refusing
an already public release. Clean runners download those **draft assets** by ID,
compare API and sidecar digests, check provenance and run the product smoke
without a product checkout or compiler. A failed smoke leaves a draft, never
publishes. Publication is a separate human action.

After publication, manually invoke a tool's caller of `tool-public-smoke.yml`.
That separate read-only workflow checks anonymous API/download access and repeats
the archived-binary smoke. Lobo retains its current independent release workflow;
it can adopt this path at a later release.

## Prebuilt packaging generators

`tools/package-bin` renders a Homebrew formula and an AUR `-bin` recipe from
`packaging/products/NAME.json`. Shared templates cover ordinary CLI tools;
product hooks can replace formula, PKGBUILD, .SRCINFO or install text to preserve
special installation layouts, caveats and smoke tests. Lobo's lossless hooks
preserve its complete existing recipes, including the server test.

```sh
# Read-only dry run against the published lobo release:
python3 -I tools/package-bin --product lobo --version 0.1.5 --check
# Generate files in an explicitly chosen staging directory, never publish:
python3 -I tools/package-bin --product den --version 0.1.0 --output target/package-stage
python3 -I tests/test_release.py
```

Online generation requires the sidecar, GitHub asset digest and hash of an
anonymous archive download to agree. Drafts and missing digests refuse. Offline
mode with explicit digests is for fixtures only and says that integrity was not
checked. `--check` compares every generated byte without rewriting files.
The generator does not tag, release, publish, commit, or push to Homebrew or AUR.
First-tier product descriptions are preparation, not a claim of availability.

### boreutils package layout

When published, the boreutils recipes install only the `bore` dispatcher on PATH:
`bore cat FILE`, for example. AUR places the utility executables in
`/usr/lib/boreutils/bin/`; Homebrew uses `libexec/boreutils/bin/`. Neither recipe
replaces system commands or declares that it replaces coreutils.

Unprefixed names are an explicit opt-in:

```sh
# AUR:
export PATH="/usr/lib/boreutils/bin:$PATH"
# Homebrew:
export PATH="$(brew --prefix boreutils)/libexec/boreutils/bin:$PATH"
```

Or make only the links you choose in your own directory; no forced links:

```sh
mkdir -p "$HOME/.local/bin"
ln -s /usr/lib/boreutils/bin/cat "$HOME/.local/bin/bore-cat"
# Homebrew alternative:
ln -s "$(brew --prefix boreutils)/libexec/boreutils/bin/cat" "$HOME/.local/bin/bore-cat"
```

Use one installation's link command, not both. The launcher is packaging glue;
the dispatched utility executables are the release archive's Wolf programs.

## Reporting

Formula problems here; language and compiler problems upstream at
[wolf-lang](https://github.com/wolffe-lang/wolf-lang/issues).
