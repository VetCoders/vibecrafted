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
    recent_runs: Vec<DashboardRun>,
    all_runs: Vec<DashboardRun>,
    lifecycle_runs: Vec<DashboardLifecycleRun>,
    warnings: Vec<String>,
    events: Vec<DashboardEvent>,
}

#[derive(Clone, Default)]
struct DashboardSettlement {
    scope: String,
    active: usize,
    f: usize,
    x: usize,
    n: usize,
    invalid: usize,
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
    report_path: String,
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
            report_path: run.report_path,
            updated_at: run.updated_at,
        }
    }

    let state = crate::control::api::state_payload(plane, now);
    let all_runs = plane.load_snapshots();
    let lifecycle_runs = plane.load_lifecycle_run_summaries();
    let settlement = state.settlement_counts;

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
            total_settled: settlement.total_settled,
        },
        active_runs: state.active_runs.into_iter().map(run_summary).collect(),
        recent_runs: state.recent_runs.into_iter().map(run_summary).collect(),
        all_runs: all_runs.into_iter().map(run_summary).collect(),
        lifecycle_runs: lifecycle_runs.into_iter().map(lifecycle_summary).collect(),
        warnings: state.warnings,
        events: state.events.into_iter().map(event_summary).collect(),
    }
}

#[cfg(not(feature = "ssr"))]
fn load_dashboard_data() -> DashboardData {
    DashboardData::default()
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
                        <span class="control-badge">{run.agent}</span>
                        <span class="control-badge">{run.skill}</span>
                        <span class="control-badge">{run.mode}</span>
                    </div>
                    <div class="control-run-meta">
                        <span>{run.updated_at}</span>
                        <span>{report_label}</span>
                    </div>
                </article>
            }
        })
        .collect_view()
}

fn lifecycle_cards(runs: Vec<DashboardLifecycleRun>) -> impl IntoView {
    runs.into_iter()
        .map(|run| {
            let stage_label = if run.current_stage.is_empty() {
                "stage unknown".to_string()
            } else {
                run.current_stage.clone()
            };
            let baton_label = match (run.next_stage.is_empty(), run.next_agent.is_empty()) {
                (true, true) => "baton clear".to_string(),
                (false, true) => format!("next {}", run.next_stage),
                (true, false) => format!("next agent {}", run.next_agent),
                (false, false) => format!("next {} / {}", run.next_stage, run.next_agent),
            };
            let report_label = if run.report_path.is_empty() {
                "no report".to_string()
            } else {
                run.report_path.clone()
            };
            let controls_label = if run.human_controls.is_empty() {
                "controls none".to_string()
            } else {
                format!("controls {}", run.human_controls.join(", "))
            };

            view! {
                <article class="control-run-row">
                    <div class="control-run-primary">
                        <span class="control-run-id">{run.run_id}</span>
                        <span class="control-run-root">{run.workflow}</span>
                    </div>
                    <div class="control-run-tags">
                        <span class="control-badge">{run.status}</span>
                        <span class="control-badge">{stage_label}</span>
                        <span class="control-badge">{baton_label}</span>
                        <span class="control-badge">{run.dou_label}</span>
                        <span class="control-badge">{format!("accepted {}", run.accepted_dou)}</span>
                    </div>
                    <div class="control-run-meta">
                        <span>{run.updated_at}</span>
                        <span>{controls_label}</span>
                        <span>{format!("control count {}", run.human_controls_count)}</span>
                        <span>{format!("actions {}", run.operator_actions_count)}</span>
                        <span>{report_label}</span>
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
            class="settlement-board"
            aria-label="Settlement board"
            data-scope=settlement.scope.clone()
            data-active=settlement.active
            data-f=settlement.f
            data-x=settlement.x
            data-n=settlement.n
            data-invalid=settlement.invalid
            data-total-settled=settlement.total_settled
        >
            <div class="settlement-board-head">
                <div>
                    <p class="section-eyebrow">"settlement truth"</p>
                    <h2>"f / x / n"</h2>
                </div>
                <div class="settlement-scope">
                    <span>"scope"</span>
                    <strong>{settlement.scope.clone()}</strong>
                </div>
            </div>
            <dl class="settlement-cells">
                <div class="settlement-cell settlement-cell-f">
                    <dt><kbd>"f"</kbd> "Finalized"</dt>
                    <dd>{settlement.f}</dd>
                </div>
                <div class="settlement-cell settlement-cell-x">
                    <dt><kbd>"x"</kbd> "Failed"</dt>
                    <dd>{settlement.x}</dd>
                    <small>{format!("{} invalid", settlement.invalid)}</small>
                </div>
                <div class="settlement-cell settlement-cell-n">
                    <dt><kbd>"n"</kbd> "Needs attention"</dt>
                    <dd>{settlement.n}</dd>
                </div>
            </dl>
            <div class="settlement-board-foot">
                <span>{format!("{} active", settlement.active)}</span>
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
    let theme = use_theme();
    let dashboard = load_dashboard_data();
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

    view! {
        <Title text="vc-server - control plane" />
        <Meta name="description" content="Vibecrafted control-plane dashboard." />
        <Meta name="theme-color" content="#0e0e0e" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/inter-var-latin.woff2" crossorigin="anonymous" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/jetbrains-mono-var-latin.woff2" crossorigin="anonymous" />

        <main class="server-console-shell">
            <div class="settlement-board-wrap">
                {settlement_board(settlement)}
            </div>

            <section class="server-console-hero">
                <div class="server-console-topbar">
                    <span class="server-console-brand mono-cap">"vc-server"</span>
                    <span class="server-console-pill">{theme_state}</span>
                </div>

                <div class="server-console-grid">
                    <div class="server-console-copy">
                        <p class="section-eyebrow">"control plane"</p>
                        <h1>"vc-server"</h1>
                        <p>
                            "One typed read-model over the Vibecrafted runtime: active runs, recent state, events, warnings, and every stored run snapshot."
                        </p>
                        <p>
                            <a class="server-console-link" href="/scaffold">
                                "Open scaffold review"
                            </a>
                        </p>
                    </div>

                    <aside class="server-console-panel" aria-label="Console status preview">
                        <div class="server-console-panel-head">
                            <span class="mono-cap">"snapshot"</span>
                            <span class="server-console-pill">{theme_state}</span>
                        </div>
                        <dl>
                            <div>
                                <dt>"active"</dt>
                                <dd>{active_count}</dd>
                            </div>
                            <div>
                                <dt>"recent"</dt>
                                <dd>{recent_count}</dd>
                            </div>
                            <div>
                                <dt>"all runs"</dt>
                                <dd>{all_count}</dd>
                            </div>
                            <div>
                                <dt>"lifecycle"</dt>
                                <dd>{lifecycle_count}</dd>
                            </div>
                        </dl>
                    </aside>
                </div>
            </section>

            <section class="control-plane-band" aria-label="Control-plane dashboard">
                <div class="control-plane-meta">
                    <span>{dashboard.control_plane}</span>
                    <span>{dashboard.generated_at}</span>
                </div>

                <div class="control-dashboard-grid">
                    <section class="control-panel" aria-label="Active runs">
                        <div class="control-panel-head">
                            <h2>"Active"</h2>
                            <span>{active_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_active_runs}>"No active runs are visible in the typed state view."</p>
                        {run_cards(dashboard.active_runs)}
                    </section>

                    <section class="control-panel" aria-label="Warnings">
                        <div class="control-panel-head">
                            <h2>"Warnings"</h2>
                            <span>{warning_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_warnings}>"No warnings."</p>
                        <ul class="control-warning-list">
                            {warning_rows(dashboard.warnings)}
                        </ul>
                    </section>
                </div>

                <section class="control-panel control-panel-wide" aria-label="Lifecycle runs">
                    <div class="control-panel-head">
                        <h2>"Lifecycle"</h2>
                        <span>{lifecycle_count}</span>
                    </div>
                    <p class="control-empty" hidden={!no_lifecycle_runs}>"No lifecycle runs found under the control plane."</p>
                    <div class="control-run-list">
                        {lifecycle_cards(dashboard.lifecycle_runs)}
                    </div>
                </section>

                <section class="control-panel control-panel-wide" aria-label="All runs">
                    <div class="control-panel-head">
                        <h2>"All Runs"</h2>
                        <span>{all_count}</span>
                    </div>
                    <p class="control-empty" hidden={!no_all_runs}>"No run snapshots found under the control plane."</p>
                    <div class="control-run-list">
                        {run_cards(dashboard.all_runs)}
                    </div>
                </section>

                <div class="control-dashboard-grid">
                    <section class="control-panel" aria-label="Recent state view">
                        <div class="control-panel-head">
                            <h2>"Recent State View"</h2>
                            <span>{recent_count}</span>
                        </div>
                        {run_cards(dashboard.recent_runs)}
                    </section>

                    <section class="control-panel" aria-label="Event tail">
                        <div class="control-panel-head">
                            <h2>"Events"</h2>
                            <span>{event_count}</span>
                        </div>
                        <p class="control-empty" hidden={!no_events}>"No events in the current tail."</p>
                        <ul class="control-event-list">
                            {event_rows(dashboard.events)}
                        </ul>
                    </section>
                </div>
            </section>
        </main>
    }
}

#[cfg(all(test, feature = "ssr"))]
mod tests {
    use std::fs;
    use std::path::{Path, PathBuf};

    use chrono::Utc;
    use control_core::ControlPlane;
    use leptos::prelude::*;
    use serde_json::{Value, json};

    use super::{load_dashboard_data_from, settlement_board};
    use crate::control::api::state_payload;

    fn temp_home() -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!("vc-web-settlement-{}-{nanos}", std::process::id()))
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

        let plane = ControlPlane::new(&home);
        let now = chrono::DateTime::parse_from_rfc3339("2026-07-22T12:30:00+00:00")
            .expect("fixed now")
            .with_timezone(&Utc);
        let api = serde_json::to_value(state_payload(&plane, now)).expect("state JSON");
        let dashboard = load_dashboard_data_from(&plane, now);
        let html = settlement_board(dashboard.settlement).to_html();
        let board = &api["settlement_counts"];

        for key in ["active", "f", "x", "n", "invalid", "total_settled"] {
            let expected = board[key].as_u64().expect("numeric settlement field");
            let attribute = key.replace('_', "-");
            assert!(
                html.contains(&format!("data-{attribute}=\"{expected}\"")),
                "SSR {key} must equal API value {expected}: {html}"
            );
        }
        let scope = board["scope"].as_str().expect("scope string");
        assert!(html.contains(&format!("data-scope=\"{scope}\"")));
        assert!(html.contains("Finalized"));
        assert!(html.contains("Failed"));
        assert!(html.contains("Needs attention"));
        assert_eq!(board["f"], 1);
        assert_eq!(board["x"], 2);
        assert_eq!(board["invalid"], 1);
        assert_eq!(board["n"], 1);

        fs::remove_dir_all(home).ok();
    }
}
