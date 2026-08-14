import AppKit

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
    showMainWindowIfNeeded()
  }

  func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    true
  }

  func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    true
  }

  private func launchWorkspaceTerminal() {
    if terminalProcess?.isRunning == true {
      return
    }

    let appRoot = Bundle.main.bundleURL
    let terminal = appRoot.appendingPathComponent("Contents/Helpers/vc-terminal")
    let frame = appRoot.appendingPathComponent("Contents/Helpers/vc-frame")
    let config = appRoot.appendingPathComponent(
      "Contents/Resources/terminal/vibecrafted.toml")
    let start = appRoot.appendingPathComponent("Contents/Resources/runtime/bin/vc-start")
    for required in [terminal, frame, start] where !FileManager.default.isExecutableFile(
      atPath: required.path)
    {
      print("Bundled product entry is missing or not executable: \(required.path)")
      return
    }
    guard FileManager.default.fileExists(atPath: config.path) else {
      print("Bundled terminal config is missing: \(config.path)")
      return
    }

    let host = ProcessInfo.processInfo.environment
    let home = host["HOME"] ?? FileManager.default.homeDirectoryForCurrentUser.path
    let runtimeHome =
      host["VIBECRAFTED_RUNTIME_HOME"]
      ?? host["XDG_DATA_HOME"].map { "\($0)/vibecrafted" }
      ?? "\(home)/.local/share/vibecrafted"
    do {
      try FileManager.default.createDirectory(
        atPath: runtimeHome, withIntermediateDirectories: true)
    } catch {
      print("Cannot create Vibecrafted runtime home \(runtimeHome): \(error)")
      return
    }

    let inherited = [
      "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "COLORTERM", "TMPDIR",
      "SHELL",
    ]
    var environment = Dictionary(
      uniqueKeysWithValues: inherited.compactMap { key in host[key].map { (key, $0) } })
    environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["VIBECRAFTED_RUNTIME_HOME"] = runtimeHome
    environment["VIBECRAFTED_APP_ROOT"] = appRoot.path
    environment["VIBECRAFTED_VC_FRAME_BIN"] = frame.path

    let process = Process()
    process.executableURL = terminal
    process.arguments = [
      "--config-file", config.path,
      "-e", start.path, "operator",
    ]
    process.environment = environment
    do {
      try process.run()
      terminalProcess = process
    } catch {
      print("Failed to launch bundled vc-terminal: \(error)")
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
    menu.addItem(.separator())
    menu.addItem(
      withTitle: "Quit Vibecrafted", action: #selector(NSApplication.terminate(_:)),
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
