// Vibecrafted — Inspector
// Created by VetCoders

import AppKit

class InspectorViewController: NSViewController {
    private let stackView = NSStackView()
    private let nameLabel = NSTextField(labelWithString: "No server selected")
    private let pidLabel = NSTextField(labelWithString: "")
    private let socketLabel = NSTextField(labelWithString: "")
    private let rssLabel = NSTextField(labelWithString: "")
    private let restartsLabel = NSTextField(labelWithString: "")
    private let errorLabel = NSTextField(labelWithString: "")

    private let restartButton = NSButton(title: "Restart", target: nil, action: nil)
    private let verifyButton = NSButton(title: "Verify Clients", target: nil, action: nil)
    private let openConfigButton = NSButton(title: "Open Config", target: nil, action: nil)

    private var currentServerName: String?

    override func loadView() {
        let container = NSView()
        container.wantsLayer = true
        view = container

        nameLabel.font = .boldSystemFont(ofSize: 14)
        [pidLabel, socketLabel, rssLabel, restartsLabel, errorLabel].forEach {
            $0.font = .systemFont(ofSize: 12)
            $0.textColor = .secondaryLabelColor
        }

        errorLabel.textColor = .systemRed

        restartButton.target = self
        restartButton.action = #selector(restartServiceAction)

        verifyButton.target = self
        verifyButton.action = #selector(verifyClientsAction)

        openConfigButton.target = self
        openConfigButton.action = #selector(openConfig)

        [restartButton, verifyButton, openConfigButton].forEach {
            $0.isEnabled = false
            $0.bezelStyle = .rounded
        }

        stackView.orientation = .vertical
        stackView.alignment = .leading
        stackView.spacing = 8
        stackView.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)
        stackView.translatesAutoresizingMaskIntoConstraints = false

        stackView.addArrangedSubview(nameLabel)
        stackView.addArrangedSubview(pidLabel)
        stackView.addArrangedSubview(socketLabel)
        stackView.addArrangedSubview(rssLabel)
        stackView.addArrangedSubview(restartsLabel)
        stackView.addArrangedSubview(errorLabel)

        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
        stackView.addArrangedSubview(spacer)

        let buttonStack = NSStackView(views: [restartButton, verifyButton, openConfigButton])
        buttonStack.orientation = .vertical
        buttonStack.alignment = .leading
        buttonStack.spacing = 8
        stackView.addArrangedSubview(buttonStack)

        container.addSubview(stackView)

        NSLayoutConstraint.activate([
            stackView.topAnchor.constraint(equalTo: container.topAnchor),
            stackView.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            stackView.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            stackView.bottomAnchor.constraint(equalTo: container.bottomAnchor),
        ])

        NotificationCenter.default.addObserver(
            self, selector: #selector(handleSelectedServerChanged),
            name: NSNotification.Name("SelectedServerChanged"), object: nil
        )
    }

    @objc private func handleSelectedServerChanged(_ notification: Notification) {
        if let name = notification.userInfo?["serverName"] as? String {
            currentServerName = name
            nameLabel.stringValue = name
            // Dummy details since FFI doesn't provide them yet
            pidLabel.stringValue = "PID: unknown"
            socketLabel.stringValue = "Socket: auto"
            rssLabel.stringValue = "RSS: --"
            restartsLabel.stringValue = "Restarts: --"
            errorLabel.stringValue = ""

            [restartButton, verifyButton, openConfigButton].forEach { $0.isEnabled = true }
        } else {
            currentServerName = nil
            nameLabel.stringValue = "No server selected"
            pidLabel.stringValue = ""
            socketLabel.stringValue = ""
            rssLabel.stringValue = ""
            restartsLabel.stringValue = ""
            errorLabel.stringValue = ""

            [restartButton, verifyButton, openConfigButton].forEach { $0.isEnabled = false }
        }
    }

    @objc private func restartServiceAction() {
        guard let name = currentServerName else { return }
        Task {
            do {
                try await restartService(name: name)
            } catch {
                DispatchQueue.main.async {
                    self.errorLabel.stringValue = "Restart failed: \(error)"
                }
            }
        }
    }

    @objc private func verifyClientsAction() {
        guard currentServerName != nil else { return }
        Task {
            do {
                let res = try await verifyClient(kind: .codex)
                DispatchQueue.main.async {
                    let alert = NSAlert()
                    alert.messageText = "Verify Results"
                    alert.informativeText = "Status: \(res.ok ? "OK" : "Failed")\nDetail: \(res.detail)"
                    alert.runModal()
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorLabel.stringValue = "Verify failed: \(error)"
                }
            }
        }
    }

    @objc private func openConfig() {
        // Not implemented in FFI yet
    }
}
