// Application shell + root component.

use leptos::prelude::*;
use leptos_meta::{Link, Meta, Title};
use leptos_router::components::{Route, Router, Routes};
use leptos_router::path;

use crate::scaffold::ScaffoldEditorPage;
use crate::theme::{Theme, ThemeBridge, provide_theme_context, use_theme};

#[derive(Clone, Default)]
struct DashboardData {
    control_plane: String,
    generated_at: String,
    settlement: DashboardSettlement,
    active_runs: Vec<DashboardRun>,
    stalled_runs: Vec<DashboardRun>,
    recent_runs: Vec<DashboardRun>,
    lifecycle_runs: Vec<DashboardLifecycleRun>,
    warnings: Vec<String>,
    events: Vec<DashboardEvent>,
    loctree_report: String,
}

#[derive(Clone, Default)]
struct DashboardSettlement {
    scope: String,
    active: usize,
    f: usize,
    x: usize,
    n: usize,
    invalid: usize,
    unclassified: usize,
    total_settled: usize,
}

#[derive(Clone, Default)]
struct DashboardRun {
    run_id: String,
    state: String,
    health: String,
    agent: String,
    skill: String,
    mode: String,
    root: String,
    latest_report: String,
    updated_at: String,
    /// Settlement tui cell when Python wrote one (`f`/`x`/`n`), else empty.
    settlement_tui: String,
    last_error: String,
}

#[derive(Clone, Default)]
struct DashboardLifecycleRun {
    run_id: String,
    workflow: String,
    status: String,
    current_stage: String,
    next_stage: String,
    next_agent: String,
    dou_label: String,
    accepted_dou: i64,
    human_controls: Vec<String>,
    human_controls_count: usize,
    operator_actions_count: usize,
    updated_at: String,
}

#[derive(Clone, Default)]
struct DashboardEvent {
    ts: String,
    run_id: String,
    kind: String,
    message: String,
}

#[cfg(feature = "ssr")]
fn load_dashboard_data() -> DashboardData {
    use chrono::Utc;
    use control_core::ControlPlane;

    load_dashboard_data_from(&ControlPlane::from_env(), Utc::now())
}

#[cfg(feature = "ssr")]
fn load_dashboard_data_from(
    plane: &control_core::ControlPlane,
    now: chrono::DateTime<chrono::Utc>,
) -> DashboardData {
    use control_core::{Event, LifecycleRunSummary, RunStatus};

    fn run_summary(run: RunStatus) -> DashboardRun {
        let settlement_tui = run
            .settlement_tui
            .map(|cell| match cell {
                control_core::SettlementTui::F => "f",
                control_core::SettlementTui::X => "x",
                control_core::SettlementTui::N => "n",
            })
            .unwrap_or("")
            .to_string();
        DashboardRun {
            run_id: run.run_id,
            state: run.state,
            health: run.health,
            agent: run.agent,
            skill: run.skill,
            mode: run.mode,
            root: run.root,
            latest_report: run.latest_report,
            updated_at: run.updated_at,
            settlement_tui,
            last_error: run.last_error,
        }
    }

    fn event_summary(event: Event) -> DashboardEvent {
        DashboardEvent {
            ts: event.ts,
            run_id: event.run_id,
            kind: event.kind,
            message: event.message,
        }
    }

    fn lifecycle_summary(run: LifecycleRunSummary) -> DashboardLifecycleRun {
        let dou_label = match (run.dou_readiness.as_str(), run.dou_index) {
            ("zero", Some(0)) => "ZERO DoU".to_string(),
            ("open", Some(value)) => format!("DoU {value}"),
            _ => "DoU unknown".to_string(),
        };
        DashboardLifecycleRun {
            run_id: run.run_id,
            workflow: run.workflow,
            status: run.status,
            current_stage: run.current_stage,
            next_stage: run.next_stage,
            next_agent: run.next_agent,
            dou_label,
            accepted_dou: run.accepted_dou,
            human_controls: run.human_controls,
            human_controls_count: run.human_controls_count,
            operator_actions_count: run.operator_actions_count,
            updated_at: run.updated_at,
        }
    }

    let state = crate::control::api::state_payload(plane, now);
    let lifecycle_runs = plane.load_lifecycle_run_summaries();
    let settlement = state.settlement_counts;
    let loctree_report = state
        .active_runs
        .iter()
        .chain(state.recent_runs.iter())
        .filter_map(|run| {
            let path = std::path::Path::new(&run.root).join(".loctree/report.html");
            path.is_file().then(|| path.to_string_lossy().into_owned())
        })
        .next()
        .unwrap_or_default();

    DashboardData {
        control_plane: state.control_plane,
        generated_at: state.generated_at,
        settlement: DashboardSettlement {
            scope: serde_json::to_value(settlement.scope)
                .ok()
                .and_then(|value| value.as_str().map(str::to_owned))
                .unwrap_or_else(|| "unknown".to_string()),
            active: settlement.active,
            f: settlement.f,
            x: settlement.x,
            n: settlement.n,
            invalid: settlement.invalid,
            unclassified: settlement.unclassified,
            total_settled: settlement.total_settled,
        },
        active_runs: state.active_runs.into_iter().map(run_summary).collect(),
        stalled_runs: state.stalled_runs.into_iter().map(run_summary).collect(),
        recent_runs: state.recent_runs.into_iter().map(run_summary).collect(),
        lifecycle_runs: lifecycle_runs.into_iter().map(lifecycle_summary).collect(),
        warnings: state.warnings,
        events: state.events.into_iter().map(event_summary).collect(),
        loctree_report,
    }
}

#[cfg(not(feature = "ssr"))]
fn load_dashboard_data() -> DashboardData {
    DashboardData::default()
}

fn settlement_badge(tui: String) -> String {
    if tui.is_empty() {
        "settle:—".to_string()
    } else {
        format!("settle:{tui}")
    }
}

fn run_cards(runs: Vec<DashboardRun>) -> impl IntoView {
    runs.into_iter()
        .map(|run| {
            let report_label = if run.latest_report.is_empty() {
                "no report".to_string()
            } else {
                run.latest_report.clone()
            };

            view! {
                <article class="control-run-row">
                    <div class="control-run-primary">
                        <span class="control-run-id">{run.run_id}</span>
                        <span class="control-run-root">{run.root}</span>
                    </div>
                    <div class="control-run-tags">
                        <span class="control-badge">{run.state}</span>
                        <span class="control-badge">{run.health}</span>
                        <span class="control-badge">{settlement_badge(run.settlement_tui.clone())}</span>
                        <span class="control-badge">{run.agent}</span>
                        <span class="control-badge">{run.skill}</span>
                        <span class="control-badge">{run.mode}</span>
                    </div>
                    <div class="control-run-meta">
                        <span>{run.updated_at}</span>
                        <span>{report_label}</span>
                        <span class="control-run-error">{run.last_error}</span>
                    </div>
                </article>
            }
        })
        .collect_view()
}

fn is_terminal_state(state: &str) -> bool {
    matches!(
        state.to_ascii_lowercase().as_str(),
        "report_validated"
            | "completed"
            | "closed"
            | "converged"
            | "finalized"
            | "failed"
            | "blocked"
            | "cancelled"
            | "stopped"
    )
}

fn is_quarantined_run(run: &DashboardRun) -> bool {
    run.run_id == "smoke-nonexistent"
        || run.run_id.starts_with("smoke-")
        || (run.skill.eq_ignore_ascii_case("marbles") && run.health != "active")
}

fn operator_active_runs(runs: Vec<DashboardRun>) -> Vec<DashboardRun> {
    runs.into_iter()
        .filter(|run| {
            run.health == "active" && !is_terminal_state(&run.state) && !is_quarantined_run(run)
        })
        .take(8)
        .collect()
}

fn operator_action_runs(runs: Vec<DashboardLifecycleRun>) -> Vec<DashboardLifecycleRun> {
    runs.into_iter()
        .filter(|run| !is_terminal_state(&run.status) && !run.run_id.starts_with("smoke-"))
        .take(6)
        .collect()
}

fn action_cards(runs: Vec<DashboardLifecycleRun>) -> impl IntoView {
    runs.into_iter()
        .map(|run| {
            let stage_label = if run.current_stage.is_empty() {
                "stage unknown".to_string()
            } else {
                run.current_stage.clone()
            };
            let next_action = if let Some(control) = run.human_controls.first() {
                format!("Operator: {control}")
            } else if !run.next_stage.is_empty() && !run.next_agent.is_empty() {
                format!("Launch {} with {}", run.next_stage, run.next_agent)
            } else if !run.next_stage.is_empty() {
                format!("Advance to {}", run.next_stage)
            } else if !run.next_agent.is_empty() {
                format!("Hand off to {}", run.next_agent)
            } else {
                "Inspect the latest runtime event".to_string()
            };

            view! {
                <article class="operator-action-row">
                    <div class="control-run-primary">
                        <span class="control-run-id">{run.run_id}</span>
                        <span class="control-run-root">{run.workflow}</span>
                    </div>
                    <div class="control-run-tags">
                        <span class="control-badge">{run.status}</span>
                        <span class="control-badge">{stage_label}</span>
                        <span class="control-badge">{run.dou_label}</span>
                        <span class="control-badge">{format!("accepted {}", run.accepted_dou)}</span>
                    </div>
                    <div class="operator-next-action">
                        <strong>"Next action"</strong>
                        <span>{next_action}</span>
                    </div>
                    <div class="control-run-meta">
                        <span>{run.updated_at}</span>
                        <span>{format!("{} controls / {} actions", run.human_controls_count, run.operator_actions_count)}</span>
                    </div>
                </article>
            }
        })
        .collect_view()
}

fn event_rows(events: Vec<DashboardEvent>) -> impl IntoView {
    events
        .into_iter()
        .map(|event| {
            view! {
                <li class="control-event-row">
                    <span>{event.ts}</span>
                    <strong>{event.kind}</strong>
                    <span>{event.run_id}</span>
                    <span>{event.message}</span>
                </li>
            }
        })
        .collect_view()
}

fn warning_rows(warnings: Vec<String>) -> impl IntoView {
    warnings
        .into_iter()
        .map(|warning| view! { <li>{warning}</li> })
        .collect_view()
}

fn settlement_board(settlement: DashboardSettlement) -> impl IntoView {
    view! {
        <section
            class="operator-summary-strip"
            aria-label="Operator summary"
            data-scope=settlement.scope.clone()
            data-active=settlement.active
            data-f=settlement.f
            data-x=settlement.x
            data-n=settlement.n
            data-invalid=settlement.invalid
            data-unclassified=settlement.unclassified
            data-total-settled=settlement.total_settled
        >
            <div class="operator-summary-title">
                <span class="mono-cap">"runtime truth"</span>
                <strong>{settlement.scope.clone()}</strong>
            </div>
            <dl class="operator-summary-cells">
                <a class="operator-summary-cell" href="#fleet">
                    <dt>"alive"</dt>
                    <dd>{settlement.active}</dd>
                </a>
                <a class="operator-summary-cell" href="#fleet">
                    <dt>"final"</dt>
                    <dd>{settlement.f}</dd>
                </a>
                <a class="operator-summary-cell" href="#fleet">
                    <dt>"failed"</dt>
                    <dd>{settlement.x}</dd>
                </a>
                <a class="operator-summary-cell" href="#fleet">
                    <dt>"attention"</dt>
                    <dd>{settlement.n}</dd>
                </a>
            </dl>
            <div class="operator-summary-detail">
                <span>{format!("{} invalid", settlement.invalid)}</span>
                <span>{format!("{} unclassified", settlement.unclassified)}</span>
                <span>{format!("{} settled", settlement.total_settled)}</span>
            </div>
        </section>
    }
}

#[cfg(feature = "ssr")]
pub fn shell(options: leptos::config::LeptosOptions) -> impl IntoView {
    use leptos_meta::MetaTags;

    const STYLE_TOKENS: &str = include_str!("../styles/tokens.css");
    const STYLE_FONTS: &str = include_str!("../styles/fonts.css");
    const STYLE_MAIN: &str = include_str!("../styles/main.css");

    let _ = options;

    view! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <MetaTags/>
                <style>{STYLE_TOKENS}</style>
                <style>{STYLE_FONTS}</style>
                <style>{STYLE_MAIN}</style>
            </head>
            <body>
                <App/>
            </body>
        </html>
    }
}

#[component]
pub fn App() -> impl IntoView {
    leptos_meta::provide_meta_context();
    provide_theme_context();

    view! {
        <Router>
            <ThemeBridge />
            <Routes fallback=|| view! { <ConsolePage /> }>
                <Route path=path!("/") view=ConsolePage />
                <Route path=path!("/scaffold") view=ScaffoldEditorPage />
            </Routes>
        </Router>
    }
}

#[component]
pub fn ConsolePage() -> impl IntoView {
    let dashboard = load_dashboard_data();

    view! {
        <Title text="vc-server - control plane" />
        <Meta name="description" content="Vibecrafted control-plane dashboard." />
        <Meta name="theme-color" content="#0e0e0e" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/inter-var-latin.woff2" crossorigin="anonymous" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/jetbrains-mono-var-latin.woff2" crossorigin="anonymous" />
        {console_dashboard(dashboard)}
    }
}

fn console_dashboard(dashboard: DashboardData) -> impl IntoView {
    let theme = use_theme();
    let active_count = dashboard.active_runs.len();
    let recent_count = dashboard.recent_runs.len();
    let all_count = dashboard.all_runs.len();
    let lifecycle_count = dashboard.lifecycle_runs.len();
    let warning_count = dashboard.warnings.len();
    let event_count = dashboard.events.len();
    let settlement = dashboard.settlement.clone();
    let no_active_runs = dashboard.active_runs.is_empty();
    let no_all_runs = dashboard.all_runs.is_empty();
    let no_lifecycle_runs = dashboard.lifecycle_runs.is_empty();
    let no_warnings = dashboard.warnings.is_empty();
    let no_events = dashboard.events.is_empty();
    let theme_state = move || match theme.get() {
        Theme::Dark => "dark",
        Theme::Light => "light",
    };
    let has_loctree_link = loctree_link.is_some();

    view! {
        <main class="server-console-shell">
            <div class="settlement-board-wrap">
                {settlement_board(settlement)}
            </div>

            <section class="server-console-hero">
                <div class="server-console-topbar">
                    <span class="server-console-brand mono-cap">"vc-server"</span>
                    <button
                        type="button"
                        class="server-console-toggle"
                        aria-label="Toggle color theme"
                        aria-pressed=move || theme.get() == Theme::Light
                        on:click=move |_| theme.update(|current| *current = current.toggle())
                    >
                        {move || format!("{} mode", theme.get().code())}
                    </button>
                </div>

                <nav class="operator-rail" aria-label="Operator rail">
                    <a href="#now">"NOW"</a>
                    <a href="#fleet">"Fleet"</a>
                    <a href="#context">"Context"</a>
                    <a href="#structure">"Structure"</a>
                </nav>

                <div class="server-console-grid">
                    <div class="server-console-copy" id="now">
                        <p class="section-eyebrow">"control plane"</p>
                        <h1>"Operator Console"</h1>
                        <p>
                            "One live shell for what is running, what needs a decision, and where the supporting context lives."
                        </p>
                        <p class="server-console-links">
                            <a class="server-console-link" href="/scaffold">
                                "Open scaffold review"
                            </a>
                            <a
                                class="server-console-link"
                                href="http://127.0.0.1:8033/?q=vibecrafted+server&sort=oldest"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                "Open AICX context"
                            </a>
                            <a class="server-console-link" href="#structure">
                                "Jump to structure"
                            </a>
                        </p>
                    </div>

                    <aside class="server-console-panel" aria-label="Console status preview">
                        <div class="server-console-panel-head">
                            <span class="mono-cap">"right now"</span>
                            <button
                                type="button"
                                class="server-console-toggle server-console-toggle-compact"
                                aria-label="Toggle color theme"
                                aria-pressed=move || theme.get() == Theme::Light
                                on:click=move |_| theme.update(|current| *current = current.toggle())
                            >
                                {move || theme.get().code()}
                            </button>
                        </div>
                        <dl class="operator-now-cells">
                            <a class="operator-summary-cell" href="#fleet">
                                <dt>"alive"</dt>
                                <dd>{active_count}</dd>
                            </a>
                            <a class="operator-summary-cell" href="#fleet">
                                <dt>"next"</dt>
                                <dd>{action_count}</dd>
                            </a>
                            <a class="operator-summary-cell" href="#fleet">
                                <dt>"warnings"</dt>
                                <dd>{warning_count}</dd>
                            </a>
                            <a class="operator-summary-cell" href="#context">
                                <dt>"stalled"</dt>
                                <dd>{stalled_count}</dd>
                            </div>
                            <div>
                                <dt>"recent"</dt>
                                <dd>{recent_count}</dd>
                            </a>
                        </dl>
                    </aside>
                </div>
            </section>

            <section class="control-plane-band" id="fleet" aria-label="Control-plane dashboard">
                <div class="control-plane-meta">
                    <span>{control_plane}</span>
                    <span>{generated_at}</span>
                </div>

                <div class="control-dashboard-grid">
                    <section class="control-panel" aria-label="Active runs">
                        <div class="control-panel-head">
                            <h2>"Active"</h2>
                            <span>{active_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_active_runs}>"No live workers need the hero right now."</p>
                        <div class="control-run-list">
                            {run_cards(active_runs)}
                        </div>
                    </section>

                    <section class="control-panel" aria-label="Stalled runs">
                        <div class="control-panel-head">
                            <h2>"Stalled"</h2>
                            <span>{stalled_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_stalled_runs}>"No stalled runs."</p>
                        {run_cards(dashboard.stalled_runs)}
                    </section>

                    <section class="control-panel" aria-label="Warnings">
                        <div class="control-panel-head">
                            <h2>"Warnings"</h2>
                            <span>{warning_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_warnings}>"No warnings."</p>
                        <ul class="control-warning-list">
                            {warning_rows(warnings)}
                        </ul>
                    </section>
                </div>

                <section class="control-panel control-panel-wide" aria-label="Action plan">
                    <div class="control-panel-head">
                        <h2>"Action Plan"</h2>
                        <span>{action_count}</span>
                    </div>
                    <p class="control-empty" hidden={!no_action_runs}>"No lifecycle baton currently needs an operator action."</p>
                    <div class="operator-action-list">
                        {action_cards(action_runs)}
                    </div>
                </section>

                <div class="control-dashboard-grid" id="context">
                    <section class="control-panel" aria-label="Recent state view">
                        <div class="control-panel-head">
                            <h2>"Recent truth"</h2>
                            <span>{recent_count}</span>
                        </div>
                        <div class="control-run-list">
                            {run_cards(recent_runs)}
                        </div>
                    </section>

                    <section class="control-panel" aria-label="Event tail">
                        <div class="control-panel-head">
                            <h2>"Runtime context"</h2>
                            <span>{event_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_events}>"No events in the current tail."</p>
                        <ul class="control-event-list">
                            {event_rows(events)}
                        </ul>
                    </section>
                </div>

                <section class="control-panel control-panel-wide" id="structure" aria-label="Structure">
                    <div class="control-panel-head">
                        <h2>"Structure"</h2>
                        <span>"Loctree + scaffold"</span>
                    </div>
                    <div class="structure-links">
                        {loctree_link.map(|href| view! {
                            <a class="server-console-link" href=href>"Open last Loctree report"</a>
                        })}
                        <a class="server-console-link" href="/scaffold">"Open scaffold review"</a>
                    </div>
                    <p class="control-empty" hidden=has_loctree_link>
                        "No Loctree report is known for the roots in the canonical state view."
                    </p>
                </section>
            </section>
        </main>
    }
}

#[cfg(all(test, feature = "ssr"))]
mod tests {
    use std::fs;
    use std::io::ErrorKind;
    use std::path::{Path, PathBuf};
    use std::sync::atomic::{AtomicU64, Ordering};

    use chrono::Utc;
    use control_core::ControlPlane;
    use leptos::prelude::*;
    use serde_json::{Value, json};

    use super::{DashboardRun, console_dashboard, load_dashboard_data_from, operator_active_runs};
    use crate::control::api::state_payload;
    use crate::theme::provide_theme_context;

    fn temp_home() -> PathBuf {
        static NEXT_ID: AtomicU64 = AtomicU64::new(0);

        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let base = std::env::var_os("TMPDIR")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("/tmp"));

        for attempt in 0..100 {
            let nonce = NEXT_ID.fetch_add(1, Ordering::Relaxed);
            let candidate = base.join(format!(
                "vc-web-settlement-{}-{nanos}-{nonce}-{attempt}",
                std::process::id()
            ));
            match fs::create_dir(&candidate) {
                Ok(()) => return candidate,
                Err(error) if error.kind() == ErrorKind::AlreadyExists => continue,
                Err(error) => panic!("create isolated fixture home: {error}"),
            }
        }

        panic!("could not allocate an isolated fixture home")
    }

    fn write_snapshot(runs_dir: &Path, run_id: &str, verdict: &str, tui: &str) {
        let payload = json!({
            "run_id": run_id,
            "state": "completed",
            "agent": "codex",
            "skill": "implement",
            "mode": "implement",
            "root": "/tmp/repo",
            "operator_session": format!("repo-{run_id}"),
            "latest_report": "",
            "latest_transcript": "",
            "last_error": "",
            "updated_at": "2026-07-22T12:00:00+00:00",
            "started_at": "2026-07-22T11:59:00+00:00",
            "health": "final",
            "source": "agent-meta",
            "lock_present": false,
            "exit_code": Value::Null,
            "liveness": "terminal",
            "launcher_pid": Value::Null,
            "completed_at": "2026-07-22T12:00:00+00:00",
            "session_id": "",
            "current_loop": Value::Null,
            "total_loops": Value::Null,
            "settlement_verdict": verdict,
            "settlement_tui": tui,
        });
        fs::write(
            runs_dir.join(format!("{run_id}.json")),
            serde_json::to_vec_pretty(&payload).expect("snapshot JSON"),
        )
        .expect("write snapshot");
    }

    #[test]
    fn state_json_and_ssr_render_the_same_canonical_settlement_board() {
        let home = temp_home();
        let runs_dir = home.join("control_plane/runs");
        fs::create_dir_all(&runs_dir).expect("runs dir");
        write_snapshot(&runs_dir, "finalized", "finalized", "f");
        write_snapshot(&runs_dir, "failed", "failed", "x");
        write_snapshot(&runs_dir, "invalid", "invalid", "x");
        write_snapshot(&runs_dir, "attention", "needs_attention", "n");
        let locks_dir = home.join("locks");
        fs::create_dir_all(&locks_dir).expect("locks dir");
        fs::write(
            locks_dir.join("raw-only.lock"),
            "run_id=raw-only\nstatus=running\nagent=codex\n",
        )
        .expect("write raw lock");

        let plane = ControlPlane::new(&home);
        let now = chrono::DateTime::parse_from_rfc3339("2026-07-22T12:30:00+00:00")
            .expect("fixed now")
            .with_timezone(&Utc);
        let api = serde_json::to_value(state_payload(&plane, now)).expect("state JSON");
        let dashboard = load_dashboard_data_from(&plane, now);
        let owner = Owner::new();
        let html = owner.with(|| {
            provide_theme_context();
            console_dashboard(dashboard).to_html()
        });
        let board = &api["settlement_counts"];
        assert!(
            api["recent_runs"]
                .as_array()
                .expect("recent runs")
                .iter()
                .all(|run| run["run_id"] != "raw-only"),
            "the HTTP/SSR projection must use Python-owned snapshots, not rescan raw locks"
        );

        for key in [
            "active",
            "f",
            "x",
            "n",
            "invalid",
            "unclassified",
            "total_settled",
        ] {
            let expected = board[key].as_u64().expect("numeric settlement field");
            let attribute = key.replace('_', "-");
            assert!(
                html.contains(&format!("data-{attribute}=\"{expected}\"")),
                "SSR {key} must equal API value {expected}: {html}"
            );
        }
        let scope = board["scope"].as_str().expect("scope string");
        assert!(html.contains(&format!("data-scope=\"{scope}\"")));
        assert!(html.contains("final"));
        assert!(html.contains("failed"));
        assert!(html.contains("attention"));
        assert!(html.contains("aria-label=\"Toggle color theme\""));
        assert!(html.contains("http://127.0.0.1:8033/"));
        assert!(html.contains("operator-rail"));
        assert!(html.contains("href=\"#fleet\""));
        assert!(!html.contains("aria-label=\"All runs\""));
        let board_position = html
            .find("aria-label=\"Operator summary\"")
            .expect("summary");
        let active_position = html
            .find("aria-label=\"Active runs\"")
            .expect("active runs");
        let warnings_position = html.find("aria-label=\"Warnings\"").expect("warnings");
        let action_position = html
            .find("aria-label=\"Action plan\"")
            .expect("action plan");
        let recent_position = html
            .find("aria-label=\"Recent state view\"")
            .expect("recent state");
        let events_position = html.find("aria-label=\"Event tail\"").expect("event tail");
        let structure_position = html.find("aria-label=\"Structure\"").expect("structure");
        assert!(
            board_position < active_position,
            "operator summary must be the first fleet summary"
        );
        assert!(board_position < warnings_position);
        assert!(active_position < action_position);
        assert!(warnings_position < action_position);
        assert!(action_position < recent_position);
        assert!(recent_position < events_position);
        assert!(events_position < structure_position);
        assert_eq!(board["f"], 1);
        assert_eq!(board["x"], 2);
        assert_eq!(board["invalid"], 1);
        assert_eq!(board["n"], 1);

        fs::remove_dir_all(home).ok();
    }

    #[test]
    fn active_hero_quarantines_smoke_terminal_and_stale_marbles_noise() {
        fn run(run_id: &str, state: &str, health: &str, skill: &str) -> DashboardRun {
            DashboardRun {
                run_id: run_id.to_string(),
                state: state.to_string(),
                health: health.to_string(),
                skill: skill.to_string(),
                ..DashboardRun::default()
            }
        }

        let visible = operator_active_runs(vec![
            run("smoke-nonexistent", "running", "active", "implement"),
            run("smoke-old", "running", "active", "implement"),
            run("marb-old", "completed", "final", "marbles"),
            run(
                "terminal-but-marked-active",
                "completed",
                "active",
                "implement",
            ),
            run("real-worker", "running", "active", "ownership"),
        ]);

        assert_eq!(visible.len(), 1);
        assert_eq!(visible[0].run_id, "real-worker");
    }
}
