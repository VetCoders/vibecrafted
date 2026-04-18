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

use vibecrafted_operator::app::{App, DeepAction, LaunchFocus};
use vibecrafted_operator::config::{build_config, parse_args};
use vibecrafted_operator::launch::{LaunchCommand, LaunchKind};
use vibecrafted_operator::ui::draw;

fn main() -> anyhow::Result<()> {
    let options = parse_args()?;
    let config = build_config(options);
    run_app(config)
}

fn run_app(config: vibecrafted_operator::config::AppConfig) -> anyhow::Result<()> {
    enable_raw_mode().context("failed to enable raw mode")?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let result = (|| -> anyhow::Result<()> {
        let mut app = App::new(config)?;
        let mut last_tick = Instant::now();
        loop {
            terminal.draw(|frame| draw(frame, &app))?;
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
            KeyCode::Up | KeyCode::Char('k') => app.move_selection(-1),
            KeyCode::Down | KeyCode::Char('j') => app.move_selection(1),
            KeyCode::Char('1') => app.set_launch_kind(LaunchKind::Workflow),
            KeyCode::Char('2') => app.set_launch_kind(LaunchKind::Research),
            KeyCode::Char('3') => app.set_launch_kind(LaunchKind::Review),
            KeyCode::Char('4') => app.set_launch_kind(LaunchKind::Marbles),
            KeyCode::Char('a') => app.cycle_agent(),
            KeyCode::Char('v') => app.cycle_runtime(),
            KeyCode::Char('r') => app.refresh(),
            KeyCode::Char('e') => app.focus = LaunchFocus::EditPrompt,
            KeyCode::Enter => {
                launch_selected(app)?;
            }
            KeyCode::Char('d') if app.selected_run().is_some() => {
                if app.deep_actions().is_empty() {
                    app.append_status(
                        "No attach/resume/report actions are available for this run.",
                    );
                } else {
                    app.focus = LaunchFocus::DeepControls;
                }
            }
            _ => {}
        },
        LaunchFocus::DeepControls => match key.code {
            KeyCode::Char('q') | KeyCode::Esc => app.focus = LaunchFocus::Browse,
            KeyCode::Up | KeyCode::Char('k') => app.move_deep_selection(-1),
            KeyCode::Down | KeyCode::Char('j') => app.move_deep_selection(1),
            KeyCode::Char('r') => app.refresh(),
            KeyCode::Enter => run_selected_deep_control(app)?,
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

fn suspend_and_run(command: &vibecrafted_operator::launch::LaunchCommand) -> anyhow::Result<()> {
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
