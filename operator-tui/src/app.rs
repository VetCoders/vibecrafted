use crate::config::{AppConfig, path_display};
use crate::launch::{
    LaunchCommand, LaunchKind, LaunchRequest, LaunchRuntime, build_launch_command,
};
use crate::state::{ControlPlaneState, RenderedRun, RunKind, render_runs};
use std::collections::BTreeMap;
use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchFocus {
    Browse,
    EditPrompt,
    DeepControls,
    Help,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DeepAction {
    AttachSession(String),
    ResumeSession { agent: String, session: String },
    OpenReport(PathBuf),
    OpenTranscript(PathBuf),
    OpenRoot(PathBuf),
}

impl DeepAction {
    pub fn label(&self) -> String {
        match self {
            DeepAction::AttachSession(session) => {
                format!("Attach operator session: vibecrafted dashboard attach {session}")
            }
            DeepAction::ResumeSession { agent, session } => {
                format!("Resume agent session: vibecrafted resume {agent} --session {session}")
            }
            DeepAction::OpenReport(path) => {
                format!("Open latest report: {}", path.to_string_lossy())
            }
            DeepAction::OpenTranscript(path) => {
                format!("Open latest transcript: {}", path.to_string_lossy())
            }
            DeepAction::OpenRoot(path) => format!("Open run root: {}", path.to_string_lossy()),
        }
    }
}

#[derive(Debug)]
pub struct App {
    pub config: AppConfig,
    pub state: ControlPlaneState,
    pub runs: Vec<RenderedRun>,
    pub selected: usize,
    pub launch_kind: LaunchKind,
    pub launch_agent: usize,
    pub launch_prompt: String,
    pub launch_runtime: LaunchRuntime,
    pub focus: LaunchFocus,
    pub status_line: String,
    pub launch_history: Vec<String>,
    pub deep_selected: usize,
}

impl App {
    pub fn new(config: AppConfig) -> anyhow::Result<Self> {
        let state = ControlPlaneState::load(&config.state_root)
            .unwrap_or_else(|_| ControlPlaneState::empty(&config.state_root));
        let runs = render_runs(&state);
        let launch_runtime = config.launch_runtime;
        let mut app = Self {
            config,
            state,
            runs,
            selected: 0,
            launch_kind: LaunchKind::Workflow,
            launch_agent: 0,
            launch_prompt: default_prompt(LaunchKind::Workflow),
            launch_runtime,
            focus: LaunchFocus::Browse,
            status_line: String::new(),
            launch_history: Vec::new(),
            deep_selected: 0,
        };
        app.sync_selection();
        Ok(app)
    }

    pub fn refresh(&mut self) {
        let state = ControlPlaneState::load(&self.config.state_root)
            .unwrap_or_else(|_| ControlPlaneState::empty(&self.config.state_root));
        self.state = state;
        self.runs = render_runs(&self.state);
        self.sync_selection();
    }

    pub fn selected_run(&self) -> Option<&RenderedRun> {
        self.runs.get(self.selected)
    }

    pub fn set_launch_kind(&mut self, kind: LaunchKind) {
        self.launch_kind = kind;
        self.launch_prompt = default_prompt(kind);
        self.focus = LaunchFocus::Browse;
    }

    pub fn cycle_agent(&mut self) {
        self.launch_agent = (self.launch_agent + 1) % agents().len();
    }

    pub fn cycle_runtime(&mut self) {
        self.launch_runtime = self.launch_runtime.cycle();
    }

    pub fn selected_agent(&self) -> &'static str {
        agents()[self.launch_agent]
    }

    pub fn launch_request(&self) -> LaunchRequest {
        LaunchRequest {
            kind: self.launch_kind,
            agent: self.selected_agent().to_string(),
            prompt: self.launch_prompt.clone(),
            runtime: self.launch_runtime,
            root: Some(self.config.launch_root.clone()),
            count: Some(3),
            depth: Some(3),
        }
    }

    pub fn launch_command(&self) -> LaunchCommand {
        build_launch_command(&self.config.command_deck, &self.launch_request())
    }

    pub fn append_status<S: Into<String>>(&mut self, status: S) {
        self.status_line = status.into();
    }

    pub fn push_launch_history<S: Into<String>>(&mut self, entry: S) {
        self.launch_history.push(entry.into());
        if self.launch_history.len() > 6 {
            self.launch_history.drain(0..self.launch_history.len() - 6);
        }
    }

    pub fn move_selection(&mut self, delta: isize) {
        if self.runs.is_empty() {
            self.selected = 0;
            return;
        }
        let len = self.runs.len() as isize;
        let mut index = self.selected as isize + delta;
        if index < 0 {
            index = len - 1;
        }
        if index >= len {
            index = 0;
        }
        self.selected = index as usize;
    }

    pub fn sync_selection(&mut self) {
        if self.selected >= self.runs.len() && !self.runs.is_empty() {
            self.selected = self.runs.len() - 1;
        }
        let deep_len = self.deep_actions().len();
        if deep_len == 0 {
            self.deep_selected = 0;
            if self.focus == LaunchFocus::DeepControls {
                self.focus = LaunchFocus::Browse;
            }
        } else if self.deep_selected >= deep_len {
            self.deep_selected = deep_len - 1;
        }
    }

    pub fn status_summary(&self) -> String {
        if self.runs.is_empty() {
            return "no runs loaded yet".to_string();
        }
        let mut counts = BTreeMap::new();
        for run in &self.runs {
            *counts.entry(run.kind.label()).or_insert(0usize) += 1;
        }
        let mut parts = vec![format!("runs: {}", self.runs.len())];
        for label in [
            "active",
            "stalled",
            "failed",
            "paused",
            "recent",
            "completed",
            "unknown",
        ] {
            if let Some(count) = counts.get(label)
                && *count > 0
            {
                parts.push(format!("{label} {count}"));
            }
        }
        parts.join(" | ")
    }

    pub fn detail_lines(&self) -> Vec<String> {
        let Some(run) = self.selected_run() else {
            return vec![
                "No runs found in the control-plane state directory yet.".to_string(),
                String::new(),
                "Start here:".to_string(),
                "1 -> Workflow for the normal path".to_string(),
                "2 -> Research swarm if the surface is still unclear".to_string(),
                "3 -> Review if something already exists and needs truth".to_string(),
                "4 -> Marbles when the system works but still drifts".to_string(),
                String::new(),
                "Use a / v / e / Enter in the launch panel below.".to_string(),
                "Press ? for the in-app operator guide.".to_string(),
                String::new(),
                format!("State root: {}", path_display(&self.config.state_root)),
                format!("Launch root: {}", path_display(&self.config.launch_root)),
            ];
        };

        let snapshot = &run.snapshot;
        let mut lines = vec![
            format!("run_id: {}", snapshot.run_id),
            format!(
                "status: {} ({})",
                run.kind.label(),
                snapshot.display_state()
            ),
            format!("agent: {}", snapshot.agent.as_deref().unwrap_or("unknown")),
            format!("skill: {}", snapshot.skill.as_deref().unwrap_or("unknown")),
            format!("mode: {}", snapshot.mode.as_deref().unwrap_or("unknown")),
            format!("age: {}", run.age_label),
            format!(
                "operator_session: {}",
                snapshot.operator_session.as_deref().unwrap_or("none")
            ),
        ];
        if let Some(session_id) = snapshot.session_id.as_deref() {
            lines.push(format!("session_id: {session_id}"));
        }

        if let Some(root) = snapshot.root.as_deref() {
            lines.push(format!("root: {root}"));
        }
        if let Some(report) = snapshot.latest_report.as_deref() {
            lines.push(format!("latest_report: {report}"));
        }
        if let Some(transcript) = snapshot.latest_transcript.as_deref() {
            lines.push(format!("latest_transcript: {transcript}"));
        }
        if let Some(error) = snapshot.last_error.as_deref() {
            lines.push(format!("last_error: {error}"));
        }
        if let Some(session) = snapshot.operator_session.as_deref() {
            lines.push(String::new());
            lines.push(format!(
                "Attach hint: vibecrafted dashboard attach {session}"
            ));
            lines.push(format!("Zellij hint: zellij attach {session}"));
        }
        if let Some(agent) = snapshot.agent.as_deref() {
            lines.push(format!("Resume hint: vibecrafted resume {agent}"));
        }
        lines.push(String::new());
        lines.push(format!(
            "State root: {}",
            path_display(&self.config.state_root)
        ));
        lines
    }

    pub fn event_lines(&self) -> Vec<String> {
        let Some(run) = self.selected_run() else {
            return Vec::new();
        };
        if run.recent_events.is_empty() {
            return vec!["No recent events for this run.".to_string()];
        }
        run.recent_events
            .iter()
            .map(|event| {
                let message = event.message.as_deref().unwrap_or(event.kind.as_str());
                format!("{} {}", event.ts, message)
            })
            .collect()
    }

    pub fn prompt_lines(&self) -> Vec<String> {
        let command_preview = self.launch_command().command_line();
        let mut lines = vec![
            format!(
                "{}  {}",
                self.launch_kind.human_title(),
                self.launch_kind.human_description()
            ),
            format!(
                "agent: {}  runtime: {}",
                self.selected_agent(),
                self.launch_runtime.label()
            ),
            format!("prompt: {}", self.launch_prompt),
            String::new(),
            "Keys: 1 workflow  2 research  3 review  4 marbles".to_string(),
            "      a cycle agent  v cycle runtime  e edit prompt  Enter launch".to_string(),
            String::new(),
            format!("root: {}", path_display(&self.config.launch_root)),
            format!("command: {}", command_preview),
        ];
        if let Some(last) = self.launch_history.last() {
            lines.push(String::new());
            lines.push(format!("last launch: {last}"));
        }
        lines
    }

    pub fn help_lines(&self) -> Vec<String> {
        vec![
            "Operator guide".to_string(),
            String::new(),
            "This console is the human front door into Vibecrafted control-plane state.".to_string(),
            "Browse runs on the left, inspect truth on the right, and launch new work below.".to_string(),
            String::new(),
            "Quick start".to_string(),
            "1 Workflow  -> normal path for most tasks".to_string(),
            "2 Research  -> send a research swarm first".to_string(),
            "3 Review    -> audit an existing surface".to_string(),
            "4 Marbles   -> convergence loop for fragile systems".to_string(),
            String::new(),
            "Keys".to_string(),
            "↑/↓ or j/k  move through runs".to_string(),
            "a           cycle launch agent".to_string(),
            "v           cycle runtime (terminal / visible / headless)".to_string(),
            "e           edit launch prompt".to_string(),
            "Enter       launch selected action".to_string(),
            "d           selected-run deep controls".to_string(),
            "r           refresh control-plane state".to_string(),
            "?           close this guide".to_string(),
            "q / Esc     quit".to_string(),
            String::new(),
            "Operator rule".to_string(),
            "Use this to decide and launch. Let worker agents execute; do not overload the shell as your only dashboard.".to_string(),
        ]
    }

    pub fn active_run_count(&self) -> usize {
        self.runs
            .iter()
            .filter(|run| matches!(run.kind, RunKind::Active | RunKind::Stalled))
            .count()
    }

    pub fn deep_actions(&self) -> Vec<DeepAction> {
        let Some(run) = self.selected_run() else {
            return Vec::new();
        };
        let snapshot = &run.snapshot;
        let mut actions = Vec::new();
        if let Some(session) = snapshot
            .operator_session
            .as_ref()
            .filter(|value| !value.is_empty())
        {
            actions.push(DeepAction::AttachSession(session.clone()));
        }
        if let (Some(agent), Some(session)) = (
            snapshot.agent.as_ref().filter(|value| !value.is_empty()),
            snapshot
                .session_id
                .as_ref()
                .filter(|value| !value.is_empty()),
        ) {
            actions.push(DeepAction::ResumeSession {
                agent: agent.clone(),
                session: session.clone(),
            });
        }
        if let Some(report) = snapshot
            .latest_report
            .as_ref()
            .filter(|value| !value.is_empty())
        {
            actions.push(DeepAction::OpenReport(PathBuf::from(report)));
        }
        if let Some(transcript) = snapshot
            .latest_transcript
            .as_ref()
            .filter(|value| !value.is_empty())
        {
            actions.push(DeepAction::OpenTranscript(PathBuf::from(transcript)));
        }
        if let Some(root) = snapshot.root.as_ref().filter(|value| !value.is_empty()) {
            actions.push(DeepAction::OpenRoot(PathBuf::from(root)));
        }
        actions
    }

    pub fn selected_deep_action(&self) -> Option<DeepAction> {
        self.deep_actions().get(self.deep_selected).cloned()
    }

    pub fn move_deep_selection(&mut self, delta: isize) {
        let len = self.deep_actions().len();
        if len == 0 {
            self.deep_selected = 0;
            return;
        }
        let len = len as isize;
        let mut index = self.deep_selected as isize + delta;
        if index < 0 {
            index = len - 1;
        }
        if index >= len {
            index = 0;
        }
        self.deep_selected = index as usize;
    }

    pub fn deep_control_lines(&self) -> Vec<String> {
        let actions = self.deep_actions();
        if actions.is_empty() {
            return vec![
                "Deep controls".to_string(),
                "No attach/resume/report actions are available for the selected run.".to_string(),
                "Pick another run or launch a fresh one below.".to_string(),
            ];
        }
        let mut lines = vec![
            "Deep controls".to_string(),
            "Enter runs the selected action. Esc returns to browse.".to_string(),
            String::new(),
        ];
        lines.extend(actions.iter().enumerate().map(|(idx, action)| {
            let prefix = if self.focus == LaunchFocus::DeepControls && idx == self.deep_selected {
                "▶"
            } else {
                " "
            };
            format!("{prefix} {}", action.label())
        }));
        lines
    }
}

pub fn default_prompt(kind: LaunchKind) -> String {
    match kind {
        LaunchKind::Workflow => "Plan and implement the task I am looking at now.".to_string(),
        LaunchKind::Research => {
            "Research the task I am looking at now and report the ground truth.".to_string()
        }
        LaunchKind::Review => {
            "Review the selected surface and call out concrete risks.".to_string()
        }
        LaunchKind::Marbles => {
            "Run a convergence loop on the selected surface until the lies are exposed.".to_string()
        }
    }
}

pub fn agents() -> [&'static str; 3] {
    ["claude", "codex", "gemini"]
}
