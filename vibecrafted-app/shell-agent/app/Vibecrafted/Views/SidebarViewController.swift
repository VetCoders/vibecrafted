// Vibecrafted — Sidebar
// Created by VetCoders

import AppKit

class SidebarViewController: NSViewController, NSTableViewDataSource, NSTableViewDelegate {
    private let scrollView = NSScrollView()
    private let tableView = NSTableView()

    private var servers: [FfiServerStatus] = []

    override func loadView() {
        let container = NSView()
        container.wantsLayer = true
        view = container

        scrollView.hasVerticalScroller = true
        scrollView.borderType = .noBorder

        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("ServerColumn"))
        column.title = "Servers"
        tableView.addTableColumn(column)
        tableView.headerView = nil
        tableView.dataSource = self
        tableView.delegate = self
        tableView.rowHeight = 24
        tableView.style = .sourceList

        scrollView.documentView = tableView
        scrollView.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(scrollView)

        NSLayoutConstraint.activate([
            scrollView.topAnchor.constraint(equalTo: container.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: container.bottomAnchor),
        ])

        NotificationCenter.default.addObserver(
            self, selector: #selector(handleIpcEvent),
            name: NSNotification.Name("IpcEvent"), object: nil
        )

        Task {
            do {
                servers = try await getServerStatus()
                tableView.reloadData()
            } catch {
                print("Failed to get initial server status: \(error)")
            }
        }
    }

    @objc private func handleIpcEvent(_ notification: Notification) {
        // Refresh server list on state changes
        Task {
            do {
                let newServers = try await getServerStatus()
                self.servers = newServers
                self.tableView.reloadData()
            } catch {
                print("Failed to get server status: \(error)")
            }
        }
    }

    // MARK: - NSTableViewDataSource

    func numberOfRows(in tableView: NSTableView) -> Int {
        servers.count
    }

    // MARK: - NSTableViewDelegate

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let server = servers[row]
        let identifier = NSUserInterfaceItemIdentifier("ServerCell")
        var cell = tableView.makeView(withIdentifier: identifier, owner: self) as? NSTableCellView

        if cell == nil {
            cell = NSTableCellView()
            cell?.identifier = identifier

            let imageView = NSImageView()
            imageView.translatesAutoresizingMaskIntoConstraints = false
            imageView.symbolConfiguration = NSImage.SymbolConfiguration(pointSize: 12, weight: .regular)

            let textField = NSTextField(labelWithString: "")
            textField.translatesAutoresizingMaskIntoConstraints = false

            cell?.addSubview(imageView)
            cell?.addSubview(textField)
            cell?.imageView = imageView
            cell?.textField = textField

            NSLayoutConstraint.activate([
                imageView.leadingAnchor.constraint(equalTo: cell!.leadingAnchor, constant: 4),
                imageView.centerYAnchor.constraint(equalTo: cell!.centerYAnchor),
                imageView.widthAnchor.constraint(equalToConstant: 16),
                imageView.heightAnchor.constraint(equalToConstant: 16),

                textField.leadingAnchor.constraint(equalTo: imageView.trailingAnchor, constant: 6),
                textField.centerYAnchor.constraint(equalTo: cell!.centerYAnchor),
                textField.trailingAnchor.constraint(equalTo: cell!.trailingAnchor, constant: -4)
            ])
        }

        cell?.textField?.stringValue = server.name

        let statusGlyph: String
        let color: NSColor

        if server.status == "Idle" || server.status == "Routing" || server.status == "Saturated" {
            statusGlyph = "circle.fill"
            color = server.status == "Saturated" ? .systemYellow : .systemGreen
        } else {
            statusGlyph = "circle.fill"
            color = .systemRed
        }

        cell?.imageView?.image = NSImage(systemSymbolName: statusGlyph, accessibilityDescription: server.status)
        cell?.imageView?.contentTintColor = color

        return cell
    }

    func tableViewSelectionDidChange(_ notification: Notification) {
        let row = tableView.selectedRow
        if row >= 0 && row < servers.count {
            let serverName = servers[row].name
            NotificationCenter.default.post(
                name: NSNotification.Name("SelectedServerChanged"), object: nil,
                userInfo: ["serverName": serverName]
            )
        } else {
            NotificationCenter.default.post(
                name: NSNotification.Name("SelectedServerChanged"), object: nil,
                userInfo: nil
            )
        }
    }
}
