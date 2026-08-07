//! vc-procs interactive application state.

use std::time::{Duration, Instant};

use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyModifiers};

use super::model::MonitorSnapshot;
use super::sampler::Sampler;
use super::ui;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SortMode {
    Rss,
    Cpu,
    Pid,
}

pub struct ProcsApp {
    pub snapshot: MonitorSnapshot,
    pub selected: usize,
    pub filter: String,
    pub filter_mode: bool,
    pub sort: SortMode,
    pub status: String,
    pub confirm_kill: Option<u32>,
    sampler: Sampler,
    last_sample: Instant,
    interval: Duration,
}

impl ProcsApp {
    pub fn new() -> Self {
        let mut sampler = Sampler::new();
        let snapshot = sampler.sample();
        Self {
            snapshot,
            selected: 0,
            filter: String::new(),
            filter_mode: false,
            sort: SortMode::Rss,
            status: "j/k navigate · / filter · s sort · r refresh · k kill · q quit".into(),
            confirm_kill: None,
            sampler,
            last_sample: Instant::now(),
            interval: Duration::from_millis(750),
        }
    }

    pub fn filtered_indices(&self) -> Vec<usize> {
        let f = self.filter.to_lowercase();
        self.snapshot
            .processes
            .iter()
            .enumerate()
            .filter(|(_, p)| {
                if f.is_empty() {
                    return true;
                }
                p.command.to_lowercase().contains(&f)
                    || p.name.to_lowercase().contains(&f)
                    || p.family.as_str().contains(&f)
                    || p.pid.to_string().contains(&f)
            })
            .map(|(i, _)| i)
            .collect()
    }

    pub fn tick_sample(&mut self) {
        if self.last_sample.elapsed() >= self.interval {
            let prev_id = self
                .filtered_indices()
                .get(self.selected)
                .and_then(|&i| self.snapshot.processes.get(i))
                .map(|p| p.identity.clone());
            self.snapshot = self.sampler.sample();
            self.apply_sort();
            if let Some(id) = prev_id {
                let idxs = self.filtered_indices();
                if let Some(pos) = idxs.iter().position(|&i| {
                    self.snapshot
                        .processes
                        .get(i)
                        .map(|p| p.identity == id)
                        .unwrap_or(false)
                }) {
                    self.selected = pos;
                } else {
                    self.selected = 0;
                }
            }
            self.last_sample = Instant::now();
        }
    }

    fn apply_sort(&mut self) {
        match self.sort {
            SortMode::Rss => super::model::sort_by_rss(&mut self.snapshot.processes),
            SortMode::Cpu => self.snapshot.processes.sort_by(|a, b| {
                b.cpu
                    .partial_cmp(&a.cpu)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| a.pid.cmp(&b.pid))
            }),
            SortMode::Pid => self.snapshot.processes.sort_by_key(|p| p.pid),
        }
    }

    pub fn handle_key(&mut self, key: KeyEvent) -> bool {
        if self.filter_mode {
            match key.code {
                KeyCode::Esc => {
                    self.filter_mode = false;
                }
                KeyCode::Enter => {
                    self.filter_mode = false;
                    self.selected = 0;
                }
                KeyCode::Backspace => {
                    self.filter.pop();
                    self.selected = 0;
                }
                KeyCode::Char(c) => {
                    self.filter.push(c);
                    self.selected = 0;
                }
                _ => {}
            }
            return false;
        }

        if let Some(pid) = self.confirm_kill {
            match key.code {
                KeyCode::Char('y') | KeyCode::Char('Y') => {
                    self.status = format!(
                        "kill delegated to `vibecrafted procs terminate` for pid {pid} (identity required from snapshot CLI)"
                    );
                    self.confirm_kill = None;
                }
                KeyCode::Esc | KeyCode::Char('n') | KeyCode::Char('N') => {
                    self.confirm_kill = None;
                    self.status = "kill cancelled".into();
                }
                _ => {}
            }
            return false;
        }

        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => return true,
            KeyCode::Char('c') if key.modifiers.contains(KeyModifiers::CONTROL) => return true,
            KeyCode::Char('j') | KeyCode::Down => {
                let n = self.filtered_indices().len().saturating_sub(1);
                self.selected = (self.selected + 1).min(n);
            }
            KeyCode::Char('k') | KeyCode::Up => {
                self.selected = self.selected.saturating_sub(1);
            }
            KeyCode::Char('K') => {
                let idxs = self.filtered_indices();
                if let Some(&i) = idxs.get(self.selected)
                    && let Some(row) = self.snapshot.processes.get(i)
                {
                    self.confirm_kill = Some(row.pid);
                    self.status = format!(
                        "Confirm kill pid {} ({})? y=yes n=cancel — signals go through vibecrafted procs",
                        row.pid,
                        row.family.as_str()
                    );
                }
            }
            KeyCode::Char('r') => {
                self.snapshot = self.sampler.sample();
                self.apply_sort();
                self.status = "refreshed".into();
            }
            KeyCode::Char('s') => {
                self.sort = match self.sort {
                    SortMode::Rss => SortMode::Cpu,
                    SortMode::Cpu => SortMode::Pid,
                    SortMode::Pid => SortMode::Rss,
                };
                self.apply_sort();
                self.status = format!("sort: {:?}", self.sort);
            }
            KeyCode::Char('/') => {
                self.filter_mode = true;
                self.status = "filter: type + Enter".into();
            }
            _ => {}
        }
        false
    }

    pub fn run(mut self) -> anyhow::Result<()> {
        crossterm::terminal::enable_raw_mode()?;
        let mut stdout = std::io::stdout();
        crossterm::execute!(stdout, crossterm::terminal::EnterAlternateScreen)?;
        let backend = ratatui::backend::CrosstermBackend::new(stdout);
        let mut terminal = ratatui::Terminal::new(backend)?;

        let result = (|| -> anyhow::Result<()> {
            loop {
                self.tick_sample();
                terminal.draw(|f| ui::draw(f, &self))?;
                if event::poll(Duration::from_millis(100))?
                    && let Event::Key(key) = event::read()?
                    && self.handle_key(key)
                {
                    break;
                }
            }
            Ok(())
        })();

        crossterm::terminal::disable_raw_mode()?;
        crossterm::execute!(
            terminal.backend_mut(),
            crossterm::terminal::LeaveAlternateScreen
        )?;
        result
    }
}

impl Default for ProcsApp {
    fn default() -> Self {
        Self::new()
    }
}
