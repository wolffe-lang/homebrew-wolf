# homebrew-wolf

Homebrew formulae for the [wolf](https://github.com/wolffe-lang/wolf-lang)
language and its reference interpreter.

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

There is no syntax error — both formulae pass `ruby -c`. The second
line is Homebrew's generic failure message for a tap it declined to
read. Trust the tap first and it taps cleanly.

| formula | what it is | upstream |
|---|---|---|
| `wolf` | the compiler — a compiled systems language with tiered region memory, no lifetime annotations | [wolf-lang](https://github.com/wolffe-lang/wolf-lang) |
| `lupin` | the reference interpreter, and the compiler's differential oracle | [wolf-interp](https://github.com/wolffe-lang/wolf-interp) |

## Your first program

```sh
printf 'fn main() {\n  print("hello, wolf")\n}\n' > hello.lu
wolf run hello.lu
```

## The version string means something

Both formulae build from a **tagged git source**, not a release tarball,
and that is deliberate. `wolf --version` is stamped by the builder: it
names the version *and the commit it was built from*.

```
wolf 0.2.6 (wolfgang, pin 398e5f5)
paired with lupin 0.1.26 (reference interpreter), pin 982f857
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

Two workflows, and they answer different questions.

`doors.yml` runs on every push to `trunk` and every pull request that
touches a formula: it installs each one from source on a macOS runner,
prints its version line, and runs its `test` block. A formula whose
`tag:` and `revision:` disagree, or whose build breaks at a new tag,
goes red here instead of in your terminal.

`doors-fresh.yml` runs daily and asks the other question: whether each
formula still names the current upstream release. A package does not
break when a version is cut — it quietly keeps serving the old one.

## Reporting

Formula problems here; language and compiler problems upstream at
[wolf-lang](https://github.com/wolffe-lang/wolf-lang/issues).
