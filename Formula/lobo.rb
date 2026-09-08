class Lobo < Formula
  desc "Web server written in wolf: nginx-compatible configs, prefork workers"
  homepage "https://github.com/wolffe-lang/lobo"
  license "GPL-3.0-or-later"
  version "0.1.0"

  # A PREBUILT archive, and that is the considered choice, not a shortcut.
  # lobo is written in wolf, and `wolf-toolchain.toml` pins the compiler by
  # EXACT identity — `lib-toolchain.sh` compares `wolf --version` against
  # `wolf 0.2.6 (wolfgang, pin 398e5f5)` and refuses on any drift. A source
  # formula saying `depends_on "wolf"` would therefore break the day the
  # wolf formula moves to 0.2.7, and every release after. The published
  # archive is built from the pin by lobo's own release workflow and is the
  # byte-identical artifact its learner smoke tests on a clean runner.
  on_macos do
    on_arm do
      url "https://github.com/wolffe-lang/lobo/releases/download/v0.1.0/lobo-0.1.0-aarch64-apple-darwin.tar.gz"
      sha256 "c643e441a7168aedbe6ca3275c3fcb8ba5724d72527fe4893da97f5444e41247"
    end
  end

  on_linux do
    on_intel do
      url "https://github.com/wolffe-lang/lobo/releases/download/v0.1.0/lobo-0.1.0-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "7a99ae243b7a9cda0f778f5705612e4f2b02528ec86623d24070f780014dc0bc"
    end
  end

  def install
    # One static binary — the wolf runtime is linked in, so nothing needs
    # to sit beside it (unlike `wolf` itself, which hunts libwolf_rt.a
    # next to current_exe).
    bin.install "lobo"

    # The stock tree is a TEMPLATE, not a live prefix: lobo takes `-p`
    # like nginx, and its config's paths are relative to it (logs/,
    # html/). pkgshare is read-only, so the caveats show how to make a
    # working copy rather than pretending to a service layout 0.1.0 does
    # not have yet.
    pkgshare.install "conf", "html"
    doc.install "BUILD", "GETTING-STARTED.md", "README.md", "CHANGELOG.md"
    doc.install Dir["docs/*"]
  end

  def caveats
    <<~EOS
      lobo takes a prefix like nginx does, and the stock config's paths are
      relative to it. Make a working copy and run from it:

        mkdir -p ~/lobo && cd ~/lobo
        cp -R #{opt_pkgshare}/conf #{opt_pkgshare}/html .
        mkdir -p logs
        lobo                      # serves html/ on 127.0.0.1:8080
        lobo -s stop

      `lobo -v` names the toolchain that built it; #{opt_prefix}/share/doc/lobo/BUILD records
      the same line, the source commit and the pins.

      Prebuilt for macOS arm64 and linux x86-64 — the hosts wolf's release
      tier serves. windows x86-64 and linux aarch64 are named refusals.
    EOS
  end

  test do
    # The provenance assertion: a release build names its toolchain and
    # carries no +dev suffix.
    #
    # `2>&1` is required, not incidental: lobo writes -v to STDERR because
    # nginx does, and matching nginx's stream behaviour is the compat
    # charter. A test that read stdout alone would compare against "" and
    # fail while the binary was working perfectly.
    out = shell_output("#{bin}/lobo -v 2>&1")
    assert_match "lobo/#{version} (built with wolf ", out
    refute_match(/\+dev/, out)

    # And it actually serves. A working prefix, a free port, one GET, and
    # the bytes compared against the page that shipped.
    port = free_port
    cp_r "#{pkgshare}/conf", testpath
    cp_r "#{pkgshare}/html", testpath
    (testpath/"logs").mkpath
    inreplace testpath/"conf/lobo.conf", "127.0.0.1:8080", "127.0.0.1:#{port}"

    # `serve` is a VERB, not a flag — lobo's own stock config documents it
    # (`./lobo -c conf/lobo.conf serve`). nginx's `-g "daemon off;"` is
    # accepted as an option but does not start the server, so a test
    # written from nginx habit gets a banner and a refused connection.
    pid = spawn bin/"lobo", "-p", testpath, "-c", "conf/lobo.conf", "serve"
    begin
      sleep 3
      served = shell_output("curl -sf http://127.0.0.1:#{port}/")
      assert_equal (testpath/"html/index.html").read, served
    ensure
      system bin/"lobo", "-p", testpath, "-c", "conf/lobo.conf", "-s", "stop"
      Process.kill("TERM", pid) rescue nil
      Process.wait(pid) rescue nil
    end
  end
end
