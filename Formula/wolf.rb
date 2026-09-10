class Wolf < Formula
  desc "Compiled systems language whose compiler infers memory regions"
  homepage "https://github.com/wolffe-lang/wolf-lang"
  # A git source, not the release tarball, and D57 is the whole reason.
  # `wolf --version` is stamped by the BUILDER: `cargo xtask dist` reads
  # HEAD's short sha and the tags pointing at it, and grants the bare
  # version only when `v<version>` is one of them. An archive tarball has
  # no .git, so a build from one answers `0.2.6+dev.unknown` — a binary
  # that cannot say which compiler it is. Homebrew stages a real .git for
  # a tagged git url, so this build tells the truth.
  url "https://github.com/wolffe-lang/wolf-lang.git",
      using:    :git,
      tag:      "v0.2.10",
      revision: "662b14c6e10e4ee4628d788eb166f3f66b3e63f3"
  license "GPL-3.0-or-later"
  head "https://github.com/wolffe-lang/wolf-lang.git", branch: "trunk"

  depends_on "rust" => :build

  def install
    # The only build that stamps. It also stages the three files that
    # must travel together and smoke-tests the staged tree by compiling
    # and running corpus/hello.lu out of it.
    system "cargo", "xtask", "dist"

    triple = Utils.safe_popen_read("rustc", "-vV")[/^host: (.+)$/, 1]
    staged = buildpath/"target/dist/wolf-#{version}-#{triple}"

    # `wolf` looks for libwolf_rt.a strictly beside the running binary
    # (std::env::current_exe, no PATH fallback) and for the C importer
    # worker beside it or on PATH. A symlink in bin does NOT do it: on
    # macOS current_exe returns the symlink, the lookup misses, and
    # `wolf build` fails with "libwolf_rt.a not found next to the `wolf`
    # binary" — measured. The exec script replaces the process image, so
    # current_exe is the real libexec path on every host.
    libexec.install staged/"wolf", staged/"wolf-cimport-worker", staged/"libwolf_rt.a"
    bin.write_exec_script libexec/"wolf"

    doc.install "README.md"
    # The runtime library carries a linking exception: programs compiled
    # with wolf are yours, under any license you choose.
    doc.install "crates/wolf_rt/LICENSE-EXCEPTION"
  end

  def caveats
    <<~EOS
      First program:

        printf 'fn main() {\\n  print("hello, wolf")\\n}\\n' > hello.lu
        wolf run hello.lu

      `wolf --version` tells the truth about the build it names (D57):
      a release build prints the bare version and its pin, and anything
      else carries a `+dev` suffix.

      Native codegen (`wolf build` / `wolf run`) serves macOS arm64 and
      linux x86-64 today. Elsewhere the native tier refuses BY NAME and
      the checked tier still runs your program:

        wolf test hello.lu

      The per-host ledger:
        https://github.com/wolffe-lang/wolf-lang/blob/v#{version}/docs/platforms.md
    EOS
  end

  test do
    # The assertion that separates a package from a tarball with
    # ceremony: the bare version, no `+dev`, and a pin.
    out = shell_output("#{bin}/wolf --version")
    assert_match(/^wolf #{Regexp.escape(version.to_s)} \(wolfgang, pin [0-9a-f]{7}\)$/, out.lines.first.chomp)
    refute_match(/\+dev/, out)

    (testpath/"hello.lu").write <<~WOLF
      fn main() {
        print("hello, wolf")
      }
    WOLF

    # `wolf build` needs libwolf_rt.a beside the real binary — this is
    # what the exec script exists for. On a host the native tier does not
    # serve, the driver refuses by name with exit 2 and the checked tier
    # runs the same program; both are a working install, and a silent
    # skip would not be.
    if quiet_system(bin/"wolf", "build", "hello.lu", "-o", testpath/"hello")
      assert_equal "hello, wolf", shell_output(testpath/"hello").chomp
    else
      refusal = shell_output("#{bin}/wolf build hello.lu -o #{testpath}/hello 2>&1", 2)
      assert_match "this host cannot run the native tier", refusal
      # `wolf run --checked` refuses on an unserved host too — measured on
      # linux/aarch64. `wolf test` is the checked-tier entry point that
      # actually runs the program there, which is what xtask dist's own
      # smoke degrades to.
      assert_match "1 passed", shell_output("#{bin}/wolf test hello.lu")
    end
  end
end
