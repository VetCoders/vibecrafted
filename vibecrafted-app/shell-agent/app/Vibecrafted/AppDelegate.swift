import AppKit
import CoreText
import Darwin
import os.log

private let installLog = Logger(subsystem: "io.vetcoders.vibecrafted", category: "install")

private struct CanonicalRuntimeInstall {
  let root: URL
  let terminal: URL
  let terminalHost: URL
  let frame: URL
  let start: URL
  let primaryShell: URL
  let terminalConfig: URL
  let frameConfig: URL
  let runtimeHome: URL
  let configHome: URL
  let craftedHome: URL
}

final class EventObserver: @unchecked Sendable, EventCallback {
  func onEvent(eventJson: String) {
    DispatchQueue.main.async {
      NotificationCenter.default.post(
        name: NSNotification.Name("IpcEvent"), object: nil, userInfo: ["eventJson": eventJson])
    }
  }

  func onError(err: String) {
    print("IPC Stream Error: \(err)")
  }
}

@MainActor
class AppDelegate: NSObject, NSApplicationDelegate {
  var mainWindow: MainWindowController?
  private var statusItem: NSStatusItem?
  private var terminalProcess: Process?
  private var workspaceLaunchFailureReported = false
  private var eyeReconcileProcess: Process?
  let eventObserver = EventObserver()

  func showMainWindowIfNeeded() {
    if mainWindow == nil {
      mainWindow = MainWindowController()
    }
    mainWindow?.showWindow(nil)
    mainWindow?.window?.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
  }

  func applicationDidFinishLaunching(_ notification: Notification) {
    if ProcessInfo.processInfo.arguments.contains("--bootstrap-only") {
      do {
        let install = try installCanonicalRuntime()
        print(install.root.path)
        exit(EXIT_SUCCESS)
      } catch {
        fputs("Vibecrafted bootstrap failed: \(error)\n", stderr)
        exit(EXIT_FAILURE)
      }
    }

    buildMainMenu()
    buildStatusItem()

    let socketPath = "/tmp/vibecrafted-mux.sock"
    do {
      try initRuntime(socketPath: socketPath)
      Task {
        do {
          try await subscribeEvents(callback: eventObserver)
        } catch {
          print("Failed to subscribe: \(error)")
        }
      }
    } catch {
      print("Failed to init runtime: \(error)")
    }

    launchWorkspaceTerminal()
  }

  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    false
  }

  func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    true
  }

  private func launchWorkspaceTerminal() {
    if terminalProcess?.isRunning == true {
      return
    }

    let install: CanonicalRuntimeInstall
    do {
      install = try installCanonicalRuntime()
    } catch {
      reportWorkspaceLaunchFailure(
        "Cannot publish the canonical Vibecrafted runtime: \(error.localizedDescription)")
      return
    }

    // The install moment. Publishing the generation above touched nothing an
    // agent reads; what follows is the part a person decides: which agents,
    // which skills language, where agents work, what they may do. Recorded
    // once in ~/.config/vibecrafted/config.toml, re-applied on every launch
    // so an upgrade keeps the agents connected without asking again.
    switch ensureFirstRunDecisions(install) {
    case .ready:
      break
    case .quit:
      NSApp.terminate(nil)
      return
    case .failed(let message):
      reportWorkspaceLaunchFailure(message)
      return
    }

    for required in [
      install.terminal, install.terminalHost, install.frame, install.start,
      install.primaryShell,
    ]
      where !FileManager.default.isExecutableFile(
      atPath: required.path)
    {
      reportWorkspaceLaunchFailure(
        "Bundled product entry is missing or not executable: \(required.path)")
      return
    }
    guard FileManager.default.fileExists(atPath: install.terminalConfig.path) else {
      reportWorkspaceLaunchFailure(
        "Canonical terminal config is missing: \(install.terminalConfig.path)")
      return
    }
    do {
      try registerBundledFonts()
    } catch {
      reportWorkspaceLaunchFailure(
        "Cannot register the bundled terminal font: \(error.localizedDescription)")
      return
    }

    let host = ProcessInfo.processInfo.environment
    let inherited = [
      "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "COLORTERM", "TMPDIR",
      "SHELL",
    ]
    var environment = Dictionary(
      uniqueKeysWithValues: inherited.compactMap { key in host[key].map { (key, $0) } })
    // The workspace terminal spawns agent CLIs (codex, gh, claude, loct) whose
    // `#!/usr/bin/env` shebangs resolve against exactly this PATH. Amputating the
    // caller's PATH down to the system set hides Homebrew, ~/.local/bin and
    // ~/.cargo/bin, so those tools die with exit 127. Keep the host PATH and only
    // give the signed generation priority over it.
    environment["PATH"] = composedPath(
      generation: install.root, inherited: host["PATH"])
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["XDG_CONFIG_HOME"] = install.configHome.path
    environment["VIBECRAFTED_HOME"] = install.craftedHome.path
    environment["VIBECRAFTED_RUNTIME_HOME"] = install.runtimeHome.path
    environment["VIBECRAFTED_RUNTIME_ROOT"] = install.root.path
    environment["VIBECRAFTED_ROOT"] = install.root.path
    environment["VIBECRAFTED_PYTHON"] = install.root.appendingPathComponent("bin/python3").path
    environment["VIBECRAFTED_VC_FRAME_BIN"] = install.frame.path
    environment["VC_FRAME_CONFIG_DIR"] = install.frameConfig.path
    // Keep Unix socket paths below macOS' 104-byte sockaddr_un limit. Preserve
    // the former TMPDIR namespace for one-way import into WES during startup.
    let socketRoot = "/tmp/vc-frame-\(getuid())"
    environment["VC_FRAME_SOCKET_DIR"] = socketRoot
    environment["ZELLIJ_SOCKET_DIR"] = socketRoot
    if let temp = host["TMPDIR"]?.trimmingCharacters(in: CharacterSet(charactersIn: "/")),
      !temp.isEmpty
    {
      environment["VIBECRAFTED_LEGACY_VC_FRAME_SOCKET_DIR"] =
        "/\(temp)/vc-frame-\(getuid())"
    }

    let process = Process()
    process.executableURL = install.terminalHost
    process.arguments = [
      "--config-file", install.terminalConfig.path,
      "-e", install.primaryShell.path, install.start.path, "operator",
    ]
    process.environment = environment
    do {
      try process.run()
      terminalProcess = process
    } catch {
      reportWorkspaceLaunchFailure(
        "Failed to launch bundled vc-terminal: \(error.localizedDescription)")
    }
    reconcileControlPlaneEye(install: install, environment: environment)
  }

  private func reconcileControlPlaneEye(
    install: CanonicalRuntimeInstall, environment: [String: String]
  ) {
    let deck = install.root.appendingPathComponent("bin/vibecrafted")
    guard FileManager.default.isExecutableFile(atPath: deck.path) else { return }
    let process = Process()
    process.executableURL = deck
    process.arguments = ["server", "service", "reconcile"]
    process.environment = environment
    process.standardOutput = FileHandle.nullDevice
    process.standardError = FileHandle.nullDevice
    do {
      try process.run()
      eyeReconcileProcess = process
    } catch {
      print("Cannot reconcile the control-plane eye: \(error)")
    }
  }

  private func registerBundledFonts() throws {
    let font = Bundle.main.bundleURL.appendingPathComponent(
      "Contents/Resources/fonts/SpotMono.ttc")
    guard FileManager.default.fileExists(atPath: font.path) else {
      throw NSError(
        domain: "io.vetcoders.vibecrafted.fonts", code: 1,
        userInfo: [NSLocalizedDescriptionKey: "bundled SpotMono.ttc is missing"])
    }

    var registrationError: Unmanaged<CFError>?
    if !CTFontManagerRegisterFontsForURL(font as CFURL, .session, &registrationError) {
      let message = registrationError?.takeRetainedValue().localizedDescription
        ?? "CoreText rejected SpotMono.ttc"
      // A system-installed Spot Mono can already occupy the session scope.
      // Accept that case only when CoreText resolves the required family.
      let descriptor = CTFontDescriptorCreateWithAttributes(
        [kCTFontFamilyNameAttribute as String: "Spot Mono"] as CFDictionary)
      guard let match = CTFontDescriptorCreateMatchingFontDescriptor(descriptor, nil),
        CTFontDescriptorCopyAttribute(match, kCTFontFamilyNameAttribute) as? String == "Spot Mono"
      else {
        throw NSError(
          domain: "io.vetcoders.vibecrafted.fonts", code: 2,
          userInfo: [NSLocalizedDescriptionKey: message])
      }
    }
  }

  private func installCanonicalRuntime() throws -> CanonicalRuntimeInstall {
    let manager = FileManager.default
    let host = ProcessInfo.processInfo.environment
    let home = host["HOME"] ?? manager.homeDirectoryForCurrentUser.path
    let runtimeHome = URL(
      fileURLWithPath:
        host["VIBECRAFTED_RUNTIME_HOME"]
        ?? host["XDG_DATA_HOME"].map { "\($0)/vibecrafted" }
        ?? "\(home)/.local/share/vibecrafted", isDirectory: true)
    let configHome = URL(
      fileURLWithPath: host["XDG_CONFIG_HOME"] ?? "\(home)/.config", isDirectory: true)
    let productConfig = configHome.appendingPathComponent("vibecrafted", isDirectory: true)
    let craftedHome = URL(
      fileURLWithPath: host["VIBECRAFTED_HOME"] ?? "\(home)/.vibecrafted", isDirectory: true)
    let launcherHome = URL(
      fileURLWithPath: host["VIBECRAFTED_LAUNCHER_BIN"] ?? "\(home)/.local/bin",
      isDirectory: true)

    let appRoot = Bundle.main.bundleURL
    let bundledRuntime = appRoot.appendingPathComponent(
      "Contents/Resources/runtime", isDirectory: true)
    let versionURL = bundledRuntime.appendingPathComponent("VERSION")
    let version = try String(contentsOf: versionURL, encoding: .utf8)
      .trimmingCharacters(in: .whitespacesAndNewlines)
    let allowed = CharacterSet(charactersIn: "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+_-")
    guard !version.isEmpty, version.unicodeScalars.allSatisfy(allowed.contains) else {
      throw NSError(
        domain: "io.vetcoders.vibecrafted.install", code: 1,
        userInfo: [NSLocalizedDescriptionKey: "invalid bundled VERSION: \(version)"])
    }

    let releases = runtimeHome.appendingPathComponent("releases", isDirectory: true)
    let generation = releases.appendingPathComponent(version, isDirectory: true)
    try manager.createDirectory(at: releases, withIntermediateDirectories: true)
    try manager.createDirectory(at: productConfig, withIntermediateDirectories: true)
    try manager.createDirectory(at: craftedHome, withIntermediateDirectories: true)
    try manager.createDirectory(
      at: craftedHome.appendingPathComponent("artifacts", isDirectory: true),
      withIntermediateDirectories: true)
    try manager.createDirectory(
      at: craftedHome.appendingPathComponent("control_plane", isDirectory: true),
      withIntermediateDirectories: true)
    try manager.createDirectory(at: launcherHome, withIntermediateDirectories: true)

    if !manager.fileExists(atPath: generation.path) {
      let staging = releases.appendingPathComponent(
        ".\(version).staging-\(UUID().uuidString)", isDirectory: true)
      defer { try? manager.removeItem(at: staging) }
      try manager.copyItem(at: bundledRuntime, to: staging)
      let bin = staging.appendingPathComponent("bin", isDirectory: true)
      try manager.createDirectory(at: bin, withIntermediateDirectories: true)
      try manager.copyItem(
        at: appRoot.appendingPathComponent(
          "Contents/Helpers/vc-terminal.app/Contents/MacOS/alacritty"),
        to: bin.appendingPathComponent("vc-terminal"))
      try manager.copyItem(
        at: appRoot.appendingPathComponent("Contents/Helpers/vc-frame"),
        to: bin.appendingPathComponent("vc-frame"))
      try assertNoSymlinks(below: staging)
      try manager.moveItem(at: staging, to: generation)
    }
    try assertNoSymlinks(below: generation)
    let bin = generation.appendingPathComponent("bin", isDirectory: true)

    // The terminal policy and palettes are signed, version-bound inputs. The
    // tiny entry file is regenerated on every launch and imports the current
    // generation plus one product-owned mutable palette. We never read or
    // mutate the user's Alacritty configuration.
    let terminalPolicy = generation.appendingPathComponent(
      "config/vc-terminal/vibecrafted.toml")
    let terminalThemes = generation.appendingPathComponent(
      "config/vc-terminal/themes", isDirectory: true)
    let terminalTheme = productConfig.appendingPathComponent("terminal-theme.toml")
    if !manager.fileExists(atPath: terminalTheme.path) {
      try manager.copyItem(
        at: terminalThemes.appendingPathComponent("dark.toml"), to: terminalTheme)
    }
    let terminalConfig = productConfig.appendingPathComponent("terminal-entry.toml")
    let terminalEntry = """
      # Generated by Vibecrafted.app. Do not point this at a private Alacritty config.
      [general]
      import = [
        \(tomlBasicString(terminalPolicy.path)),
        \(tomlBasicString(terminalTheme.path)),
      ]
      live_config_reload = true
      """
    try Data(terminalEntry.utf8).write(to: terminalConfig, options: .atomic)
    let sourceFrameConfig = generation.appendingPathComponent(
      "vibecrafted-core/vibecrafted_core/config/vc-frame", isDirectory: true)
    let frameConfig = productConfig.appendingPathComponent("vc-frame", isDirectory: true)
    if !manager.fileExists(atPath: frameConfig.path) {
      try manager.copyItem(at: sourceFrameConfig, to: frameConfig)
    }
    let sourceShell = generation.appendingPathComponent(
      "vibecrafted-core/vibecrafted_core/runtime/shell", isDirectory: true)
    let productShell = productConfig.appendingPathComponent("shell", isDirectory: true)
    // The shell helper layer is runtime code, not operator config. A
    // copy-once projection froze an old parser here (`--run-id` unknown while
    // the release already spoke it), so every install refreshes it in full.
    if manager.fileExists(atPath: productShell.path) {
      try manager.removeItem(at: productShell)
    }
    try manager.copyItem(at: sourceShell, to: productShell)
    try assertNoSymlinks(below: productConfig)

    let terminal = generation.appendingPathComponent("bin/vc-terminal")
    let terminalHost = appRoot.appendingPathComponent(
      "Contents/Helpers/vc-terminal.app/Contents/MacOS/alacritty")
    let frame = generation.appendingPathComponent("bin/vc-frame")
    let start = generation.appendingPathComponent("bin/vc-start")
    let primaryShell = generation.appendingPathComponent(
      "config/alacritty/launch-primary-shell.zsh")
    let deck = generation.appendingPathComponent("bin/vibecrafted")
    let server = generation.appendingPathComponent("bin/vc-server")
    let guardian = generation.appendingPathComponent("bin/vc-guardian")
    let supervisor = generation.appendingPathComponent("bin/vc-server-supervisor")
    let workflow = generation.appendingPathComponent("bin/vc-workflow")
    for required in [
      terminal, terminalHost, frame, start, primaryShell, deck, server, guardian,
      supervisor, workflow,
    ]
      where !manager.isExecutableFile(atPath: required.path)
    {
      throw NSError(
        domain: "io.vetcoders.vibecrafted.install", code: 2,
        userInfo: [NSLocalizedDescriptionKey: "runtime entry is not executable: \(required.path)"])
    }

    let common = [
      "export XDG_CONFIG_HOME=\(shellQuote(configHome.path))",
      "export VIBECRAFTED_HOME=\(shellQuote(craftedHome.path))",
      "export VIBECRAFTED_RUNTIME_HOME=\(shellQuote(runtimeHome.path))",
      "export VIBECRAFTED_RUNTIME_ROOT=\(shellQuote(generation.path))",
      "export VIBECRAFTED_ROOT=\(shellQuote(generation.path))",
      "export VIBECRAFTED_PYTHON=\(shellQuote(generation.appendingPathComponent("bin/python3").path))",
      "export VIBECRAFTED_VC_FRAME_BIN=\(shellQuote(frame.path))",
      "export VC_FRAME_CONFIG_DIR=\(shellQuote(frameConfig.path))",
      // PATH is the one export that must compose instead of replace. A launcher
      // that hard-codes the system set strips Homebrew, ~/.local/bin and
      // ~/.cargo/bin from everything it spawns, so `#!/usr/bin/env node` CLIs
      // exit 127. The generation still wins; the caller's PATH survives behind
      // it, with the system set as the fallback when the caller has none.
      "export PATH=\"\(shellDoubleQuoteBody(generation.appendingPathComponent("bin").path))"
        + ":${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}\"",
    ]
    let runtimeEntries = try manager.contentsOfDirectory(
      at: bin, includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles])
    for entry in runtimeEntries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
      let name = entry.lastPathComponent
      guard name != "python3", name != "vc-terminal" else { continue }
      let values = try entry.resourceValues(forKeys: [.isRegularFileKey])
      guard values.isRegularFile == true, manager.isExecutableFile(atPath: entry.path) else { continue }
      try writeLauncher(
        launcherHome.appendingPathComponent(name), common: common, executable: entry)
    }
    try writeLauncher(
      launcherHome.appendingPathComponent("vc-terminal"), common: common, executable: terminalHost,
      leadingArguments: ["--config-file", terminalConfig.path])

    // Deck-verb wrappers. These public names have no runtime binary of their
    // own — they are verbs of the bash deck. A plain `exec deck "$@"` shim (or
    // a symlink onto one) loses the invoked name at the shebang boundary, so
    // `vc-resume claude --session <id>` used to degrade into
    // `vibecrafted claude --session <id>` ("Unknown mode"). Injecting the verb
    // into the shim keeps launcher identity across any exec chain. Keep this
    // map in lockstep with SHELL_WRAPPER_VERBS in vibecrafted_core/cli.py
    // (tests/tui/test_keys.py pins the parity).
    let deckVerbWrappers: [(name: String, verb: String)] = [
      ("vc-help", "help"),
      ("vc-init", "init"),
      ("vc-dashboard", "dashboard"),
      ("vc-dispatch", "dispatch"),
      ("vc-resume", "resume"),
      ("vc-justdo", "justdo"),
      ("telemetry", "telemetry"),
    ]
    for wrapper in deckVerbWrappers
      where !manager.isExecutableFile(atPath: bin.appendingPathComponent(wrapper.name).path)
    {
      try writeLauncher(
        launcherHome.appendingPathComponent(wrapper.name), common: common, executable: deck,
        leadingArguments: [wrapper.verb])
    }

    let active: [String: String] = [
      "schema": "vibecrafted.active-runtime.v1",
      "version": version,
      "runtime_root": generation.path,
      "app_root": appRoot.path,
    ]
    let activeData = try JSONSerialization.data(
      withJSONObject: active, options: [.prettyPrinted, .sortedKeys])
    try activeData.write(to: runtimeHome.appendingPathComponent("active.json"), options: .atomic)

    return CanonicalRuntimeInstall(
      root: generation, terminal: terminal, terminalHost: terminalHost, frame: frame,
      start: start, primaryShell: primaryShell, terminalConfig: terminalConfig,
      frameConfig: frameConfig, runtimeHome: runtimeHome, configHome: configHome,
      craftedHome: craftedHome)
  }

  private func assertNoSymlinks(below root: URL) throws {
    let keys: [URLResourceKey] = [.isSymbolicLinkKey]
    if try root.resourceValues(forKeys: Set(keys)).isSymbolicLink == true {
      throw NSError(
        domain: "io.vetcoders.vibecrafted.install", code: 3,
        userInfo: [
          NSLocalizedDescriptionKey:
            "symlink is forbidden: \(root.standardizedFileURL.path)"
        ])
    }
    guard let enumerator = FileManager.default.enumerator(
      at: root, includingPropertiesForKeys: keys, options: [], errorHandler: nil)
    else { return }
    for case let item as URL in enumerator {
      if try item.resourceValues(forKeys: Set(keys)).isSymbolicLink == true {
        // The absolute path of the offending link is the only actionable part of
        // this failure; it is what the operator has to delete or replace.
        throw NSError(
          domain: "io.vetcoders.vibecrafted.install", code: 3,
          userInfo: [
            NSLocalizedDescriptionKey:
              "symlink is forbidden in runtime: \(item.standardizedFileURL.path)"
          ])
      }
    }
  }

  private func shellQuote(_ value: String) -> String {
    "'\(value.replacingOccurrences(of: "'", with: "'\"'\"'"))'"
  }

  /// Escape `value` for use *inside* a double-quoted shell word, where parameter
  /// expansion must stay live for the rest of the word.
  private func shellDoubleQuoteBody(_ value: String) -> String {
    value
      .replacingOccurrences(of: "\\", with: "\\\\")
      .replacingOccurrences(of: "$", with: "\\$")
      .replacingOccurrences(of: "`", with: "\\`")
      .replacingOccurrences(of: "\"", with: "\\\"")
  }

  /// Signed generation bin first, then whatever PATH the caller already had;
  /// the minimal system set only when the caller carried no PATH at all.
  private func composedPath(generation: URL, inherited: String?) -> String {
    let tail = (inherited ?? "").isEmpty ? "/usr/bin:/bin:/usr/sbin:/sbin" : inherited!
    return "\(generation.appendingPathComponent("bin").path):\(tail)"
  }

  private enum FirstRunOutcome {
    case ready
    case quit
    case failed(String)
  }

  /// Run a runtime Python command to completion and return (status, stdout, stderr).
  private func runRuntimePython(
    _ install: CanonicalRuntimeInstall, _ arguments: [String], timeout: TimeInterval = 600
  ) -> (Int32, String, String) {
    let process = Process()
    process.executableURL = install.root.appendingPathComponent("bin/python3")
    process.arguments = arguments
    process.environment = firstRunEnvironment(install)
    let out = Pipe()
    let err = Pipe()
    process.standardOutput = out
    process.standardError = err
    do {
      try process.run()
    } catch {
      return (-1, "", error.localizedDescription)
    }
    let deadline = Date().addingTimeInterval(timeout)
    while process.isRunning && Date() < deadline {
      RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.1))
    }
    if process.isRunning {
      process.terminate()
      return (-1, "", "timed out after \(Int(timeout)) s")
    }
    let stdout = String(decoding: out.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
    let stderr = String(decoding: err.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
    return (process.terminationStatus, stdout, stderr)
  }

  private func firstRunEnvironment(_ install: CanonicalRuntimeInstall) -> [String: String] {
    let host = ProcessInfo.processInfo.environment
    var environment: [String: String] = [:]
    for key in ["HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "SHELL"] {
      if let value = host[key] { environment[key] = value }
    }
    environment["PATH"] = composedPath(generation: install.root, inherited: host["PATH"])
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["XDG_CONFIG_HOME"] = install.configHome.path
    environment["VIBECRAFTED_HOME"] = install.craftedHome.path
    environment["VIBECRAFTED_RUNTIME_HOME"] = install.runtimeHome.path
    environment["VIBECRAFTED_RUNTIME_ROOT"] = install.root.path
    environment["VIBECRAFTED_ROOT"] = install.root.path
    environment["VIBECRAFTED_PYTHON"] = install.root.appendingPathComponent("bin/python3").path
    return environment
  }

  /// Whether `[product]` decisions are recorded (`first_run show` prints JSON or `null`).
  private func firstRunDecisionsRecorded(_ install: CanonicalRuntimeInstall) -> Bool {
    let (status, stdout, _) = runRuntimePython(
      install, ["-m", "vibecrafted_core.first_run", "show"], timeout: 30)
    return status == 0 && stdout.trimmingCharacters(in: .whitespacesAndNewlines) != "null"
  }

  /// The install moment: wizard in the browser (or an explicit unattended
  /// preset), then the skills projection from whatever was decided.
  private func ensureFirstRunDecisions(_ install: CanonicalRuntimeInstall) -> FirstRunOutcome {
    let unattended =
      ProcessInfo.processInfo.arguments.contains("--unattended")
      || ProcessInfo.processInfo.environment["VIBECRAFTED_FIRST_RUN"] == "unattended"

    if !firstRunDecisionsRecorded(install) {
      if unattended {
        installLog.notice(
          "first run: unattended preset (all detected agents, English skills, Living Tree, agents ask) — VIBECRAFTED_FIRST_RUN=unattended")
        let (detectStatus, detected, _) = runRuntimePython(
          install, ["-m", "vibecrafted_core.agent_view", "detect"], timeout: 30)
        let agents = detectStatus == 0
          ? detected.split(separator: "\n").map(String.init).joined(separator: ",") : ""
        let version = (try? String(
          contentsOf: install.root.appendingPathComponent("VERSION"), encoding: .utf8))?
          .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let (status, stdout, stderr) = runRuntimePython(
          install,
          [
            "-m", "vibecrafted_core.first_run", "apply", "--unattended",
            "--agents", agents, "--lang", "en", "--work-mode", "living-tree",
            "--permissions", "ask", "--version", version,
          ])
        installLog.notice("first run (unattended): \(stdout, privacy: .public)")
        if status != 0 {
          return .failed("Unattended first run could not record its decisions: \(stderr)")
        }
      } else {
        switch runFirstRunWizard(install) {
        case .ready: break
        case .quit: return .quit
        case .failed(let message): return .failed(message)
        }
      }
    }

    // Every launch: re-project from the record, so a new generation (this
    // one) is what the agents see. Errors here are loud but not fatal: the
    // workspace still opens, doctor names the broken link.
    let (status, stdout, stderr) = runRuntimePython(
      install, ["-m", "vibecrafted_core.first_run", "reapply"], timeout: 120)
    if status != 0 {
      installLog.error(
        "skills projection failed (\(status)): \(stdout, privacy: .public) \(stderr, privacy: .public)")
    } else {
      installLog.notice("skills projection: \(stdout, privacy: .public)")
    }
    return .ready
  }

  /// Open the first-run wizard (runtime scripts/installer_gui.py --first-run)
  /// in the browser and wait until it has recorded the decisions, the person
  /// quit, or the wizard process died.
  private func runFirstRunWizard(_ install: CanonicalRuntimeInstall) -> FirstRunOutcome {
    let wizardScript = install.root.appendingPathComponent("scripts/installer_gui.py")
    guard FileManager.default.isReadableFile(atPath: wizardScript.path) else {
      return .failed(
        "The first-run wizard is missing from this runtime: \(wizardScript.path). Reinstall Vibecrafted, or launch with --unattended to accept the default setup.")
    }
    let wizard = Process()
    wizard.executableURL = install.root.appendingPathComponent("bin/python3")
    wizard.arguments = [wizardScript.path, "--first-run", "--source", install.root.path, "--port", "0"]
    wizard.environment = firstRunEnvironment(install)
    wizard.standardOutput = FileHandle.nullDevice
    wizard.standardError = FileHandle.nullDevice
    do {
      try wizard.run()
    } catch {
      return .failed("Cannot open the first-run wizard: \(error.localizedDescription)")
    }
    defer { if wizard.isRunning { wizard.terminate() } }

    let alert = NSAlert()
    alert.alertStyle = .informational
    alert.messageText = "Setting up Vibecrafted"
    alert.informativeText =
      "The setup opened in your browser. It installs the foundations (Loctree, AICX, prview, screenscribe) and asks four things: which agents, skills language, where agents work, and what they may do. This window closes by itself when the setup is done."
    alert.addButton(withTitle: "Quit Vibecrafted")

    var outcome: FirstRunOutcome = .quit
    let poll = Timer(timeInterval: 1.5, repeats: true) { [weak self] timer in
      // Timer callbacks land on the main run loop; the actor check is only
      // what the compiler cannot see from a nonisolated closure.
      MainActor.assumeIsolated {
        guard let self else { return }
        if self.firstRunDecisionsRecorded(install) {
          outcome = .ready
          timer.invalidate()
          NSApp.abortModal()
        } else if !wizard.isRunning {
          outcome = .failed(
            "The first-run wizard closed before the setup was recorded. Open Vibecrafted again to retry, or launch with --unattended.")
          timer.invalidate()
          NSApp.abortModal()
        }
      }
    }
    RunLoop.main.add(poll, forMode: .common)
    let response = alert.runModal()
    poll.invalidate()
    if response == .alertFirstButtonReturn {
      return .quit
    }
    return outcome
  }

  /// Surface a launch failure where the operator can actually see it: the unified
  /// log for post-mortem, plus one modal so a broken install is never silent.
  private func reportWorkspaceLaunchFailure(_ message: String) {
    installLog.error("\(message, privacy: .public)")
    guard !workspaceLaunchFailureReported else { return }
    workspaceLaunchFailureReported = true
    let alert = NSAlert()
    alert.alertStyle = .critical
    alert.messageText = "Vibecrafted cannot open its workspace terminal"
    alert.informativeText = message
    alert.addButton(withTitle: "OK")
    alert.runModal()
  }

  private func tomlBasicString(_ value: String) -> String {
    let escaped = value
      .replacingOccurrences(of: "\\", with: "\\\\")
      .replacingOccurrences(of: "\"", with: "\\\"")
    return "\"\(escaped)\""
  }

  private func writeLauncher(
    _ destination: URL, common: [String], executable: URL, leadingArguments: [String] = []
  ) throws {
    let arguments = leadingArguments.map(shellQuote).joined(separator: " ")
    let prefix = arguments.isEmpty ? "" : "\(arguments) "
    let body =
      (["#!/bin/bash", "set -euo pipefail"] + common
        + ["exec \(shellQuote(executable.path)) \(prefix)\"$@\""])
      .joined(separator: "\n") + "\n"
    let temporary = destination.deletingLastPathComponent().appendingPathComponent(
      ".\(destination.lastPathComponent).new-\(UUID().uuidString)")
    try body.write(to: temporary, atomically: true, encoding: .utf8)
    try FileManager.default.setAttributes(
      [.posixPermissions: 0o755], ofItemAtPath: temporary.path)
    if rename(temporary.path, destination.path) != 0 {
      let code = errno
      try? FileManager.default.removeItem(at: temporary)
      throw NSError(
        domain: NSPOSIXErrorDomain, code: Int(code),
        userInfo: [NSLocalizedDescriptionKey: "cannot atomically publish \(destination.path)"])
    }
  }

  // MARK: - Main Menu

  private func buildStatusItem() {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    // Inherit the app (dock) icon for the menu-bar status item so the tray
    // matches the dock panda instead of a generic SF Symbol.
    let trayIcon = NSApp.applicationIconImage.copy() as? NSImage
    trayIcon?.size = NSSize(width: 18, height: 18)
    trayIcon?.accessibilityDescription = "Vibecrafted"
    item.button?.image =
      trayIcon ?? NSImage(systemSymbolName: "hammer.fill", accessibilityDescription: "Vibecrafted")
    item.button?.imagePosition = .imageOnly

    let menu = NSMenu()
    menu.addItem(
      withTitle: "Open Console", action: #selector(openConsoleFromStatusItem), keyEquivalent: "")
    menu.addItem(
      withTitle: "Open vc-terminal", action: #selector(openTerminalFromStatusItem),
      keyEquivalent: "")
    menu.addItem(.separator())
    menu.addItem(
      withTitle: "Quit", action: #selector(NSApplication.terminate(_:)),
      keyEquivalent: "q")
    item.menu = menu
    statusItem = item
  }

  @objc private func openConsoleFromStatusItem() {
    Task {
      _ = try? await getServerStatus()
      await MainActor.run {
        self.showMainWindowIfNeeded()
      }
    }
  }

  @objc private func openTerminalFromStatusItem() {
    if let process = terminalProcess, process.isRunning {
      NSRunningApplication(processIdentifier: process.processIdentifier)?.activate(options: [])
      return
    }
    launchWorkspaceTerminal()
  }

  private func buildMainMenu() {
    let mainMenu = NSMenu()

    // Application menu
    let appMenu = NSMenu()
    appMenu.addItem(
      withTitle: "About Vibecrafted",
      action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
    appMenu.addItem(.separator())
    appMenu.addItem(
      withTitle: "Hide Vibecrafted", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
    let hideOthers = appMenu.addItem(
      withTitle: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)),
      keyEquivalent: "h")
    hideOthers.keyEquivalentModifierMask = [.command, .option]
    appMenu.addItem(
      withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)),
      keyEquivalent: "")
    appMenu.addItem(.separator())
    appMenu.addItem(
      withTitle: "Quit Vibecrafted", action: #selector(NSApplication.terminate(_:)),
      keyEquivalent: "q")

    let appMenuItem = NSMenuItem()
    appMenuItem.submenu = appMenu
    mainMenu.addItem(appMenuItem)

    // File menu
    let fileMenu = NSMenu(title: "File")
    fileMenu.addItem(
      withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")

    let fileMenuItem = NSMenuItem()
    fileMenuItem.submenu = fileMenu
    mainMenu.addItem(fileMenuItem)

    // View menu
    let viewMenu = NSMenu(title: "View")
    let sidebarItem = viewMenu.addItem(
      withTitle: "Toggle Sidebar", action: #selector(NSSplitViewController.toggleSidebar(_:)),
      keyEquivalent: "s")
    sidebarItem.keyEquivalentModifierMask = [.command, .control]
    let inspectorItem = viewMenu.addItem(
      withTitle: "Toggle Inspector", action: #selector(NSSplitViewController.toggleInspector(_:)),
      keyEquivalent: "i")
    inspectorItem.keyEquivalentModifierMask = [.command, .control]

    let viewMenuItem = NSMenuItem()
    viewMenuItem.submenu = viewMenu
    mainMenu.addItem(viewMenuItem)

    // Window menu
    let windowMenu = NSMenu(title: "Window")
    windowMenu.addItem(
      withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
    windowMenu.addItem(
      withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")

    let windowMenuItem = NSMenuItem()
    windowMenuItem.submenu = windowMenu
    mainMenu.addItem(windowMenuItem)
    NSApp.windowsMenu = windowMenu

    // Help menu
    let helpMenu = NSMenu(title: "Help")
    let helpMenuItem = NSMenuItem()
    helpMenuItem.submenu = helpMenu
    mainMenu.addItem(helpMenuItem)
    NSApp.helpMenu = helpMenu

    NSApp.mainMenu = mainMenu
  }
}
