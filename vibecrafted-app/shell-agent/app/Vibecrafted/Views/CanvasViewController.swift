// Vibecrafted — Canvas View (Routing Matrix / Log Tail)
// Created by VetCoders

import AppKit

class CanvasViewController: NSViewController, NSTableViewDataSource, NSTableViewDelegate {
    private let segmentedControl = NSSegmentedControl(labels: ["Routing Matrix", "Log Tail"], trackingMode: .selectOne, target: nil, action: nil)

    // Routing Matrix
    private let matrixScrollView = NSScrollView()
    private let matrixTableView = NSTableView()
    private var routes: [FfiRoute] = []

    // Log Tail
    private let logScrollView = NSScrollView()
    private let logTextView = NSTextView()

    private var currentServerName: String?

    override func loadView() {
        let container = NSView()
        container.wantsLayer = true
        view = container

        segmentedControl.selectedSegment = 0
        segmentedControl.target = self
        segmentedControl.action = #selector(segmentChanged(_:))
        segmentedControl.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(segmentedControl)

        // Matrix setup
        matrixScrollView.hasVerticalScroller = true
        matrixScrollView.borderType = .bezelBorder

        let clientCol = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("Client"))
        clientCol.title = "Client"
        clientCol.width = 100
        matrixTableView.addTableColumn(clientCol)

        let serverCol = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("Server"))
        serverCol.title = "Server"
        serverCol.width = 150
        matrixTableView.addTableColumn(serverCol)

        let stateCol = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("State"))
        stateCol.title = "State"
        stateCol.width = 100
        matrixTableView.addTableColumn(stateCol)

        matrixTableView.dataSource = self
        matrixTableView.delegate = self
        matrixScrollView.documentView = matrixTableView
        matrixScrollView.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(matrixScrollView)

        // Log setup
        logScrollView.hasVerticalScroller = true
        logScrollView.borderType = .bezelBorder
        logTextView.isEditable = false
        logTextView.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        logScrollView.documentView = logTextView
        logScrollView.translatesAutoresizingMaskIntoConstraints = false
        logScrollView.isHidden = true
        container.addSubview(logScrollView)

        NSLayoutConstraint.activate([
            segmentedControl.topAnchor.constraint(equalTo: container.topAnchor, constant: 12),
            segmentedControl.centerXAnchor.constraint(equalTo: container.centerXAnchor),

            matrixScrollView.topAnchor.constraint(equalTo: segmentedControl.bottomAnchor, constant: 12),
            matrixScrollView.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 12),
            matrixScrollView.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -12),
            matrixScrollView.bottomAnchor.constraint(equalTo: container.bottomAnchor, constant: -12),

            logScrollView.topAnchor.constraint(equalTo: segmentedControl.bottomAnchor, constant: 12),
            logScrollView.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 12),
            logScrollView.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -12),
            logScrollView.bottomAnchor.constraint(equalTo: container.bottomAnchor, constant: -12),
        ])

        NotificationCenter.default.addObserver(
            self, selector: #selector(handleIpcEvent),
            name: NSNotification.Name("IpcEvent"), object: nil
        )
        NotificationCenter.default.addObserver(
            self, selector: #selector(handleSelectedServerChanged),
            name: NSNotification.Name("SelectedServerChanged"), object: nil
        )

        refreshRoutes()
    }

    @objc private func segmentChanged(_ sender: NSSegmentedControl) {
        let isMatrix = sender.selectedSegment == 0
        matrixScrollView.isHidden = !isMatrix
        logScrollView.isHidden = isMatrix
        if !isMatrix {
            refreshLogs()
        }
    }

    @objc private func handleIpcEvent(_ notification: Notification) {
        refreshRoutes()
    }

    @objc private func handleSelectedServerChanged(_ notification: Notification) {
        currentServerName = notification.userInfo?["serverName"] as? String
        if segmentedControl.selectedSegment == 1 {
            refreshLogs()
        }
    }

    private func refreshRoutes() {
        Task {
            do {
                self.routes = try await getRoutes()
                self.matrixTableView.reloadData()
            } catch {
                print("Failed to get routes: \(error)")
            }
        }
    }

    private func refreshLogs() {
        guard let server = currentServerName else {
            logTextView.string = "No server selected."
            return
        }
        Task {
            do {
                let lines = try await getRecentLogs(service: server, lines: 100)
                self.logTextView.string = lines.joined(separator: "\n")
                self.logTextView.scrollToEndOfDocument(nil)
            } catch {
                self.logTextView.string = "Failed to load logs: \(error)"
            }
        }
    }

    // MARK: - NSTableViewDataSource

    func numberOfRows(in tableView: NSTableView) -> Int {
        routes.count
    }

    // MARK: - NSTableViewDelegate

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let route = routes[row]
        let identifier = tableColumn?.identifier ?? NSUserInterfaceItemIdentifier("")
        var cell = tableView.makeView(withIdentifier: identifier, owner: self) as? NSTableCellView

        if cell == nil {
            cell = NSTableCellView()
            cell?.identifier = identifier
            let textField = NSTextField(labelWithString: "")
            textField.translatesAutoresizingMaskIntoConstraints = false
            cell?.addSubview(textField)
            cell?.textField = textField
            NSLayoutConstraint.activate([
                textField.leadingAnchor.constraint(equalTo: cell!.leadingAnchor, constant: 4),
                textField.centerYAnchor.constraint(equalTo: cell!.centerYAnchor),
                textField.trailingAnchor.constraint(equalTo: cell!.trailingAnchor, constant: -4)
            ])
        }

        if identifier.rawValue == "Client" {
            cell?.textField?.stringValue = String(describing: route.client)
        } else if identifier.rawValue == "Server" {
            cell?.textField?.stringValue = route.service
        } else if identifier.rawValue == "State" {
            cell?.textField?.stringValue = route.state
        }

        return cell
    }
}
