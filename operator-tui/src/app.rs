use crate::config::{AppConfig, path_display};
use crate::launch::{
    LaunchCommand, LaunchKind, LaunchRequest, LaunchRuntime, build_launch_command,
};
use crate::state::{ControlPlaneState, RenderedRun, RunKind, render_runs};
use std::collections::BTreeMap;
use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppTab {
    Monitor,
    Dispatch,
    Controls,
}

impl AppTab {
    pub const TITLES: [&'static str; 3] = ["Monitor", "Dispatch", "Controls"];

    pub fn label(self) -> &'static str {
        match self {
            Self::Monitor => "Monitor",
            Self::Dispatch => "Dispatch",
            Self::Controls => "Controls",
        }
    }

    pub fn from_index(index: usize) -> Self {
        match index % Self::TITLES.len() {
            0 => Self::Monitor,
            1 => Self::Dispatch,
            _ => Self::Controls,
        }
    }

    pub fn index(self) -> usize {
        match self {
            Self::Monitor => 0,
            Self::Dispatch => 1,
            Self::Controls => 2,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DispatchFocus {
    Kind,
    Agent,
    Runtime,
    Prompt,
}

impl DispatchFocus {
    pub const COUNT: usize = 4;

    pub fn from_index(index: usize) -> Self {
        match index % Self::COUNT {
            0 => Self::Kind,
            1 => Self::Agent,
            2 => Self::Runtime,
            _ => Self::Prompt,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchFocus {
    Browse,
    EditPrompt,
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
    pub active_tab: usize,
    pub launch_kind: LaunchKind,
    pub launch_agent: usize,
    pub launch_prompt: String,
    pub launch_runtime: LaunchRuntime,
    pub dispatch_selected: usize,
    pub focus: LaunchFocus,
    pub status_line: String,
    pub launch_history: Vec<String>,
    pub deep_selected: usize,
    pub filter_active_only: bool,
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
            active_tab: AppTab::Monitor.index(),
            launch_kind: LaunchKind::Workflow,
            launch_agent: 0,
            launch_prompt: default_prompt(LaunchKind::Workflow),
            launch_runtime,
            dispatch_selected: DispatchFocus::Kind as usize,
            focus: LaunchFocus::Browse,
            status_line: String::new(),
            launch_history: Vec::new(),
            deep_selected: 0,
            filter_active_only: false,
        };
        app.sync_selection();
        Ok(app)
    }

    pub fn refresh(&mut self) {
        let state = ControlPlaneState::load(&self.config.state_root)
            .unwrap_or_else(|_| ControlPlaneState::empty(&self.config.state_root));
        self.state = state;
        let mut runs = render_runs(&self.state);
        if self.filter_active_only {
            runs.retain(|r| matches!(r.kind, RunKind::Active | RunKind::Stalled | RunKind::Paused));
        }
        self.runs = runs;
        self.sync_selection();
    }

    pub fn toggle_filter(&mut self) {
        self.filter_active_only = !self.filter_active_only;
        self.refresh();
    }

    pub fn selected_run(&self) -> Option<&RenderedRun> {
        self.runs.get(self.selected)
    }

    pub fn active_tab(&self) -> AppTab {
        AppTab::from_index(self.active_tab)
    }

    pub fn next_tab(&mut self) {
        self.active_tab = (self.active_tab + 1) % AppTab::TITLES.len();
        self.focus = LaunchFocus::Browse;
    }

    pub fn previous_tab(&mut self) {
        self.active_tab = if self.active_tab == 0 {
            AppTab::TITLES.len() - 1
        } else {
            self.active_tab - 1
        };
        self.focus = LaunchFocus::Browse;
    }

    pub fn set_active_tab(&mut self, tab: AppTab) {
        self.active_tab = tab.index();
        self.focus = LaunchFocus::Browse;
    }

    pub fn set_launch_kind(&mut self, kind: LaunchKind) {
        self.launch_kind = kind;
        self.launch_prompt = default_prompt(kind);
        self.active_tab = AppTab::Dispatch.index();
        self.dispatch_selected = DispatchFocus::Kind as usize;
        self.focus = LaunchFocus::Browse;
    }

    pub fn cycle_agent(&mut self) {
        self.shift_agent(1);
    }

    pub fn cycle_runtime(&mut self) {
        self.shift_runtime(1);
    }

    pub fn selected_agent(&self) -> &'static str {
        agents()[self.launch_agent]
    }

    pub fn shift_agent(&mut self, delta: isize) {
        let len = agents().len() as isize;
        let mut index = self.launch_agent as isize + delta;
        while index < 0 {
            index += len;
        }
        self.launch_agent = (index % len) as usize;
    }

    pub fn shift_runtime(&mut self, delta: isize) {
        let runtimes = [
            LaunchRuntime::Headless,
            LaunchRuntime::Terminal,
            LaunchRuntime::Visible,
        ];
        let current = runtimes
            .iter()
            .position(|runtime| *runtime == self.launch_runtime)
            .unwrap_or(1) as isize;
        let len = runtimes.len() as isize;
        let mut index = current + delta;
        while index < 0 {
            index += len;
        }
        self.launch_runtime = runtimes[(index % len) as usize];
    }

    pub fn shift_launch_kind(&mut self, delta: isize) {
        let kinds = [
            LaunchKind::Workflow,
            LaunchKind::Research,
            LaunchKind::Review,
            LaunchKind::Marbles,
        ];
        let current = kinds
            .iter()
            .position(|kind| *kind == self.launch_kind)
            .unwrap_or(0) as isize;
        let len = kinds.len() as isize;
        let mut index = current + delta;
        while index < 0 {
            index += len;
        }
        self.launch_kind = kinds[(index % len) as usize];
        self.launch_prompt = default_prompt(self.launch_kind);
    }

    pub fn dispatch_focus(&self) -> DispatchFocus {
        DispatchFocus::from_index(self.dispatch_selected)
    }

    pub fn move_dispatch_selection(&mut self, delta: isize) {
        let len = DispatchFocus::COUNT as isize;
        let mut index = self.dispatch_selected as isize + delta;
        while index < 0 {
            index += len;
        }
        self.dispatch_selected = (index % len) as usize;
    }

    pub fn adjust_dispatch_selection(&mut self, delta: isize) {
        match self.dispatch_focus() {
            DispatchFocus::Kind => self.shift_launch_kind(delta),
            DispatchFocus::Agent => self.shift_agent(delta),
            DispatchFocus::Runtime => self.shift_runtime(delta),
            DispatchFocus::Prompt => {
                self.focus = LaunchFocus::EditPrompt;
            }
        }
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
            dispatch_line(
                self.dispatch_focus() == DispatchFocus::Kind,
                format!(
                    "mission: {}  {}",
                    self.launch_kind.human_title(),
                    self.launch_kind.human_description()
                ),
            ),
            dispatch_line(
                self.dispatch_focus() == DispatchFocus::Agent,
                format!("agent: {}", self.selected_agent()),
            ),
            dispatch_line(
                self.dispatch_focus() == DispatchFocus::Runtime,
                format!("runtime: {}", self.launch_runtime.label()),
            ),
            dispatch_line(
                self.dispatch_focus() == DispatchFocus::Prompt,
                format!("prompt: {}", self.launch_prompt),
            ),
            String::new(),
            "Arrows: ↑/↓ choose field  ←/→ change field  Enter launch".to_string(),
            "Shortcuts: 1-4 mission  a agent  v runtime  e edit prompt".to_string(),
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
            "Tabs".to_string(),
            "Tab / Shift+Tab switch between Monitor, Dispatch, and Controls.".to_string(),
            "Monitor keeps the live board. Dispatch shapes the next run. Controls opens attach/report actions.".to_string(),
            String::new(),
            "Keys".to_string(),
            "↑/↓ or j/k  navigate inside the active tab".to_string(),
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

    pub fn tab_labels(&self) -> [String; 3] {
        let monitor = if self.filter_active_only {
            format!("Monitor {}/{}", self.active_run_count(), self.runs.len())
        } else {
            format!("Monitor {}", self.runs.len())
        };
        let dispatch = format!(
            "Dispatch {}/{}",
            self.launch_kind.label(),
            self.selected_agent()
        );
        let controls = if self.selected_run().is_some() {
            format!("Controls {}", self.deep_actions().len())
        } else {
            "Controls -".to_string()
        };
        [monitor, dispatch, controls]
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
            let prefix = if self.active_tab() == AppTab::Controls && idx == self.deep_selected {
                "▶"
            } else {
                " "
            };
            format!("{prefix} {}", action.label())
        }));
        lines
    }
}

fn dispatch_line(selected: bool, content: String) -> String {
    if selected {
        format!("▶ {content}")
    } else {
        format!("  {content}")
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
