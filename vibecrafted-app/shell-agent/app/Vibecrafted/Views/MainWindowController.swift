// Vibecrafted — Main Window Controller
// Created by VetCoders

import AppKit

class MainWindowController: NSWindowController, NSToolbarDelegate {
    private let mainViewController = MainSplitViewController()

    private let toolbarSidebarItem = NSToolbarItem.Identifier("toggleSidebar")
    private let toolbarInspectorItem = NSToolbarItem.Identifier("toggleInspector")

    init() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 800),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "Vibecrafted"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.toolbarStyle = .unified
        window.center()
        window.setFrameAutosaveName("VibecraftedMainWindow")
        window.contentViewController = mainViewController
        window.minSize = NSSize(width: 800, height: 600)

        super.init(window: window)

        let toolbar = NSToolbar(identifier: "VibecraftedToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        window.toolbar = toolbar
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError()
    }

    // MARK: - NSToolbarDelegate

    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier itemIdentifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        switch itemIdentifier {
        case toolbarSidebarItem:
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Sidebar"
            item.toolTip = "Toggle Sidebar"
            item.image = NSImage(systemSymbolName: "sidebar.left", accessibilityDescription: "Toggle Sidebar")
            item.target = mainViewController
            item.action = #selector(NSSplitViewController.toggleSidebar(_:))
            return item

        case toolbarInspectorItem:
            let item = NSToolbarItem(itemIdentifier: itemIdentifier)
            item.label = "Inspector"
            item.toolTip = "Toggle Inspector"
            item.image = NSImage(systemSymbolName: "sidebar.right", accessibilityDescription: "Toggle Inspector")
            item.target = mainViewController
            item.action = #selector(NSSplitViewController.toggleInspector(_:))
            return item

        default:
            return nil
        }
    }

    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [toolbarSidebarItem, .flexibleSpace, toolbarInspectorItem]
    }

    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
        [toolbarSidebarItem, .flexibleSpace, toolbarInspectorItem]
    }
}
