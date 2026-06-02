import AppKit

final class EventObserver: @unchecked Sendable, EventCallback {
    func onEvent(eventJson: String) {
        DispatchQueue.main.async {
            NotificationCenter.default.post(name: NSNotification.Name("IpcEvent"), object: nil, userInfo: ["eventJson": eventJson])
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

        showMainWindowIfNeeded()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
        true
    }

    // MARK: - Main Menu

    private func buildStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.image = NSImage(systemSymbolName: "hammer.fill", accessibilityDescription: "Vibecrafted")
        item.button?.imagePosition = .imageLeading
        item.button?.title = "Vibecrafted"

        let menu = NSMenu()
        menu.addItem(withTitle: "Open Console", action: #selector(openConsoleFromStatusItem), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Vibecrafted", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
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
        appMenu.addItem(withTitle: "About Vibecrafted", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide Vibecrafted", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = appMenu.addItem(withTitle: "Hide Others", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: "Show All", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Vibecrafted", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")

        let appMenuItem = NSMenuItem()
        appMenuItem.submenu = appMenu
        mainMenu.addItem(appMenuItem)

        // File menu
        let fileMenu = NSMenu(title: "File")
        fileMenu.addItem(withTitle: "Close Window", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")

        let fileMenuItem = NSMenuItem()
        fileMenuItem.submenu = fileMenu
        mainMenu.addItem(fileMenuItem)

        // View menu
        let viewMenu = NSMenu(title: "View")
        let sidebarItem = viewMenu.addItem(withTitle: "Toggle Sidebar", action: #selector(NSSplitViewController.toggleSidebar(_:)), keyEquivalent: "s")
        sidebarItem.keyEquivalentModifierMask = [.command, .control]
        let inspectorItem = viewMenu.addItem(withTitle: "Toggle Inspector", action: #selector(NSSplitViewController.toggleInspector(_:)), keyEquivalent: "i")
        inspectorItem.keyEquivalentModifierMask = [.command, .control]

        let viewMenuItem = NSMenuItem()
        viewMenuItem.submenu = viewMenu
        mainMenu.addItem(viewMenuItem)

        // Window menu
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")

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
