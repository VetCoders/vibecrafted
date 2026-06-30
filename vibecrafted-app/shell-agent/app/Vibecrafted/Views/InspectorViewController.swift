// Vibecrafted — Inspector
// Created by Vetcoders
//
// Two modes share the right pane:
//   • Mux server-detail (Restart / Verify Clients / Open Config) — driven by
//     `SelectedServerChanged`, reachable from the Routing-Matrix surface.
//   • Run inspector — driven by `MissionControlSelection`, drills into one
//     dispatched run's REAL artifacts (report.md + transcript tail + header)
//     read off disk through the `loadRunDetail` FFI.
//
// The active mode is chosen by which selection notification arrives, so the
// mux path is never deleted — a run selection swaps in the run inspector, a
// server selection swaps back to the mux detail.

import AppKit

class InspectorViewController: NSViewController {
  // MARK: Mode containers

  private let muxStack = NSStackView()
  private let runStack = NSStackView()
  private let placeholderLabel = NSTextField(labelWithString: "Select a run")

  // MARK: Mux server-detail (existing)

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

  // MARK: Run inspector (new)

  private let runHeaderLabel = NSTextField(labelWithString: "")
  private let reportTextView = NSTextView()
  private let reportScrollView = NSScrollView()
  private let transcriptTextView = NSTextView()
  private let transcriptScrollView = NSScrollView()
  private let openInFinderButton = NSButton(title: "Open in Finder", target: nil, action: nil)

  /// Filesystem path opened by "Open in Finder". Prefers the run's report
  /// path; falls back to the selection's `source_path` when no report exists.
  private var revealPath: String?
  /// Guards against an out-of-order async load clobbering a newer selection.
  private var currentRunId: String?

  override func loadView() {
    let container = NSView()
    container.wantsLayer = true
    view = container

    buildMuxStack()
    buildRunStack()

    placeholderLabel.font = .systemFont(ofSize: 13)
    placeholderLabel.textColor = .secondaryLabelColor
    placeholderLabel.translatesAutoresizingMaskIntoConstraints = false

    muxStack.translatesAutoresizingMaskIntoConstraints = false
    runStack.translatesAutoresizingMaskIntoConstraints = false
    container.addSubview(muxStack)
    container.addSubview(runStack)
    container.addSubview(placeholderLabel)

    for pinned in [muxStack, runStack] {
      NSLayoutConstraint.activate([
        pinned.topAnchor.constraint(equalTo: container.topAnchor),
        pinned.leadingAnchor.constraint(equalTo: container.leadingAnchor),
        pinned.trailingAnchor.constraint(equalTo: container.trailingAnchor),
        pinned.bottomAnchor.constraint(equalTo: container.bottomAnchor),
      ])
    }
    NSLayoutConstraint.activate([
      placeholderLabel.centerXAnchor.constraint(equalTo: container.centerXAnchor),
      placeholderLabel.centerYAnchor.constraint(equalTo: container.centerYAnchor),
    ])

    // Initial state: neither detail bound yet — show the run placeholder, not
    // the mux "No server selected" stack.
    showMode(.placeholder)

    NotificationCenter.default.addObserver(
      self, selector: #selector(handleSelectedServerChanged),
      name: NSNotification.Name("SelectedServerChanged"), object: nil
    )
    NotificationCenter.default.addObserver(
      self, selector: #selector(handleMissionControlSelection),
      name: NSNotification.Name("MissionControlSelection"), object: nil
    )
  }

  // MARK: - Mode switching

  private enum Mode {
    case placeholder
    case mux
    case run
  }

  private func showMode(_ mode: Mode) {
    muxStack.isHidden = mode != .mux
    runStack.isHidden = mode != .run
    placeholderLabel.isHidden = mode != .placeholder
  }

  // MARK: - Mux stack (existing server-detail)

  private func buildMuxStack() {
    nameLabel.font = .boldSystemFont(ofSize: 14)
    for label in [pidLabel, socketLabel, rssLabel, restartsLabel, errorLabel] {
      label.font = .systemFont(ofSize: 12)
      label.textColor = .secondaryLabelColor
    }
    errorLabel.textColor = .systemRed

    restartButton.target = self
    restartButton.action = #selector(restartServiceAction)
    verifyButton.target = self
    verifyButton.action = #selector(verifyClientsAction)
    openConfigButton.target = self
    openConfigButton.action = #selector(openConfig)

    for button in [restartButton, verifyButton, openConfigButton] {
      button.isEnabled = false
      button.bezelStyle = .rounded
    }

    muxStack.orientation = .vertical
    muxStack.alignment = .leading
    muxStack.spacing = 8
    muxStack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)

    muxStack.addArrangedSubview(nameLabel)
    muxStack.addArrangedSubview(pidLabel)
    muxStack.addArrangedSubview(socketLabel)
    muxStack.addArrangedSubview(rssLabel)
    muxStack.addArrangedSubview(restartsLabel)
    muxStack.addArrangedSubview(errorLabel)

    let spacer = NSView()
    spacer.setContentHuggingPriority(.defaultLow, for: .vertical)
    muxStack.addArrangedSubview(spacer)

    let buttonStack = NSStackView(views: [restartButton, verifyButton, openConfigButton])
    buttonStack.orientation = .vertical
    buttonStack.alignment = .leading
    buttonStack.spacing = 8
    muxStack.addArrangedSubview(buttonStack)
  }

  // MARK: - Run stack (new run inspector)

  private func buildRunStack() {
    runHeaderLabel.font = .boldSystemFont(ofSize: 13)
    runHeaderLabel.lineBreakMode = .byTruncatingTail
    runHeaderLabel.maximumNumberOfLines = 2

    let reportTitle = sectionTitle("Report")
    configureReadonlyTextView(reportTextView, in: reportScrollView)
    let transcriptTitle = sectionTitle("Transcript tail")
    configureReadonlyTextView(transcriptTextView, in: transcriptScrollView)

    openInFinderButton.target = self
    openInFinderButton.action = #selector(openInFinderAction)
    openInFinderButton.bezelStyle = .rounded
    openInFinderButton.isEnabled = false

    runStack.orientation = .vertical
    // AppKit NSStackView has no cross-axis `.fill`; keep `.leading` and pin the
    // wide subviews' trailing edge to the stack so the text panes span the full
    // inspector width. Leading comes from the alignment + edge inset.
    runStack.alignment = .leading
    runStack.spacing = 8
    runStack.edgeInsets = NSEdgeInsets(top: 16, left: 16, bottom: 16, right: 16)

    runStack.addArrangedSubview(runHeaderLabel)
    runStack.addArrangedSubview(openInFinderButton)
    runStack.addArrangedSubview(reportTitle)
    runStack.addArrangedSubview(reportScrollView)
    runStack.addArrangedSubview(transcriptTitle)
    runStack.addArrangedSubview(transcriptScrollView)

    // Stretch the text panes (and header/titles) the full inspector width.
    for wide in [runHeaderLabel, reportTitle, transcriptTitle, reportScrollView, transcriptScrollView] {
      wide.trailingAnchor.constraint(equalTo: runStack.trailingAnchor, constant: -16).isActive = true
    }
    reportScrollView.heightAnchor.constraint(greaterThanOrEqualToConstant: 160).isActive = true
    transcriptScrollView.heightAnchor.constraint(greaterThanOrEqualToConstant: 160).isActive = true
  }

  private func sectionTitle(_ text: String) -> NSTextField {
    let label = NSTextField(labelWithString: text)
    label.font = .systemFont(ofSize: 11, weight: .semibold)
    label.textColor = .secondaryLabelColor
    return label
  }

  private func configureReadonlyTextView(_ textView: NSTextView, in scrollView: NSScrollView) {
    scrollView.hasVerticalScroller = true
    scrollView.borderType = .bezelBorder
    textView.isEditable = false
    textView.isSelectable = true
    textView.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
    textView.textContainerInset = NSSize(width: 4, height: 4)
    scrollView.documentView = textView
  }

  // MARK: - Run selection

  @objc private func handleMissionControlSelection(_ notification: Notification) {
    guard let runId = notification.userInfo?["run_id"] as? String, !runId.isEmpty else { return }
    let sourcePath = notification.userInfo?["source_path"] as? String

    currentRunId = runId
    showMode(.run)
    runHeaderLabel.stringValue = "\(runId) · loading…"
    reportTextView.string = ""
    transcriptTextView.string = ""
    revealPath = sourcePath
    openInFinderButton.isEnabled = sourcePath != nil

    // Disk read off the main thread; bind back on main, ignoring stale loads.
    DispatchQueue.global(qos: .userInitiated).async { [weak self] in
      let detail: FfiRunDetail
      do {
        detail = try loadRunDetail(runId: runId)
      } catch {
        DispatchQueue.main.async {
          guard let self, self.currentRunId == runId else { return }
          self.runHeaderLabel.stringValue = "\(runId) · failed to load"
          self.reportTextView.string = "Could not read run detail: \(error)"
        }
        return
      }
      DispatchQueue.main.async {
        guard let self, self.currentRunId == runId else { return }
        self.bindRunDetail(detail, fallbackRevealPath: sourcePath)
      }
    }
  }

  @MainActor
  private func bindRunDetail(_ detail: FfiRunDetail, fallbackRevealPath: String?) {
    runHeaderLabel.stringValue = runHeaderText(detail)

    if let report = detail.reportMd, !report.isEmpty {
      reportTextView.string = report
    } else {
      reportTextView.string = "No report.md for this run yet."
    }
    reportTextView.scrollToBeginningOfDocument(nil)

    if detail.transcriptTail.isEmpty {
      transcriptTextView.string = "No transcript captured for this run."
    } else {
      transcriptTextView.string = detail.transcriptTail
      transcriptTextView.scrollToEndOfDocument(nil)
    }

    // Prefer the real report path; fall back to the snapshot's source path.
    revealPath = detail.reportPath ?? detail.transcriptPath ?? fallbackRevealPath
    openInFinderButton.isEnabled = revealPath != nil
  }

  private func runHeaderText(_ detail: FfiRunDetail) -> String {
    var parts = [detail.runId]
    if let agent = detail.agent, !agent.isEmpty { parts.append(agent) }
    if let skill = detail.skill, !skill.isEmpty { parts.append(skill) }
    if let state = detail.state, !state.isEmpty { parts.append(state) }
    return parts.joined(separator: " · ")
  }

  @objc private func openInFinderAction() {
    guard let path = revealPath else { return }
    NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
  }

  // MARK: - Mux selection (existing)

  @objc private func handleSelectedServerChanged(_ notification: Notification) {
    if let name = notification.userInfo?["serverName"] as? String {
      currentServerName = name
      showMode(.mux)
      nameLabel.stringValue = name
      // Dummy details since FFI doesn't provide them yet
      pidLabel.stringValue = "PID: unknown"
      socketLabel.stringValue = "Socket: auto"
      rssLabel.stringValue = "RSS: --"
      restartsLabel.stringValue = "Restarts: --"
      errorLabel.stringValue = ""

      for button in [restartButton, verifyButton, openConfigButton] {
        button.isEnabled = true
      }
    } else {
      currentServerName = nil
      nameLabel.stringValue = "No server selected"
      pidLabel.stringValue = ""
      socketLabel.stringValue = ""
      rssLabel.stringValue = ""
      restartsLabel.stringValue = ""
      errorLabel.stringValue = ""

      for button in [restartButton, verifyButton, openConfigButton] {
        button.isEnabled = false
      }
      // No server and no run bound yet → fall back to the run placeholder.
      showMode(currentRunId == nil ? .placeholder : .run)
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
