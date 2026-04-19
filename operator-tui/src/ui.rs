use crate::app::{App, AppTab, LaunchFocus};
use crate::state::RunKind;
use ratatui::prelude::*;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Clear, List, ListItem, Paragraph, Tabs, Wrap};

pub fn draw(frame: &mut Frame, app: &App) {
    let root = frame.area();
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(2),
            Constraint::Length(3),
            Constraint::Min(12),
            Constraint::Length(3),
        ])
        .split(root);

    draw_header(frame, layout[0], app);
    draw_tabs(frame, layout[1], app);
    draw_body(frame, layout[2], app);
    draw_footer(frame, layout[3], app);

    if app.focus == LaunchFocus::Help {
        draw_help_overlay(frame, app);
    }
}

fn draw_header(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(1), Constraint::Length(1)])
        .split(area);

    let title = Line::from(vec![
        Span::styled(
            "Vibecrafted Operator Console",
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(app.status_summary(), Style::default().fg(Color::Gray)),
    ]);
    frame.render_widget(Paragraph::new(title), rows[0]);

    let context = format!(
        "mission root: {}  |  active runs: {}  |  focus: {}",
        app.config.launch_root.to_string_lossy(),
        app.active_run_count(),
        app.active_tab().label()
    );
    frame.render_widget(
        Paragraph::new(context).style(Style::default().fg(Color::DarkGray)),
        rows[1],
    );
}

fn draw_tabs(frame: &mut Frame, area: Rect, app: &App) {
    let tabs = Tabs::new(
        app.tab_labels()
            .into_iter()
            .map(Line::from)
            .collect::<Vec<_>>(),
    )
    .block(Block::default().borders(Borders::ALL).title("Surface"))
    .select(app.active_tab)
    .divider("│")
    .style(Style::default().fg(Color::Gray))
    .highlight_style(
        Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD),
    );
    frame.render_widget(tabs, area);
}

fn draw_body(frame: &mut Frame, area: Rect, app: &App) {
    match app.active_tab() {
        AppTab::Monitor => draw_monitor(frame, area, app),
        AppTab::Dispatch => draw_dispatch(frame, area, app),
        AppTab::Controls => draw_controls(frame, area, app),
    }
}

fn draw_monitor(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(12)])
        .split(area);

    draw_stat_strip(
        frame,
        rows[0],
        [
            (
                "Monitor pulse",
                vec![
                    format!("{} runs visible", app.runs.len()),
                    format!("{} active or stalled", app.active_run_count()),
                ],
                Color::Green,
            ),
            (
                "Selection",
                app.selected_run()
                    .map(|run| {
                        vec![
                            run.snapshot.run_id.clone(),
                            format!(
                                "{} / {}",
                                run.kind.label(),
                                run.snapshot.agent.as_deref().unwrap_or("unknown")
                            ),
                        ]
                    })
                    .unwrap_or_else(|| {
                        vec![
                            "No run selected".to_string(),
                            "Dispatch a worker to populate the board".to_string(),
                        ]
                    }),
                Color::Yellow,
            ),
            (
                "Filter",
                vec![
                    if app.filter_active_only {
                        "Live-only view".to_string()
                    } else {
                        "Full board".to_string()
                    },
                    "f toggles queue density".to_string(),
                ],
                Color::Cyan,
            ),
        ],
    );

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(36), Constraint::Percentage(64)])
        .split(rows[1]);

    draw_runs(frame, body[0], app, true);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(62), Constraint::Percentage(38)])
        .split(body[1]);
    draw_detail(frame, right[0], app, "Run dossier");
    draw_events(frame, right[1], app, "Recent timeline");
}

fn draw_dispatch(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(12)])
        .split(area);

    draw_stat_strip(
        frame,
        rows[0],
        [
            (
                "Mission",
                vec![
                    app.launch_kind.human_title().to_string(),
                    app.launch_kind.human_description().to_string(),
                ],
                Color::Yellow,
            ),
            (
                "Operator",
                vec![
                    format!("agent {}", app.selected_agent()),
                    format!("runtime {}", app.launch_runtime.label()),
                ],
                Color::Blue,
            ),
            (
                "Prompt",
                vec![
                    if app.focus == LaunchFocus::EditPrompt {
                        "Editing live prompt".to_string()
                    } else {
                        "Ready to launch".to_string()
                    },
                    format!("{} chars staged", app.launch_prompt.chars().count()),
                ],
                Color::Magenta,
            ),
        ],
    );

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(rows[1]);

    draw_launch(frame, body[0], app);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(44), Constraint::Percentage(56)])
        .split(body[1]);

    let guide_lines = vec![
        Line::from("Dispatch posture"),
        Line::from(""),
        Line::from("Shape the next worker before you launch it."),
        Line::from("Use mission kind for intent, agent for style, runtime for surface."),
        Line::from("Prompt edit is the last mile: keep it sharp and bounded."),
    ];
    let guide = Paragraph::new(guide_lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Dispatch playbook"),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(guide, right[0]);

    draw_launch_history(frame, right[1], app);
}

fn draw_controls(frame: &mut Frame, area: Rect, app: &App) {
    let actions = app.deep_actions();
    let selected_action = app
        .selected_deep_action()
        .map(|action| action.label())
        .unwrap_or_else(|| "No action primed".to_string());
    let artifact_count = actions
        .iter()
        .filter(|action| {
            matches!(
                action,
                crate::app::DeepAction::OpenReport(_)
                    | crate::app::DeepAction::OpenTranscript(_)
                    | crate::app::DeepAction::OpenRoot(_)
            )
        })
        .count();

    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(12)])
        .split(area);

    draw_stat_strip(
        frame,
        rows[0],
        [
            (
                "Run access",
                app.selected_run()
                    .map(|run| vec![run.snapshot.run_id.clone(), run.snapshot.display_state()])
                    .unwrap_or_else(|| {
                        vec![
                            "No run selected".to_string(),
                            "Monitor chooses the source run".to_string(),
                        ]
                    }),
                Color::Yellow,
            ),
            (
                "Action deck",
                vec![
                    format!("{} actions available", actions.len()),
                    selected_action,
                ],
                Color::Cyan,
            ),
            (
                "Artifacts",
                vec![
                    format!("{artifact_count} file surfaces"),
                    "reports / transcripts / roots".to_string(),
                ],
                Color::Green,
            ),
        ],
    );

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(46), Constraint::Percentage(54)])
        .split(rows[1]);

    draw_deep_controls(frame, body[0], app);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(body[1]);

    draw_detail(frame, right[0], app, "Artifact access");
    draw_events(frame, right[1], app, "Selected timeline");
}

fn draw_footer(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .split(area);

    let nav_hint = match (app.active_tab(), app.focus) {
        (AppTab::Monitor, _) => {
            "Monitor: ↑/↓ runs  Tab/Shift+Tab switch tabs  f filter  d controls  ? help"
        }
        (AppTab::Dispatch, LaunchFocus::EditPrompt) => {
            "Dispatch edit: type prompt  Backspace delete  Enter/Esc finish  Tab switch tabs"
        }
        (AppTab::Dispatch, _) => {
            "Dispatch: ↑/↓ field  ←/→ change  e edit prompt  Enter launch  1-4 presets"
        }
        (AppTab::Controls, _) => {
            "Controls: ↑/↓ action  ←/→ run selection  Enter open  d jump here from Monitor"
        }
    };
    frame.render_widget(
        Paragraph::new(nav_hint).style(Style::default().fg(Color::Cyan)),
        rows[0],
    );

    let shortcuts = "Global: q quit  r refresh  a cycle agent  v cycle runtime  ? help";
    frame.render_widget(
        Paragraph::new(shortcuts).style(Style::default().fg(Color::DarkGray)),
        rows[1],
    );

    let status = if app.status_line.is_empty() {
        format!("state root: {}", app.config.state_root.to_string_lossy())
    } else {
        app.status_line.clone()
    };
    frame.render_widget(
        Paragraph::new(status).style(Style::default().fg(Color::Gray)),
        rows[2],
    );
}

fn draw_runs(frame: &mut Frame, area: Rect, app: &App, emphasize_live: bool) {
    let items: Vec<ListItem> = if app.runs.is_empty() {
        vec![ListItem::new("No run snapshots found.")]
    } else {
        app.runs
            .iter()
            .enumerate()
            .map(|(idx, run)| {
                let snapshot = &run.snapshot;
                let status = status_style(run.kind);
                let selected = idx == app.selected;
                let label = format!(
                    "{} {} / {} / {}",
                    snapshot.run_id,
                    run.kind.label(),
                    snapshot.agent.as_deref().unwrap_or("unknown"),
                    snapshot.mode.as_deref().unwrap_or("unknown")
                );
                let detail = format!(
                    "{}  {}",
                    run.age_label,
                    snapshot.last_error.as_deref().unwrap_or("")
                );
                let mut spans = vec![
                    Span::styled(label, status),
                    Span::raw("\n"),
                    Span::styled(detail, Style::default().fg(Color::DarkGray)),
                ];
                if selected {
                    spans.insert(0, Span::styled("▶ ", Style::default().fg(Color::Yellow)));
                } else {
                    spans.insert(0, Span::raw("  "));
                }
                ListItem::new(Line::from(spans))
            })
            .collect()
    };

    let title = if app.filter_active_only {
        "Live queue (live-only)"
    } else if emphasize_live {
        "Live queue (all)"
    } else {
        "Runs"
    };
    let list = List::new(items).block(Block::default().borders(Borders::ALL).title(title));
    frame.render_widget(list, area);
}

fn draw_detail(frame: &mut Frame, area: Rect, app: &App, title: &str) {
    let lines = app
        .detail_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let detail = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title(title))
        .wrap(Wrap { trim: false });
    frame.render_widget(detail, area);
}

fn draw_events(frame: &mut Frame, area: Rect, app: &App, title: &str) {
    let lines = app
        .event_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let events = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title(title))
        .wrap(Wrap { trim: false });
    frame.render_widget(events, area);
}

fn draw_launch(frame: &mut Frame, area: Rect, app: &App) {
    let lines = app
        .prompt_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();

    let title = if app.focus == LaunchFocus::EditPrompt {
        "Dispatch deck (editing prompt)"
    } else {
        "Dispatch deck"
    };

    let launch = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title(title))
        .wrap(Wrap { trim: false });
    frame.render_widget(launch, area);
}

fn draw_launch_history(frame: &mut Frame, area: Rect, app: &App) {
    let mut lines = if app.launch_history.is_empty() {
        vec![
            Line::from("No launches from this session yet."),
            Line::from(""),
            Line::from("Use Dispatch to stage a worker, then press Enter."),
        ]
    } else {
        app.launch_history
            .iter()
            .rev()
            .map(|entry| Line::from(entry.clone()))
            .collect::<Vec<_>>()
    };
    lines.push(Line::from(""));
    lines.push(Line::from(format!(
        "selected run: {}",
        app.selected_run()
            .map(|run| run.snapshot.run_id.as_str())
            .unwrap_or("none")
    )));
    let panel = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title("Launch trail"))
        .wrap(Wrap { trim: false });
    frame.render_widget(panel, area);
}

fn draw_deep_controls(frame: &mut Frame, area: Rect, app: &App) {
    let lines = app
        .deep_control_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let panel = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Control actions"),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(panel, area);
}

fn draw_stat_strip(frame: &mut Frame, area: Rect, cards: [(&str, Vec<String>, Color); 3]) {
    let columns = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Ratio(1, 3); 3])
        .split(area);

    for ((title, lines, accent), column) in cards.into_iter().zip(columns.iter().copied()) {
        let content = lines.into_iter().map(Line::from).collect::<Vec<_>>();
        let panel = Paragraph::new(content)
            .block(
                Block::default()
                    .borders(Borders::ALL)
                    .title(title)
                    .border_style(Style::default().fg(accent)),
            )
            .style(Style::default().fg(Color::White))
            .wrap(Wrap { trim: false });
        frame.render_widget(panel, column);
    }
}

fn status_style(kind: RunKind) -> Style {
    match kind {
        RunKind::Active => Style::default()
            .fg(Color::Green)
            .add_modifier(Modifier::BOLD),
        RunKind::Recent | RunKind::Completed => Style::default().fg(Color::Blue),
        RunKind::Failed => Style::default().fg(Color::Red).add_modifier(Modifier::BOLD),
        RunKind::Stalled => Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD),
        RunKind::Paused => Style::default().fg(Color::Magenta),
        RunKind::Unknown => Style::default().fg(Color::Gray),
    }
}

fn draw_help_overlay(frame: &mut Frame, app: &App) {
    let area = centered_rect(72, 70, frame.area());
    frame.render_widget(Clear, area);
    let lines = app
        .help_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let help = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Help")
                .border_style(Style::default().fg(Color::Yellow)),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(help, area);
}

fn centered_rect(percent_x: u16, percent_y: u16, area: Rect) -> Rect {
    let popup_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - percent_y) / 2),
            Constraint::Percentage(percent_y),
            Constraint::Percentage((100 - percent_y) / 2),
        ])
        .split(area);

    Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - percent_x) / 2),
            Constraint::Percentage(percent_x),
            Constraint::Percentage((100 - percent_x) / 2),
        ])
        .split(popup_layout[1])[1]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::app::{DispatchFocus, LaunchFocus};
    use crate::config::AppConfig;
    use crate::launch::{LaunchKind, LaunchRuntime};
    use crate::state::{ControlPlaneState, RenderedRun, RunKind, RunSnapshot};
    use ratatui::Terminal;
    use ratatui::backend::TestBackend;
    use std::time::Duration;

    fn sample_run(run_id: &str, agent: &str, session: &str) -> RenderedRun {
        RenderedRun {
            snapshot: RunSnapshot {
                run_id: run_id.to_string(),
                session_id: Some(format!("sess-{run_id}")),
                agent: Some(agent.to_string()),
                skill: Some("workflow".to_string()),
                mode: Some("implement".to_string()),
                state: Some("running".to_string()),
                status: None,
                started_at: Some("2026-04-19T10:00:00Z".to_string()),
                updated_at: Some("2026-04-19T10:01:00Z".to_string()),
                last_heartbeat: Some("2026-04-19T10:01:30Z".to_string()),
                root: Some(format!("/tmp/{run_id}")),
                operator_session: Some(session.to_string()),
                latest_report: Some(format!("/tmp/{run_id}/report.md")),
                latest_transcript: Some(format!("/tmp/{run_id}/transcript.log")),
                last_error: None,
                extra: Default::default(),
            },
            kind: RunKind::Active,
            age_label: "just now".to_string(),
            recent_events: Vec::new(),
        }
    }

    fn sample_app() -> App {
        App {
            config: AppConfig {
                state_root: "/tmp/state".into(),
                command_deck: "/usr/bin/vibecrafted".into(),
                launch_root: "/tmp/repo".into(),
                launch_runtime: LaunchRuntime::Terminal,
                tick_rate: Duration::from_millis(250),
            },
            state: ControlPlaneState::empty("/tmp/state"),
            runs: vec![
                sample_run("run-1", "codex", "operator-1"),
                sample_run("run-2", "claude", "operator-2"),
            ],
            selected: 0,
            active_tab: AppTab::Monitor.index(),
            launch_kind: LaunchKind::Workflow,
            launch_agent: 0,
            launch_prompt: "Ship the operator surface.".to_string(),
            launch_runtime: LaunchRuntime::Terminal,
            dispatch_selected: DispatchFocus::Kind as usize,
            focus: LaunchFocus::Browse,
            status_line: String::new(),
            launch_history: vec!["vc workflow --agent codex".to_string()],
            deep_selected: 0,
            filter_active_only: false,
        }
    }

    fn render_to_string(app: &App) -> String {
        let backend = TestBackend::new(120, 40);
        let mut terminal = Terminal::new(backend).unwrap();
        terminal.draw(|frame| draw(frame, app)).unwrap();
        terminal
            .backend()
            .buffer()
            .content()
            .iter()
            .map(|cell| cell.symbol())
            .collect::<String>()
    }

    #[test]
    fn monitor_tab_renders_monitor_surface() {
        let app = sample_app();
        let rendered = render_to_string(&app);

        assert!(rendered.contains("Monitor pulse"));
        assert!(rendered.contains("Live queue (all)"));
        assert!(rendered.contains("Run dossier"));
        assert!(rendered.contains("Recent timeline"));
        assert!(!rendered.contains("Dispatch playbook"));
    }

    #[test]
    fn dispatch_tab_renders_dispatch_surface() {
        let mut app = sample_app();
        app.set_active_tab(AppTab::Dispatch);

        let rendered = render_to_string(&app);

        assert!(rendered.contains("Dispatch deck"));
        assert!(rendered.contains("Dispatch playbook"));
        assert!(rendered.contains("Launch trail"));
        assert!(!rendered.contains("Control actions"));
    }

    #[test]
    fn controls_tab_renders_controls_surface() {
        let mut app = sample_app();
        app.set_active_tab(AppTab::Controls);

        let rendered = render_to_string(&app);

        assert!(rendered.contains("Action deck"));
        assert!(rendered.contains("Control actions"));
        assert!(rendered.contains("Artifact access"));
        assert!(rendered.contains("Selected timeline"));
        assert!(!rendered.contains("Dispatch playbook"));
    }
}
