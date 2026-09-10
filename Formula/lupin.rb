class Lupin < Formula
  desc "Reference interpreter for the wolf language, and its differential oracle"
  homepage "https://github.com/wolffe-lang/wolf-interp"
  # A git source, not the release tarball, and D57 is the whole reason:
  # build.rs reads the git commit and the tags pointing at HEAD, and
  # `lupin --version` prints the bare version only when `v<version>` is
  # one of them. A build from an archive tarball has no .git and answers
  # `0.1.27+dev.unknown`.
  url "https://github.com/wolffe-lang/wolf-interp.git",
      using:    :git,
      tag:      "v0.1.31",
      revision: "e9c55b4a388f5ace9a3cc0a4f412ce7d0e474290"
  license "GPL-3.0-or-later"
  head "https://github.com/wolffe-lang/wolf-interp.git", branch: "trunk"

  depends_on "rust" => :build

  def install
    # The spec and corpus come from the tracked vendor/upstream snapshot;
    # the upstream/ submodule is not needed for a build.
    system "cargo", "install", *std_cargo_args
    doc.install "README.md", "CHANGELOG.md"
  end

  test do
    out = shell_output("#{bin}/lupin --version")
    assert_match(/^lupin #{Regexp.escape(version.to_s)} \(wolf-interp, reference interpreter at pin [0-9a-f]{7}\)$/,
                 out.lines.first.chomp)
    refute_match(/\+dev/, out)

    (testpath/"hello.lu").write <<~WOLF
      fn main() {
        print("hello, wolf")
      }
    WOLF
    assert_match "hello, wolf", shell_output("#{bin}/lupin run hello.lu")
  end
end
