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
    active_runs: Vec<DashboardRun>,
    recent_runs: Vec<DashboardRun>,
    all_runs: Vec<DashboardRun>,
    warnings: Vec<String>,
    events: Vec<DashboardEvent>,
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
struct DashboardEvent {
    ts: String,
    run_id: String,
    kind: String,
    message: String,
}

#[cfg(feature = "ssr")]
fn load_dashboard_data() -> DashboardData {
    use chrono::Utc;
    use control_core::{ControlPlane, Event, RunStatus};

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

    let plane = ControlPlane::from_env();
    let now = Utc::now();
    let view = plane.compute_view(now);
    let all_runs = plane.load_snapshots();

    DashboardData {
        control_plane: plane.control_plane_home().display().to_string(),
        generated_at: now.to_rfc3339(),
        active_runs: view.active_runs.into_iter().map(run_summary).collect(),
        recent_runs: view.recent_runs.into_iter().map(run_summary).collect(),
        all_runs: all_runs.into_iter().map(run_summary).collect(),
        warnings: view.warnings,
        events: view.events.into_iter().map(event_summary).collect(),
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
    let warning_count = dashboard.warnings.len();
    let event_count = dashboard.events.len();
    let no_active_runs = dashboard.active_runs.is_empty();
    let no_all_runs = dashboard.all_runs.is_empty();
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
