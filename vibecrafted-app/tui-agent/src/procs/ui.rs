//! Ratatui rendering for vc-procs.

use ratatui::Frame;
use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
#[allow(unused_imports)]
use ratatui::text::Text;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Cell, Gauge, Paragraph, Row, Table};

use super::app::ProcsApp;
use super::model::format_bytes;

pub fn draw(frame: &mut Frame, app: &ProcsApp) {
    let area = frame.area();
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Length(3),
            Constraint::Length(3),
            Constraint::Min(6),
            Constraint::Length(2),
        ])
        .split(area);

    draw_gauge(
        frame,
        chunks[0],
        "CPU",
        f64::from(app.snapshot.system_cpu_percent) / 100.0,
        format!("CPU {:.1}%", app.snapshot.system_cpu_percent),
        Color::Green,
    );

    let ram_ratio = if app.snapshot.system_ram_total > 0 {
        app.snapshot.system_ram_used as f64 / app.snapshot.system_ram_total as f64
    } else {
        0.0
    };
    draw_gauge(
        frame,
        chunks[1],
        "RAM",
        ram_ratio,
        format!(
            "RAM {} / {}",
            format_bytes(app.snapshot.system_ram_used),
            format_bytes(app.snapshot.system_ram_total)
        ),
        Color::Blue,
    );

    if let Some(gpu) = app.snapshot.gpu_util_percent {
        draw_gauge(
            frame,
            chunks[2],
            "GPU",
            (gpu / 100.0) as f64,
            format!("GPU {:.1}% · {}", gpu, app.snapshot.gpu_status),
            Color::Magenta,
        );
    } else {
        let p = Paragraph::new(format!("GPU: {}", app.snapshot.gpu_status))
            .style(Style::default().fg(Color::DarkGray))
            .block(Block::default().borders(Borders::ALL).title(" GPU "));
        frame.render_widget(p, chunks[2]);
    }

    draw_table(frame, chunks[3], app);

    let footer = if app.filter_mode {
        format!("filter> {}_", app.filter)
    } else {
        app.status.clone()
    };
    frame.render_widget(
        Paragraph::new(footer).style(Style::default().fg(Color::Yellow)),
        chunks[4],
    );
}

fn draw_gauge(frame: &mut Frame, area: Rect, title: &str, ratio: f64, label: String, color: Color) {
    let g = Gauge::default()
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(format!(" {title} ")),
        )
        .gauge_style(Style::default().fg(color).bg(Color::DarkGray))
        .ratio(ratio.clamp(0.0, 1.0))
        .label(label);
    frame.render_widget(g, area);
}

fn draw_table(frame: &mut Frame, area: Rect, app: &ProcsApp) {
    let idxs = app.filtered_indices();
    let header = Row::new(vec!["PID", "FAMILY", "CPU%", "RSS", "COMMAND"])
        .style(Style::default().add_modifier(Modifier::BOLD));
    let rows = idxs.iter().enumerate().filter_map(|(vis, &i)| {
        let p = app.snapshot.processes.get(i)?;
        let style = if vis == app.selected {
            Style::default()
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD)
        } else {
            Style::default()
        };
        Some(
            Row::new(vec![
                Cell::from(p.pid.to_string()),
                Cell::from(p.family.as_str()),
                Cell::from(format!("{:.1}", p.cpu)),
                Cell::from(format_bytes(p.rss)),
                Cell::from(p.truncated_cmd(area.width.saturating_sub(36) as usize)),
            ])
            .style(style),
        )
    });

    let table = Table::new(
        rows,
        [
            Constraint::Length(8),
            Constraint::Length(12),
            Constraint::Length(7),
            Constraint::Length(10),
            Constraint::Min(20),
        ],
    )
    .header(header)
    .block(
        Block::default()
            .borders(Borders::ALL)
            .title(Line::from(vec![
                Span::raw(" processes "),
                Span::styled(
                    format!("({} shown)", idxs.len()),
                    Style::default().fg(Color::DarkGray),
                ),
            ])),
    );
    frame.render_widget(table, area);
}
