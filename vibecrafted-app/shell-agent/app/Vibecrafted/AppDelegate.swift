import AppKit
import CoreText
import Darwin

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
      print("Cannot publish the canonical Vibecrafted runtime: \(error)")
      return
    }

    for required in [
      install.terminal, install.terminalHost, install.frame, install.start,
      install.primaryShell,
    ]
      where !FileManager.default.isExecutableFile(
      atPath: required.path)
    {
      print("Bundled product entry is missing or not executable: \(required.path)")
      return
    }
    guard FileManager.default.fileExists(atPath: install.terminalConfig.path) else {
      print("Canonical terminal config is missing: \(install.terminalConfig.path)")
      return
    }
    do {
      try registerBundledFonts()
    } catch {
      print("Cannot register the bundled terminal font: \(error)")
      return
    }

    let host = ProcessInfo.processInfo.environment
    let inherited = [
      "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "COLORTERM", "TMPDIR",
      "SHELL",
    ]
    var environment = Dictionary(
      uniqueKeysWithValues: inherited.compactMap { key in host[key].map { (key, $0) } })
    environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
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
      print("Failed to launch bundled vc-terminal: \(error)")
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
    if !manager.fileExists(atPath: productShell.path) {
      try manager.copyItem(at: sourceShell, to: productShell)
    }
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
      "export PATH=\(shellQuote("\(generation.appendingPathComponent("bin").path):/usr/bin:/bin:/usr/sbin:/sbin"))",
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
        userInfo: [NSLocalizedDescriptionKey: "symlink is forbidden: \(root.path)"])
    }
    guard let enumerator = FileManager.default.enumerator(
      at: root, includingPropertiesForKeys: keys, options: [], errorHandler: nil)
    else { return }
    for case let item as URL in enumerator {
      if try item.resourceValues(forKeys: Set(keys)).isSymbolicLink == true {
        throw NSError(
          domain: "io.vetcoders.vibecrafted.install", code: 3,
          userInfo: [NSLocalizedDescriptionKey: "symlink is forbidden in runtime: \(item.path)"])
      }
    }
  }

  private func shellQuote(_ value: String) -> String {
    "'\(value.replacingOccurrences(of: "'", with: "'\"'\"'"))'"
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
