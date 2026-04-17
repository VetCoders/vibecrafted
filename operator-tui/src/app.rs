use crate::config::{path_display, AppConfig};
use crate::launch::{build_launch_command, LaunchCommand, LaunchKind, LaunchRequest};
use crate::state::{render_runs, ControlPlaneState, RenderedRun, RunKind};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchFocus {
    Browse,
    EditPrompt,
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
    pub focus: LaunchFocus,
    pub status_line: String,
    pub launch_history: Vec<String>,
}

impl App {
    pub fn new(config: AppConfig) -> anyhow::Result<Self> {
        let state = ControlPlaneState::load(&config.state_root)
            .unwrap_or_else(|_| ControlPlaneState::empty(&config.state_root));
        let runs = render_runs(&state);
        let mut app = Self {
            config,
            state,
            runs,
            selected: 0,
            launch_kind: LaunchKind::Workflow,
            launch_agent: 0,
            launch_prompt: default_prompt(LaunchKind::Workflow),
            focus: LaunchFocus::Browse,
            status_line: String::new(),
            launch_history: Vec::new(),
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

    pub fn selected_agent(&self) -> &'static str {
        agents()[self.launch_agent]
    }

    pub fn launch_request(&self) -> LaunchRequest {
        LaunchRequest {
            kind: self.launch_kind,
            agent: self.selected_agent().to_string(),
            prompt: self.launch_prompt.clone(),
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
    }

    pub fn status_summary(&self) -> String {
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
                "No runs found in the control-plane state directory.".to_string(),
                format!("State root: {}", path_display(&self.config.state_root)),
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
        let mut lines = vec![
            format!("kind: {}", self.launch_kind.label()),
            format!("agent: {}", self.selected_agent()),
            format!("prompt: {}", self.launch_prompt),
            "keys: 1 workflow | 2 research | 3 review | 4 marbles | a agent | e edit prompt | Enter launch".to_string(),
        ];
        if let Some(last) = self.launch_history.last() {
            lines.push(format!("last launch: {last}"));
        }
        lines
    }

    pub fn active_run_count(&self) -> usize {
        self.runs
            .iter()
            .filter(|run| matches!(run.kind, RunKind::Active | RunKind::Stalled))
            .count()
    }
}

pub fn default_prompt(kind: LaunchKind) -> String {
    match kind {
        LaunchKind::Workflow => "Plan and implement the selected task.".to_string(),
        LaunchKind::Research => "Research the selected task and report findings.".to_string(),
        LaunchKind::Review => "Review the selected surface and report risks.".to_string(),
        LaunchKind::Marbles => "Run a convergence loop on the selected task.".to_string(),
    }
}

pub fn agents() -> [&'static str; 3] {
    ["claude", "codex", "gemini"]
}
