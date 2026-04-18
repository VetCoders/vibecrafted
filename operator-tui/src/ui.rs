use crate::app::{App, LaunchFocus};
use crate::state::RunKind;
use ratatui::prelude::*;
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph, Wrap};

pub fn draw(frame: &mut Frame, app: &App) {
    let root = frame.area();
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4),
            Constraint::Min(10),
            Constraint::Length(11),
        ])
        .split(root);

    draw_header(frame, vertical[0], app);

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(38), Constraint::Percentage(62)])
        .split(vertical[1]);

    draw_runs(frame, body[0], app);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(62), Constraint::Percentage(38)])
        .split(body[1]);

    draw_detail(frame, right[0], app);
    draw_events(frame, right[1], app);
    draw_footer(frame, vertical[2], app);
}

fn draw_header(frame: &mut Frame, area: Rect, app: &App) {
    let title = vec![
        Span::styled(
            "Vibecrafted Operator Console",
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(app.status_summary(), Style::default().fg(Color::Gray)),
    ];
    let footer = vec![
        Span::styled("q quit", Style::default().fg(Color::Red)),
        Span::raw("  "),
        Span::styled("r refresh", Style::default().fg(Color::Green)),
        Span::raw("  "),
        Span::styled("arrows move", Style::default().fg(Color::Cyan)),
        Span::raw("  "),
        Span::styled("1-4 launch kind", Style::default().fg(Color::Magenta)),
        Span::raw("  "),
        Span::styled("v runtime", Style::default().fg(Color::Yellow)),
        Span::raw("  "),
        Span::styled("d deep controls", Style::default().fg(Color::Blue)),
    ];

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1),
            Constraint::Length(1),
            Constraint::Length(1),
        ])
        .split(area);
    frame.render_widget(Paragraph::new(Line::from(title)), chunks[0]);
    frame.render_widget(Paragraph::new(Line::from(footer)), chunks[1]);
    let message = if app.status_line.is_empty() {
        format!("state root: {}", app.config.state_root.to_string_lossy())
    } else {
        app.status_line.clone()
    };
    frame.render_widget(
        Paragraph::new(Line::from(vec![Span::styled(
            message,
            Style::default().fg(Color::Gray),
        )])),
        chunks[2],
    );
}

fn draw_runs(frame: &mut Frame, area: Rect, app: &App) {
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

    let list = List::new(items).block(Block::default().borders(Borders::ALL).title("Runs"));
    frame.render_widget(list, area);
}

fn draw_detail(frame: &mut Frame, area: Rect, app: &App) {
    let lines = app
        .detail_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let detail = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title("Run detail"))
        .wrap(Wrap { trim: false });
    frame.render_widget(detail, area);
}

fn draw_events(frame: &mut Frame, area: Rect, app: &App) {
    let lines = app
        .event_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let events = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Recent events"),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(events, area);
}

fn draw_footer(frame: &mut Frame, area: Rect, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(58), Constraint::Percentage(42)])
        .split(area);
    draw_launch(frame, chunks[0], app);
    draw_deep_controls(frame, chunks[1], app);
}

fn draw_launch(frame: &mut Frame, area: Rect, app: &App) {
    let prompt_style = if app.focus == LaunchFocus::EditPrompt {
        Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(Color::White)
    };

    let lines = vec![
        Line::from(vec![
            Span::styled(
                "Launch",
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                format!("agent: {}", app.selected_agent()),
                Style::default().fg(Color::Cyan),
            ),
            Span::raw("  "),
            Span::styled(
                format!("kind: {}", app.launch_kind.label()),
                Style::default().fg(Color::Magenta),
            ),
            Span::raw("  "),
            Span::styled(
                format!("runtime: {}", app.launch_runtime.label()),
                Style::default().fg(Color::Yellow),
            ),
        ]),
        Line::from(vec![
            Span::styled("Prompt: ", Style::default().fg(Color::Gray)),
            Span::styled(app.launch_prompt.clone(), prompt_style),
        ]),
        Line::from(vec![
            Span::styled("Enter launch", Style::default().fg(Color::Green)),
            Span::raw("  "),
            Span::styled("a cycle agent", Style::default().fg(Color::Cyan)),
            Span::raw("  "),
            Span::styled("v cycle runtime", Style::default().fg(Color::Yellow)),
            Span::raw("  "),
            Span::styled("e edit prompt", Style::default().fg(Color::Yellow)),
        ]),
        Line::from(vec![
            Span::styled("Root: ", Style::default().fg(Color::Gray)),
            Span::styled(
                app.config.launch_root.to_string_lossy().into_owned(),
                Style::default().fg(Color::White),
            ),
        ]),
    ];

    let launch = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title("Launch panel"))
        .wrap(Wrap { trim: false });
    frame.render_widget(launch, area);
}

fn draw_deep_controls(frame: &mut Frame, area: Rect, app: &App) {
    let lines = app
        .deep_control_lines()
        .into_iter()
        .map(Line::from)
        .collect::<Vec<_>>();
    let panel = Paragraph::new(lines)
        .block(Block::default().borders(Borders::ALL).title("Selected run"))
        .wrap(Wrap { trim: false });
    frame.render_widget(panel, area);
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
