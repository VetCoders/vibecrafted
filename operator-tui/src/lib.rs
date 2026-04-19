pub mod app;
pub mod config;
pub mod launch;
pub mod state;
pub mod ui;

use anyhow::Context;
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyModifiers};
use crossterm::execute;
use crossterm::terminal::{
    EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode,
};
use ratatui::Terminal;
use ratatui::backend::CrosstermBackend;
use std::env;
use std::io;
use std::path::Path;
use std::time::{Duration, Instant};

pub use app::{App, AppTab, DeepAction, DispatchFocus, LaunchFocus};
pub use config::{AppConfig, CliOptions, build_config, parse_args};
pub use launch::{LaunchCommand, LaunchKind};

pub fn run_cli() -> anyhow::Result<()> {
    let options = parse_args()?;
    let config = build_config(options);
    run_app(config)
}

fn run_app(config: AppConfig) -> anyhow::Result<()> {
    enable_raw_mode().context("failed to enable raw mode")?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let result = (|| -> anyhow::Result<()> {
        let mut app = App::new(config)?;
        let mut last_tick = Instant::now();
        loop {
            terminal.draw(|frame| ui::draw(frame, &app))?;
            let timeout = app
                .config
                .tick_rate
                .checked_sub(last_tick.elapsed())
                .unwrap_or(Duration::ZERO);

            if event::poll(timeout)?
                && let Event::Key(key) = event::read()?
                && handle_key(&mut app, key)?
            {
                break;
            }

            if last_tick.elapsed() >= app.config.tick_rate {
                app.refresh();
                last_tick = Instant::now();
            }
        }
        Ok(())
    })();

    shutdown_terminal(&mut terminal)?;
    result
}

fn shutdown_terminal(terminal: &mut Terminal<CrosstermBackend<io::Stdout>>) -> anyhow::Result<()> {
    disable_raw_mode().context("failed to disable raw mode")?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    Ok(())
}

fn handle_key(app: &mut App, key: KeyEvent) -> anyhow::Result<bool> {
    if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
        return Ok(true);
    }

    match app.focus {
        LaunchFocus::EditPrompt => match key.code {
            KeyCode::Tab => app.next_tab(),
            KeyCode::BackTab => app.previous_tab(),
            KeyCode::Char('?') => {
                app.focus = LaunchFocus::Help;
            }
            KeyCode::Esc | KeyCode::Enter => {
                app.focus = LaunchFocus::Browse;
            }
            KeyCode::Backspace => {
                app.launch_prompt.pop();
            }
            KeyCode::Char(c) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                app.launch_prompt.push(c);
            }
            _ => {}
        },
        LaunchFocus::Browse => match key.code {
            KeyCode::Char('q') | KeyCode::Esc => return Ok(true),
            KeyCode::Char('?') => app.focus = LaunchFocus::Help,
            KeyCode::Tab => app.next_tab(),
            KeyCode::BackTab => app.previous_tab(),
            KeyCode::Up | KeyCode::Char('k') => match app.active_tab() {
                AppTab::Monitor => app.move_selection(-1),
                AppTab::Dispatch => app.move_dispatch_selection(-1),
                AppTab::Controls => app.move_deep_selection(-1),
            },
            KeyCode::Down | KeyCode::Char('j') => match app.active_tab() {
                AppTab::Monitor => app.move_selection(1),
                AppTab::Dispatch => app.move_dispatch_selection(1),
                AppTab::Controls => app.move_deep_selection(1),
            },
            KeyCode::Left | KeyCode::Char('h') => match app.active_tab() {
                AppTab::Monitor => {}
                AppTab::Dispatch => app.adjust_dispatch_selection(-1),
                AppTab::Controls => app.move_selection(-1),
            },
            KeyCode::Right | KeyCode::Char('l') => match app.active_tab() {
                AppTab::Monitor => {}
                AppTab::Dispatch => app.adjust_dispatch_selection(1),
                AppTab::Controls => app.move_selection(1),
            },
            KeyCode::Char('1') => app.set_launch_kind(LaunchKind::Workflow),
            KeyCode::Char('2') => app.set_launch_kind(LaunchKind::Research),
            KeyCode::Char('3') => app.set_launch_kind(LaunchKind::Review),
            KeyCode::Char('4') => app.set_launch_kind(LaunchKind::Marbles),
            KeyCode::Char('a') => {
                app.set_active_tab(AppTab::Dispatch);
                app.dispatch_selected = DispatchFocus::Agent as usize;
                app.cycle_agent();
            }
            KeyCode::Char('v') => {
                app.set_active_tab(AppTab::Dispatch);
                app.dispatch_selected = DispatchFocus::Runtime as usize;
                app.cycle_runtime();
            }
            KeyCode::Char('f') => app.toggle_filter(),
            KeyCode::Char('r') => app.refresh(),
            KeyCode::Char('e') => {
                app.set_active_tab(AppTab::Dispatch);
                app.dispatch_selected = DispatchFocus::Prompt as usize;
                app.focus = LaunchFocus::EditPrompt;
            }
            KeyCode::Enter => match app.active_tab() {
                AppTab::Monitor => {
                    if app.selected_run().is_some() {
                        app.set_active_tab(AppTab::Controls);
                    }
                }
                AppTab::Dispatch => {
                    if app.dispatch_focus() == DispatchFocus::Prompt {
                        app.focus = LaunchFocus::EditPrompt;
                    } else {
                        launch_selected(app)?;
                    }
                }
                AppTab::Controls => {
                    run_selected_deep_control(app)?;
                }
            },
            KeyCode::Char('d') if app.selected_run().is_some() => {
                app.set_active_tab(AppTab::Controls);
                if app.deep_actions().is_empty() {
                    app.append_status(
                        "No attach/resume/report actions are available for this run.",
                    );
                } else {
                    app.append_status("Controls ready: ↑/↓ select action, Enter runs it.");
                }
            }
            _ => {}
        },
        LaunchFocus::Help => match key.code {
            KeyCode::Char('?') | KeyCode::Esc | KeyCode::Enter => {
                app.focus = LaunchFocus::Browse;
            }
            _ => {}
        },
    }
    Ok(false)
}

fn launch_selected(app: &mut App) -> anyhow::Result<()> {
    let command = app.launch_command();
    let summary = command.command_line();
    suspend_and_run(&command)?;
    app.push_launch_history(summary.clone());
    app.append_status(format!("launched: {summary}"));
    app.refresh();
    Ok(())
}

fn run_selected_deep_control(app: &mut App) -> anyhow::Result<()> {
    let Some(action) = app.selected_deep_action() else {
        app.append_status("No deep action is available for the selected run.");
        app.focus = LaunchFocus::Browse;
        return Ok(());
    };
    let command = deep_control_command(app, &action);
    let summary = command.command_line();
    suspend_and_run(&command)?;
    app.push_launch_history(summary.clone());
    app.append_status(format!("ran: {summary}"));
    app.focus = LaunchFocus::Browse;
    app.refresh();
    Ok(())
}

fn deep_control_command(app: &App, action: &DeepAction) -> LaunchCommand {
    match action {
        DeepAction::AttachSession(session) => LaunchCommand {
            program: app.config.command_deck.clone(),
            args: vec!["dashboard".into(), "attach".into(), session.clone().into()],
        },
        DeepAction::ResumeSession { agent, session } => LaunchCommand {
            program: app.config.command_deck.clone(),
            args: vec![
                "resume".into(),
                agent.clone().into(),
                "--session".into(),
                session.clone().into(),
            ],
        },
        DeepAction::OpenReport(path)
        | DeepAction::OpenTranscript(path)
        | DeepAction::OpenRoot(path) => pager_command(path),
    }
}

fn pager_command(path: &Path) -> LaunchCommand {
    let quoted = shell_quote(&path.to_string_lossy());
    let viewer = env::var("PAGER")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| "less".to_string());
    let command = format!(
        "if [ -d {quoted} ]; then cd {quoted} && exec ${{SHELL:-/bin/sh}}; elif command -v {viewer} >/dev/null 2>&1; then exec {viewer} {quoted}; else cat {quoted}; fi"
    );
    LaunchCommand {
        program: "sh".into(),
        args: vec!["-lc".into(), command.into()],
    }
}

fn shell_quote(raw: &str) -> String {
    format!("'{}'", raw.replace('\'', "'\"'\"'"))
}

fn suspend_and_run(command: &LaunchCommand) -> anyhow::Result<()> {
    let mut stdout = io::stdout();
    disable_raw_mode().context("failed to disable raw mode before launch")?;
    execute!(stdout, LeaveAlternateScreen)?;

    let launch_result = match command.spawn() {
        Ok(mut child) => child.wait().context("launch process failed"),
        Err(error) => Err(error),
    };

    let leave_result =
        execute!(stdout, EnterAlternateScreen).context("failed to restore alternate screen");
    let raw_result = enable_raw_mode().context("failed to re-enable raw mode after launch");

    leave_result?;
    raw_result?;
    launch_result?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::launch::LaunchRuntime;
    use crate::state::{ControlPlaneState, RenderedRun, RunKind, RunSnapshot};

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
            launch_history: Vec::new(),
            deep_selected: 0,
            filter_active_only: false,
        }
    }

    fn key(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    #[test]
    fn handle_key_cycles_tabs_with_tab_and_shift_tab() {
        let mut app = sample_app();

        assert_eq!(app.active_tab(), AppTab::Monitor);
        handle_key(&mut app, key(KeyCode::Tab)).unwrap();
        assert_eq!(app.active_tab(), AppTab::Dispatch);

        handle_key(&mut app, key(KeyCode::BackTab)).unwrap();
        assert_eq!(app.active_tab(), AppTab::Monitor);
    }

    #[test]
    fn handle_key_routes_arrows_inside_the_active_tab() {
        let mut app = sample_app();

        handle_key(&mut app, key(KeyCode::Down)).unwrap();
        assert_eq!(app.selected, 1);

        app.set_active_tab(AppTab::Dispatch);
        handle_key(&mut app, key(KeyCode::Down)).unwrap();
        assert_eq!(app.dispatch_focus(), DispatchFocus::Agent);

        handle_key(&mut app, key(KeyCode::Right)).unwrap();
        assert_eq!(app.selected_agent(), "codex");

        app.set_active_tab(AppTab::Controls);
        handle_key(&mut app, key(KeyCode::Down)).unwrap();
        assert_eq!(app.deep_selected, 1);
    }

    #[test]
    fn handle_key_enters_prompt_edit_from_dispatch_prompt_row() {
        let mut app = sample_app();
        app.set_active_tab(AppTab::Dispatch);
        app.dispatch_selected = DispatchFocus::Prompt as usize;

        handle_key(&mut app, key(KeyCode::Enter)).unwrap();

        assert_eq!(app.focus, LaunchFocus::EditPrompt);
    }

    #[test]
    fn handle_key_shortcuts_jump_to_dispatch_controls_and_prime_selection() {
        let mut app = sample_app();

        handle_key(&mut app, key(KeyCode::Char('a'))).unwrap();
        assert_eq!(app.active_tab(), AppTab::Dispatch);
        assert_eq!(app.dispatch_focus(), DispatchFocus::Agent);
        assert_eq!(app.selected_agent(), "codex");

        handle_key(&mut app, key(KeyCode::Char('v'))).unwrap();
        assert_eq!(app.active_tab(), AppTab::Dispatch);
        assert_eq!(app.dispatch_focus(), DispatchFocus::Runtime);
        assert_eq!(app.launch_runtime, LaunchRuntime::Visible);

        app.set_active_tab(AppTab::Monitor);
        handle_key(&mut app, key(KeyCode::Char('d'))).unwrap();
        assert_eq!(app.active_tab(), AppTab::Controls);
        assert!(app.status_line.contains("Controls ready"));
    }

    #[test]
    fn handle_key_controls_can_move_across_run_list_and_prompt_edit_can_tab_out() {
        let mut app = sample_app();
        app.set_active_tab(AppTab::Controls);

        handle_key(&mut app, key(KeyCode::Right)).unwrap();
        assert_eq!(app.selected, 1);

        handle_key(&mut app, key(KeyCode::Left)).unwrap();
        assert_eq!(app.selected, 0);

        app.set_active_tab(AppTab::Dispatch);
        app.focus = LaunchFocus::EditPrompt;
        handle_key(&mut app, key(KeyCode::Tab)).unwrap();
        assert_eq!(app.active_tab(), AppTab::Controls);
        assert_eq!(app.focus, LaunchFocus::Browse);
    }

    #[test]
    fn set_active_tab_resets_focus_to_browse() {
        let mut app = sample_app();
        app.focus = LaunchFocus::EditPrompt;

        app.set_active_tab(AppTab::Controls);

        assert_eq!(app.active_tab(), AppTab::Controls);
        assert_eq!(app.focus, LaunchFocus::Browse);
    }
}
