use leptos::prelude::*;
use leptos_meta::{Link, Meta, Title};

#[component]
pub fn ScaffoldEditorPage() -> impl IntoView {
    view! {
        <Title text="vibecrafted server - scaffold review" />
        <Meta
            name="description"
            content="Editable multi-tab vc-scaffold artifact review surface."
        />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/inter-var-latin.woff2" crossorigin="anonymous" />
        <Link rel="preload" as_="font" type_="font/woff2" href="/fonts/jetbrains-mono-var-latin.woff2" crossorigin="anonymous" />

        <main class="scaffold-editor-shell">
            <iframe
                class="scaffold-editor-frame"
                title="Scaffold artifact editor"
                src="/scaffold/editor"
            />
        </main>
    }
}

#[cfg(feature = "ssr")]
pub mod api {
    use std::collections::BTreeSet;

    use axum::extract::{Form, Query};
    use axum::http::{StatusCode, header};
    use axum::response::{Html, IntoResponse, Response};
    use axum::routing::{get, post};
    use axum::{Json, Router};
    use control_core::{
        ScaffoldArtifact, ScaffoldArtifactPatch, ScaffoldArtifactStore, ScaffoldCheckpointPatch,
        ScaffoldDoctorReport, ScaffoldError, ScaffoldPlanSummary, ScaffoldWorkspace,
        vibecrafted_home,
    };
    use serde::Deserialize;

    #[derive(Debug, Clone, Deserialize)]
    pub struct ScaffoldQuery {
        org: Option<String>,
        repo: Option<String>,
        day: Option<String>,
        plan_id: Option<String>,
    }

    #[derive(Debug, Clone, Deserialize)]
    pub struct SaveArtifactForm {
        org: String,
        repo: String,
        day: String,
        plan_id: String,
        artifact_id: String,
        content: String,
        expected_hash: String,
    }

    #[derive(Debug, Clone, Deserialize)]
    pub struct CheckpointForm {
        org: String,
        repo: String,
        day: String,
        plan_id: String,
        artifact_id: String,
        #[serde(default)]
        approved: Option<String>,
        #[serde(default)]
        note: String,
    }

    #[derive(Debug, Clone)]
    struct ScaffoldPlanCard {
        plan: ScaffoldPlanSummary,
        reviewable: bool,
    }

    pub fn scaffold_routes() -> Router<leptos::config::LeptosOptions> {
        Router::<leptos::config::LeptosOptions>::new()
            .route("/scaffold/editor", get(editor))
            .route("/api/scaffold/plans", get(plans))
            .route("/api/scaffold/artifacts", get(artifacts))
            .route("/api/scaffold/changes", get(changes))
            .route("/api/scaffold/artifact", post(save_artifact))
            .route("/api/scaffold/checkpoint", post(save_checkpoint))
    }

    async fn editor(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        match load_workspace(query.clone()) {
            Ok(workspace) => Html(render_editor(&workspace)).into_response(),
            Err(ScaffoldError::SelectionRequired { plan_ids }) => {
                let store = ScaffoldArtifactStore::new(vibecrafted_home());
                let plans = matching_plans(&store, &query, &plan_ids);
                Html(render_plan_picker(&plan_card_views(&store, plans))).into_response()
            }
            Err(error) => {
                let store = ScaffoldArtifactStore::new(vibecrafted_home());
                if let Some(plan) = selected_plan(&store, &query) {
                    let report = store
                        .doctor(&plan.org, &plan.repo, &plan.day, &plan.plan_id)
                        .ok();
                    Html(render_plan_blocked(
                        &plan,
                        report.as_ref(),
                        &error.to_string(),
                    ))
                    .into_response()
                } else {
                    (
                        StatusCode::NOT_FOUND,
                        Html(render_empty(&format!(
                            "Scaffold artifacts unavailable: {error}"
                        ))),
                    )
                        .into_response()
                }
            }
        }
    }

    async fn plans(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let Some((org, repo, day)) = explicit_day(&query) else {
            return Json(serde_json::json!({"plans": store.catalog()})).into_response();
        };
        match store.plans(org, repo, day) {
            Ok(plans) => Json(serde_json::json!({"plans": plans})).into_response(),
            Err(error) => scaffold_error_response(error),
        }
    }

    async fn artifacts(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        match load_workspace(query) {
            Ok(workspace) => Json(workspace).into_response(),
            Err(error) => scaffold_error_response(error),
        }
    }

    async fn changes(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let workspace = match load_workspace(query) {
            Ok(workspace) => workspace,
            Err(error) => return scaffold_error_response(error),
        };
        match store.changes(
            &workspace.org,
            &workspace.repo,
            &workspace.day,
            &workspace.plan_id,
        ) {
            Ok(changes) => Json(changes).into_response(),
            Err(error) => (
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({ "error": error.to_string() })),
            )
                .into_response(),
        }
    }

    async fn save_artifact(Form(form): Form<SaveArtifactForm>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let result = store.write_artifact(
            &form.org,
            &form.repo,
            &form.day,
            &form.plan_id,
            ScaffoldArtifactPatch {
                artifact_id: form.artifact_id,
                content: form.content,
                expected_hash: form.expected_hash,
            },
        );
        redirect_after_mutation(
            &form.org,
            &form.repo,
            &form.day,
            &form.plan_id,
            result.err(),
        )
    }

    async fn save_checkpoint(Form(form): Form<CheckpointForm>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let result = store.checkpoint(
            &form.org,
            &form.repo,
            &form.day,
            &form.plan_id,
            ScaffoldCheckpointPatch {
                artifact_id: form.artifact_id,
                approved: form.approved.is_some(),
                note: form.note,
            },
        );
        redirect_after_mutation(
            &form.org,
            &form.repo,
            &form.day,
            &form.plan_id,
            result.err(),
        )
    }

    fn redirect_after_mutation(
        org: &str,
        repo: &str,
        day: &str,
        plan_id: &str,
        error: Option<ScaffoldError>,
    ) -> Response {
        let status = if let Some(error) = error {
            eprintln!("scaffold mutation failed: {error}");
            "status-error"
        } else {
            "status-saved"
        };
        let location = format!(
            "/scaffold/editor?org={}&repo={}&day={}&plan_id={}#{status}",
            url_component(org),
            url_component(repo),
            url_component(day),
            url_component(plan_id),
        );
        (StatusCode::SEE_OTHER, [(header::LOCATION, location)]).into_response()
    }

    fn load_workspace(query: ScaffoldQuery) -> Result<ScaffoldWorkspace, ScaffoldError> {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        if query.org.is_none() && query.repo.is_none() && query.day.is_none() {
            return store.latest_workspace();
        }
        let plan_id = query.plan_id.clone();
        let (org, repo, day) = resolve_query(&query, &store);
        store.workspace(&org, &repo, &day, plan_id.as_deref())
    }

    fn resolve_query(
        query: &ScaffoldQuery,
        store: &ScaffoldArtifactStore,
    ) -> (String, String, String) {
        let fallback = store.latest_workspace().ok();
        let org = query
            .org
            .clone()
            .or_else(|| fallback.as_ref().map(|workspace| workspace.org.clone()))
            .unwrap_or_else(|| "Vetcoders".to_string());
        let repo = query
            .repo
            .clone()
            .or_else(|| fallback.as_ref().map(|workspace| workspace.repo.clone()))
            .unwrap_or_else(|| "vibecrafted".to_string());
        let day = query
            .day
            .clone()
            .or_else(|| fallback.as_ref().map(|workspace| workspace.day.clone()))
            .unwrap_or_else(|| "2026_0606".to_string());
        (org, repo, day)
    }

    fn explicit_day(query: &ScaffoldQuery) -> Option<(&str, &str, &str)> {
        Some((
            query.org.as_deref()?,
            query.repo.as_deref()?,
            query.day.as_deref()?,
        ))
    }

    fn matching_plans(
        store: &ScaffoldArtifactStore,
        query: &ScaffoldQuery,
        plan_ids: &[String],
    ) -> Vec<ScaffoldPlanSummary> {
        store
            .catalog()
            .into_iter()
            .filter(|plan| plan_ids.contains(&plan.plan_id))
            .filter(|plan| {
                query.org.as_ref().is_none_or(|org| &plan.org == org)
                    && query.repo.as_ref().is_none_or(|repo| &plan.repo == repo)
                    && query.day.as_ref().is_none_or(|day| &plan.day == day)
            })
            .collect()
    }

    fn selected_plan(
        store: &ScaffoldArtifactStore,
        query: &ScaffoldQuery,
    ) -> Option<ScaffoldPlanSummary> {
        let org = query.org.as_deref()?;
        let repo = query.repo.as_deref()?;
        let day = query.day.as_deref()?;
        let plan_id = query.plan_id.as_deref()?;
        store.catalog().into_iter().find(|plan| {
            plan.org == org && plan.repo == repo && plan.day == day && plan.plan_id == plan_id
        })
    }

    fn plan_card_views(
        store: &ScaffoldArtifactStore,
        plans: Vec<ScaffoldPlanSummary>,
    ) -> Vec<ScaffoldPlanCard> {
        plans
            .into_iter()
            .map(|plan| ScaffoldPlanCard {
                reviewable: store.is_plan_reviewable(
                    &plan.org,
                    &plan.repo,
                    &plan.day,
                    &plan.plan_id,
                ),
                plan,
            })
            .collect()
    }

    fn scaffold_error_response(error: ScaffoldError) -> Response {
        let status = match error {
            ScaffoldError::Conflict { .. } => StatusCode::CONFLICT,
            ScaffoldError::SelectionRequired { .. } => StatusCode::MULTIPLE_CHOICES,
            ScaffoldError::ArtifactNotFound { .. } => StatusCode::NOT_FOUND,
            ScaffoldError::ReadOnly { .. }
            | ScaffoldError::UnsafePath { .. }
            | ScaffoldError::InvalidManifest { .. } => StatusCode::BAD_REQUEST,
            ScaffoldError::Io(_) | ScaffoldError::Json(_) => StatusCode::INTERNAL_SERVER_ERROR,
        };
        (
            status,
            Json(serde_json::json!({"error": error.to_string()})),
        )
            .into_response()
    }

    fn render_editor(workspace: &ScaffoldWorkspace) -> String {
        let tabs = workspace
            .artifacts
            .iter()
            .map(render_tab)
            .collect::<Vec<_>>()
            .join("");
        let panels = workspace
            .artifacts
            .iter()
            .map(|artifact| render_panel(workspace, artifact))
            .collect::<Vec<_>>()
            .join("");
        let approved = workspace
            .artifacts
            .iter()
            .filter(|artifact| artifact.checkpoint.approved)
            .count();
        let total = workspace.artifacts.len();
        format!(
            r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scaffold review</title>
<style>{}</style>
</head>
<body>
<main class="review-shell">
  <nav class="review-sidebar" aria-label="Scaffold artifacts">
    <div class="brand">vibecrafted server</div>
    <div class="summary">
      <strong>{}</strong>
      <span>{} / {} checkpointed</span>
      <span>{}</span>
    </div>
    <div class="tabs">{}</div>
    <a class="api-link" href="/api/scaffold/artifacts?org={}&repo={}&day={}&plan_id={}">artifact endpoint</a>
    <a class="api-link" href="/api/scaffold/changes?org={}&repo={}&day={}&plan_id={}">change endpoint</a>
  </nav>
  <section class="review-main">
    <div id="status-saved" class="status">Saved. Agent endpoint is current.</div>
    <div id="status-error" class="status status-error">Save failed. Check server logs.</div>
    {}
  </section>
</main>
{}
</body>
</html>"#,
            editor_css(),
            escape_html(&workspace.repo),
            approved,
            total,
            escape_html(&workspace.day),
            tabs,
            url_component(&workspace.org),
            url_component(&workspace.repo),
            url_component(&workspace.day),
            url_component(&workspace.plan_id),
            url_component(&workspace.org),
            url_component(&workspace.repo),
            url_component(&workspace.day),
            url_component(&workspace.plan_id),
            panels,
            save_on_close_guard()
        )
    }

    fn render_plan_picker(plans: &[ScaffoldPlanCard]) -> String {
        if plans.is_empty() {
            return render_empty("No manifest-backed scaffold plans are available.");
        }
        let repositories = plans
            .iter()
            .map(|card| format!("{}/{}", card.plan.org, card.plan.repo))
            .collect::<BTreeSet<_>>()
            .len();
        let artifact_count = plans
            .iter()
            .map(|card| card.plan.artifact_count)
            .sum::<usize>();
        let reviewable_count = plans.iter().filter(|card| card.reviewable).count();
        let cards = plans
            .iter()
            .enumerate()
            .map(|(index, card)| plan_picker_card(index, card))
            .collect::<Vec<_>>()
            .join("");
        format!(
            r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scaffold plans</title>
<style>{}</style>
</head>
<body>
<main class="plan-library">
  <header class="library-header">
    <nav class="library-nav" aria-label="Scaffold navigation">
      <a class="brand" href="/">vibecrafted server</a>
      <span class="library-mode">scaffold library</span>
    </nav>
    <div class="library-intro">
      <div>
        <p class="eyebrow">Plan control room</p>
        <h1>Choose the truth<br>you want to move.</h1>
      </div>
      <p class="library-lede">Every manifest-backed scaffold package available to this runtime. Search the field, open a plan, then edit and checkpoint its actual artifacts.</p>
    </div>
    <dl class="library-stats">
      <div><dt>plans</dt><dd>{}</dd></div>
      <div><dt>repositories</dt><dd>{}</dd></div>
      <div><dt>reviewable</dt><dd>{}</dd></div>
      <div><dt>artifacts</dt><dd>{}</dd></div>
    </dl>
  </header>

  <section class="plan-field" aria-labelledby="plan-field-title">
    <div class="plan-toolbar">
      <div>
        <p class="eyebrow">Manifest index</p>
        <h2 id="plan-field-title">Scaffold plans</h2>
      </div>
      <label class="plan-search">
        <span>Find a plan</span>
        <input id="plan-search" type="search" placeholder="repo, date, plan…" autocomplete="off">
        <kbd>/</kbd>
      </label>
    </div>
    <p class="result-count" aria-live="polite"><span id="visible-count">{}</span> plans visible</p>
    <div class="plan-grid" id="plan-grid">{}</div>
    <div class="plan-no-results" id="plan-no-results" hidden>
      <p class="eyebrow">No match</p>
      <strong>Nothing in the manifest index answers that search.</strong>
      <button type="button" id="clear-search">Clear search</button>
    </div>
  </section>
</main>
{}
</body>
</html>"#,
            editor_css(),
            plans.len(),
            repositories,
            reviewable_count,
            artifact_count,
            plans.len(),
            cards,
            plan_picker_script(),
        )
    }

    fn plan_picker_card(index: usize, card: &ScaffoldPlanCard) -> String {
        let plan = &card.plan;
        let href = format!(
            "/scaffold/editor?org={}&repo={}&day={}&plan_id={}",
            url_component(&plan.org),
            url_component(&plan.repo),
            url_component(&plan.day),
            url_component(&plan.plan_id),
        );
        let search = format!("{} {} {} {}", plan.org, plan.repo, plan.day, plan.plan_id);
        let (state_class, access) = if !card.reviewable {
            (" plan-card-blocked", "blocked")
        } else if plan.legacy_read_only {
            ("", "read only")
        } else {
            ("", "open")
        };
        format!(
            r#"<a class="plan-card{}" href="{}" data-search="{}">
  <div class="plan-card-top">
    <span class="plan-number">{:02}</span>
    <span class="plan-access">{}</span>
  </div>
  <div class="plan-card-title">
    <p>{} / {}</p>
    <h3>{}</h3>
  </div>
  <dl class="plan-card-meta">
    <div><dt>day</dt><dd>{}</dd></div>
    <div><dt>artifacts</dt><dd>{}</dd></div>
  </dl>
  <span class="plan-open">Open plan <b aria-hidden="true">↗</b></span>
</a>"#,
            state_class,
            escape_attr(&href),
            escape_attr(&search.to_ascii_lowercase()),
            index + 1,
            access,
            escape_html(&plan.org),
            escape_html(&plan.repo),
            escape_html(&humanize_plan_id(&plan.plan_id)),
            escape_html(&plan.day.replace('_', " · ")),
            plan.artifact_count,
        )
    }

    fn render_plan_blocked(
        plan: &ScaffoldPlanSummary,
        report: Option<&ScaffoldDoctorReport>,
        error: &str,
    ) -> String {
        let issues = report
            .map(|report| {
                report
                    .errors
                    .iter()
                    .map(|issue| {
                        let rule = issue
                            .rule
                            .as_deref()
                            .map(|rule| format!(" · {rule}"))
                            .unwrap_or_default();
                        let path = issue
                            .path
                            .as_deref()
                            .map(|path| format!("<code>{}</code>", escape_html(path)))
                            .unwrap_or_else(|| "<code>plan contract</code>".to_string());
                        format!(
                            r#"<li><div><span>{}{}</span>{}</div><p>{}</p></li>"#,
                            escape_html(&issue.code),
                            rule,
                            path,
                            escape_html(&issue.message),
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("")
            })
            .filter(|issues| !issues.is_empty())
            .unwrap_or_else(|| {
                format!(
                    "<li><div><span>runtime refusal</span><code>workspace</code></div><p>{}</p></li>",
                    escape_html(error)
                )
            });
        let issue_count = report.map_or(1, |report| report.errors.len().max(1));
        format!(
            r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scaffold plan blocked</title>
<style>{}</style>
</head>
<body>
<main class="blocked-plan-shell">
  <nav class="library-nav">
    <a class="brand" href="/">vibecrafted server</a>
    <a class="back-link" href="/scaffold/editor">← scaffold library</a>
  </nav>
  <header class="blocked-plan-head">
    <div>
      <p class="eyebrow">{}/{}</p>
      <h1>{}</h1>
    </div>
    <span class="blocked-pill">{} contract issues</span>
  </header>
  <div class="blocked-plan-grid">
    <section class="blocked-explainer">
      <p class="eyebrow">Runtime truth</p>
      <h2>The plan exists.<br>The editor refuses to lie.</h2>
      <p>The manifest is indexed, but its current artifact contract cannot be opened safely. Repair these findings and the same card will become reviewable automatically.</p>
      <dl>
        <div><dt>day</dt><dd>{}</dd></div>
        <div><dt>artifacts</dt><dd>{}</dd></div>
        <div><dt>root</dt><dd>{}</dd></div>
      </dl>
    </section>
    <section class="blocked-findings">
      <div class="blocked-findings-head">
        <p class="eyebrow">Scaffold doctor</p>
        <strong>{} findings</strong>
      </div>
      <ol>{}</ol>
    </section>
  </div>
</main>
</body>
</html>"#,
            editor_css(),
            escape_html(&plan.org),
            escape_html(&plan.repo),
            escape_html(&humanize_plan_id(&plan.plan_id)),
            issue_count,
            escape_html(&plan.day.replace('_', " · ")),
            plan.artifact_count,
            escape_html(&plan.plan_root),
            issue_count,
            issues,
        )
    }

    fn humanize_plan_id(plan_id: &str) -> String {
        plan_id
            .split(['-', '_'])
            .filter(|part| !part.is_empty())
            .map(|part| {
                let mut chars = part.chars();
                match chars.next() {
                    Some(first) => format!("{}{}", first.to_uppercase(), chars.as_str()),
                    None => String::new(),
                }
            })
            .collect::<Vec<_>>()
            .join(" ")
    }

    fn plan_picker_script() -> &'static str {
        r#"<script>
(function () {
  var search = document.getElementById("plan-search");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".plan-card"));
  var count = document.getElementById("visible-count");
  var empty = document.getElementById("plan-no-results");
  var clear = document.getElementById("clear-search");

  function normalize(value) {
    return value
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  function filterPlans() {
    var needle = normalize(search.value);
    var visible = 0;
    cards.forEach(function (card) {
      var match = !needle || normalize(card.dataset.search).indexOf(needle) !== -1;
      card.hidden = !match;
      if (match) visible += 1;
    });
    count.textContent = String(visible);
    empty.hidden = visible !== 0;
  }

  search.addEventListener("input", filterPlans);
  clear.addEventListener("click", function () {
    search.value = "";
    filterPlans();
    search.focus();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "/" && document.activeElement !== search) {
      event.preventDefault();
      search.focus();
    } else if (event.key === "Escape" && document.activeElement === search) {
      search.value = "";
      filterPlans();
      search.blur();
    }
  });
})();
</script>"#
    }

    fn render_empty(message: &str) -> String {
        format!(
            r#"<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Scaffold review unavailable</title><style>{}</style></head>
<body><main class="empty"><h1>Scaffold review</h1><p>{}</p></main></body>
</html>"#,
            editor_css(),
            escape_html(message)
        )
    }

    fn render_tab(artifact: &ScaffoldArtifact) -> String {
        let checkpoint = if artifact.checkpoint.approved {
            "done"
        } else {
            "open"
        };
        format!(
            r##"<a class="tab tab-{}" href="#{}"><span>{}</span><small>{}</small></a>"##,
            checkpoint,
            escape_attr(&artifact.id),
            escape_html(&artifact.title),
            artifact.role.as_str()
        )
    }

    fn render_panel(workspace: &ScaffoldWorkspace, artifact: &ScaffoldArtifact) -> String {
        let checked = if artifact.checkpoint.approved {
            " checked"
        } else {
            ""
        };
        let status = if artifact.checkpoint.approved {
            "checkpointed"
        } else {
            "needs checkpoint"
        };
        format!(
            r#"<article class="artifact-panel" id="{}">
  <header class="artifact-head">
    <div>
      <p class="eyebrow">{}</p>
      <h2>{}</h2>
      <p class="path">{}</p>
    </div>
    <span class="checkpoint-state">{}</span>
  </header>
  <form method="post" action="/api/scaffold/artifact" class="editor-form">
    {}
    <textarea name="content" spellcheck="false">{}</textarea>
    <button type="submit">Save artifact</button>
  </form>
  <form method="post" action="/api/scaffold/checkpoint" class="checkpoint-form">
    {}
    <label><input type="checkbox" name="approved" value="1"{}> Approved checkpoint</label>
    <input name="note" value="{}" placeholder="checkpoint note">
    <button type="submit">Update checkpoint</button>
  </form>
</article>"#,
            escape_attr(&artifact.id),
            artifact.role.as_str(),
            escape_html(&artifact.title),
            escape_html(&artifact.relative_path),
            status,
            hidden_context(workspace, artifact),
            escape_html(&artifact.content),
            hidden_context(workspace, artifact),
            checked,
            escape_attr(&artifact.checkpoint.note)
        )
    }

    /// App-wide save-on-close guard for the editable artifact panels.
    ///
    /// The editor persisted only on an explicit "Save artifact" click, so
    /// closing the window/tab (Cmd-W), or the SPA tearing the editor iframe
    /// down on navigation, silently dropped any Markdown typed in the moments
    /// before the click. This guard tracks dirty state per `editor-form` and
    /// flushes every dirty buffer to the existing `POST /api/scaffold/artifact`
    /// endpoint via `navigator.sendBeacon` on `pagehide` (iframe teardown / tab
    /// close) and `beforeunload` (Cmd-W). It introduces no new persistence
    /// path: it re-uses each form's own `action`, never the checkpoint form,
    /// and only warns natively when a beacon flush is impossible.
    fn save_on_close_guard() -> &'static str {
        r#"<script>
(function () {
  var forms = Array.prototype.slice.call(
    document.querySelectorAll("form.editor-form")
  );
  forms.forEach(function (form) {
    var ta = form.querySelector("textarea[name=content]");
    if (!ta) return;
    form.dataset.baseline = ta.value;
    ta.addEventListener("input", function () {
      form.dataset.dirty = ta.value !== form.dataset.baseline ? "1" : "";
    });
    form.addEventListener("submit", function () {
      form.dataset.baseline = ta.value;
      form.dataset.dirty = "";
    });
  });

  function flush() {
    if (!navigator.sendBeacon) return;
    forms.forEach(function (form) {
      if (form.dataset.dirty !== "1") return;
      var ta = form.querySelector("textarea[name=content]");
      try {
        var body = new URLSearchParams(new FormData(form));
        // sendBeacon serializes a URLSearchParams body as text/plain, which the
        // axum `Form` extractor rejects with 415 (the edit is silently lost).
        // Send an explicitly typed blob so the content type round-trips.
        var payload = new Blob([body.toString()], {
          type: "application/x-www-form-urlencoded",
        });
        if (navigator.sendBeacon(form.getAttribute("action"), payload)) {
          form.dataset.dirty = "";
          if (ta) form.dataset.baseline = ta.value;
        }
      } catch (e) {}
    });
  }

  function anyDirty() {
    return forms.some(function (form) {
      return form.dataset.dirty === "1";
    });
  }

  window.addEventListener("pagehide", flush);
  window.addEventListener("beforeunload", function (ev) {
    flush();
    if (anyDirty()) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });
})();
</script>"#
    }

    fn hidden_context(workspace: &ScaffoldWorkspace, artifact: &ScaffoldArtifact) -> String {
        format!(
            r#"<input type="hidden" name="org" value="{}">
<input type="hidden" name="repo" value="{}">
<input type="hidden" name="day" value="{}">
<input type="hidden" name="plan_id" value="{}">
<input type="hidden" name="artifact_id" value="{}">
<input type="hidden" name="expected_hash" value="{}">"#,
            escape_attr(&workspace.org),
            escape_attr(&workspace.repo),
            escape_attr(&workspace.day),
            escape_attr(&workspace.plan_id),
            escape_attr(&artifact.id),
            escape_attr(&artifact.content_hash),
        )
    }

    fn editor_css() -> &'static str {
        r#"
:root{color-scheme:dark;--bg:#0d0f10;--panel:#151819;--panel-lift:#1b1f20;--line:#2b3033;--text:#f3eee7;--muted:#a9b1b4;--accent:#b8ef7d;--teal:#4d9b8e;--amber:#d8a640;--warn:#ffd166;--bad:#ff8a8a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,sans-serif}
a{color:inherit}
.plan-library{min-height:100vh;background:radial-gradient(circle at 83% 7%,rgba(77,155,142,.13),transparent 31rem),var(--bg)}
.library-header{padding:26px clamp(24px,5vw,76px) 54px;border-bottom:1px solid var(--line)}
.library-nav{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:clamp(64px,9vw,130px)}
.library-nav .brand{text-decoration:none}.library-mode{color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.14em}
.library-intro{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:clamp(28px,6vw,90px);align-items:end}
.library-intro h1{max-width:850px;margin:12px 0 0;font:400 clamp(48px,7vw,102px)/.89 Georgia,'Times New Roman',serif;letter-spacing:-.055em}
.library-lede{max-width:540px;margin:0 0 8px;color:var(--muted);font-size:clamp(15px,1.5vw,19px);line-height:1.55}
.library-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));max-width:780px;margin:54px 0 0;border-top:1px solid var(--line)}
.library-stats div{padding:14px 24px 0 0}.library-stats dt,.plan-card-meta dt{color:var(--muted);font:10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.12em}
.library-stats dd{margin:2px 0 0;color:var(--amber);font:28px ui-monospace,SFMono-Regular,Menlo,monospace}
.plan-field{padding:42px clamp(24px,5vw,76px) 80px}
.plan-toolbar{display:flex;align-items:end;justify-content:space-between;gap:30px}.plan-toolbar h2{margin:5px 0 0;font:400 34px/1.05 Georgia,'Times New Roman',serif}
.plan-search{position:relative;display:grid;gap:7px;width:min(100%,390px);color:var(--muted);font:10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.12em}
.plan-search input{width:100%;border:0;border-bottom:1px solid var(--line);outline:0;background:transparent;color:var(--text);padding:8px 34px 10px 0;font:15px Inter,ui-sans-serif,system-ui,sans-serif;text-transform:none;letter-spacing:0}
.plan-search input:focus{border-color:var(--teal)}.plan-search kbd{position:absolute;right:0;bottom:10px;border:1px solid var(--line);border-radius:4px;padding:1px 6px;color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}
.result-count{margin:32px 0 14px;color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.1em}
.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:12px}
.plan-card{min-height:290px;display:flex;flex-direction:column;justify-content:space-between;gap:28px;padding:22px;border:1px solid var(--line);border-radius:9px;background:linear-gradient(145deg,var(--panel),#111415);text-decoration:none;transition:transform .18s ease,border-color .18s ease,background .18s ease}
.plan-card:hover,.plan-card:focus-visible{transform:translateY(-3px);border-color:var(--teal);background:var(--panel-lift);outline:none}
.plan-card-blocked{border-color:rgba(255,138,138,.28);background:linear-gradient(145deg,#1b1617,#111415)}.plan-card-blocked .plan-access{border-color:rgba(255,138,138,.35);color:var(--bad)}
.plan-card[hidden]{display:none}.plan-card-top,.plan-card-meta,.plan-open{display:flex;align-items:center;justify-content:space-between;gap:16px}
.plan-number{color:var(--amber);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.plan-access{border:1px solid var(--line);border-radius:99px;padding:4px 8px;color:var(--muted);font:9px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.1em}
.plan-card-title p{margin:0 0 9px;color:var(--teal);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}.plan-card-title h3{max-width:470px;margin:0;font:400 28px/1.03 Georgia,'Times New Roman',serif;letter-spacing:-.025em}
.plan-card-meta{margin:0;padding-top:14px;border-top:1px solid var(--line)}.plan-card-meta div{display:grid;gap:3px}.plan-card-meta div:last-child{text-align:right}.plan-card-meta dd{margin:0;color:var(--text);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
.plan-open{color:var(--muted);font-weight:700}.plan-open b{color:var(--accent);font-size:18px}.plan-card:hover .plan-open{color:var(--text)}
.plan-no-results{margin-top:12px;border:1px dashed var(--line);border-radius:9px;padding:50px 24px;text-align:center;color:var(--muted)}.plan-no-results strong{display:block;color:var(--text);font:400 24px Georgia,'Times New Roman',serif}.plan-no-results button{justify-self:auto;margin:20px 0 0}
.blocked-plan-shell{min-height:100vh;padding:26px clamp(24px,5vw,76px) 80px;background:radial-gradient(circle at 85% 5%,rgba(255,138,138,.08),transparent 32rem),var(--bg)}.blocked-plan-shell .library-nav{margin-bottom:clamp(60px,8vw,110px)}.back-link{color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;text-decoration:none;text-transform:uppercase;letter-spacing:.12em}.back-link:hover{color:var(--text)}
.blocked-plan-head{display:flex;align-items:end;justify-content:space-between;gap:30px;padding-bottom:36px;border-bottom:1px solid var(--line)}.blocked-plan-head h1{max-width:900px;margin:10px 0 0;font:400 clamp(44px,6.5vw,88px)/.92 Georgia,'Times New Roman',serif;letter-spacing:-.045em}.blocked-pill{flex:0 0 auto;border:1px solid rgba(255,138,138,.35);border-radius:99px;padding:7px 11px;color:var(--bad);font:10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.1em}
.blocked-plan-grid{display:grid;grid-template-columns:minmax(280px,.72fr) minmax(0,1.28fr);gap:clamp(36px,7vw,110px);padding-top:42px}.blocked-explainer h2{margin:8px 0 18px;font:400 clamp(31px,4vw,52px)/.98 Georgia,'Times New Roman',serif}.blocked-explainer>p:not(.eyebrow){max-width:520px;color:var(--muted);font-size:16px;line-height:1.6}.blocked-explainer dl{display:grid;gap:12px;margin:36px 0 0}.blocked-explainer dl div{display:grid;grid-template-columns:80px 1fr;gap:16px;padding-top:10px;border-top:1px solid var(--line)}.blocked-explainer dt{color:var(--muted);font:10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.blocked-explainer dd{min-width:0;margin:0;overflow-wrap:anywhere;font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
.blocked-findings{border:1px solid var(--line);border-radius:9px;background:var(--panel);overflow:hidden}.blocked-findings-head{display:flex;align-items:end;justify-content:space-between;gap:20px;padding:18px 20px;border-bottom:1px solid var(--line)}.blocked-findings-head p{margin:0}.blocked-findings-head strong{color:var(--bad);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}.blocked-findings ol{max-height:68vh;margin:0;padding:0;overflow:auto;list-style:none}.blocked-findings li{padding:17px 20px;border-bottom:1px solid var(--line)}.blocked-findings li:last-child{border:0}.blocked-findings li div{display:flex;justify-content:space-between;gap:14px}.blocked-findings li span{color:var(--bad);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.blocked-findings li code{color:var(--teal);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}.blocked-findings li p{margin:8px 0 0;color:var(--muted);line-height:1.5}
.review-shell{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}
.review-sidebar{border-right:1px solid var(--line);padding:18px 14px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:14px;background:#101314}
.brand{font:700 12px/1.1 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--accent)}
.summary{display:grid;gap:3px;color:var(--muted)}.summary strong{color:var(--text);font-size:16px}
.tabs{display:flex;flex-direction:column;gap:6px;overflow:auto;padding-right:4px}
.tab{display:grid;gap:2px;text-decoration:none;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:9px 10px;background:#171b1d}
.tab:hover,.tab:focus{border-color:var(--accent);outline:none}.tab small{color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}.tab-done{border-color:#4d7041}
.api-link{color:var(--accent);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;text-decoration:none}
.review-main{padding:22px;display:grid;gap:18px}.status{display:none;border:1px solid #4d7041;background:#162114;padding:10px;border-radius:8px}.status:target{display:block}.status-error{border-color:var(--bad);background:#2b1717}
.artifact-panel{border:1px solid var(--line);border-radius:8px;background:var(--panel);overflow:hidden;min-height:78vh;display:grid;grid-template-rows:auto minmax(420px,1fr) auto}
.artifact-head{display:flex;justify-content:space-between;gap:16px;padding:16px;border-bottom:1px solid var(--line)}.artifact-head h2{margin:3px 0 0;font-size:22px;letter-spacing:0}
.eyebrow,.path{margin:0;color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.checkpoint-state{align-self:start;border:1px solid var(--line);border-radius:999px;padding:5px 9px;color:var(--warn);font-size:12px}
.editor-form{display:grid;grid-template-rows:1fr auto;min-height:520px}.editor-form textarea{width:100%;min-height:520px;resize:vertical;border:0;border-bottom:1px solid var(--line);background:#0f1213;color:var(--text);padding:16px;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
button{justify-self:start;margin:12px 16px;border:1px solid #5e7f47;background:#22321f;color:var(--text);border-radius:7px;padding:8px 12px;font-weight:700;cursor:pointer}
.checkpoint-form{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:0 0 14px}.checkpoint-form input[name=note]{min-width:280px;flex:1;border:1px solid var(--line);background:#0f1213;color:var(--text);border-radius:7px;padding:8px}
.empty{max-width:720px;margin:12vh auto;border:1px solid var(--line);border-radius:8px;padding:24px;background:var(--panel)}
@media(max-width:820px){.library-intro,.blocked-plan-grid{grid-template-columns:1fr}.library-nav{margin-bottom:64px}.library-stats{max-width:none}.plan-toolbar{align-items:stretch;flex-direction:column}.plan-search{width:100%}.blocked-plan-head{align-items:start;flex-direction:column}.review-shell{grid-template-columns:1fr}.review-sidebar{position:relative;height:auto}.artifact-panel{min-height:auto}}
@media(max-width:520px){.library-header,.plan-field{padding-left:18px;padding-right:18px}.library-intro h1{font-size:48px}.library-stats dd{font-size:22px}.plan-grid{grid-template-columns:1fr}}
"#
    }

    fn escape_html(value: &str) -> String {
        value
            .replace('&', "&amp;")
            .replace('<', "&lt;")
            .replace('>', "&gt;")
    }

    fn escape_attr(value: &str) -> String {
        escape_html(value).replace('"', "&quot;")
    }

    fn url_component(value: &str) -> String {
        value
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.') {
                    c
                } else {
                    '-'
                }
            })
            .collect()
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use control_core::{
            ScaffoldArtifact, ScaffoldArtifactRole, ScaffoldCheckpoint, ScaffoldPlanSummary,
            ScaffoldWorkspace,
        };

        fn fixture() -> ScaffoldWorkspace {
            ScaffoldWorkspace {
                org: "Vetcoders".into(),
                repo: "vibecrafted".into(),
                day: "2026_0615".into(),
                plan_id: "plan-a".into(),
                plan_root: "/tmp/plan-a".into(),
                legacy_read_only: false,
                changes_path: "/tmp/op/.scaffold-changes.jsonl".into(),
                checkpoints_path: "/tmp/op/.scaffold-checkpoints.json".into(),
                artifacts: vec![ScaffoldArtifact {
                    id: "master-dispatch".into(),
                    title: "Master Dispatch".into(),
                    role: ScaffoldArtifactRole::WaveAtlas,
                    path: "/tmp/op/master-dispatch.md".into(),
                    relative_path: "operator/master-dispatch.md".into(),
                    editable: true,
                    required: true,
                    content: "# atlas".into(),
                    content_hash: "sha256:test".into(),
                    bytes: 7,
                    modified_at: "2026-06-15T00:00:00Z".into(),
                    checkpoint: ScaffoldCheckpoint::default(),
                }],
            }
        }

        #[test]
        fn editor_embeds_save_on_close_guard() {
            let html = render_editor(&fixture());
            // Flush on teardown, not just on the explicit Save click.
            assert!(
                html.contains("navigator.sendBeacon"),
                "editor must flush unsaved edits via sendBeacon on close"
            );
            // pagehide covers iframe teardown on SPA nav + tab close.
            assert!(
                html.contains("\"pagehide\""),
                "missing pagehide handler (sidebar/SPA teardown + tab close)"
            );
            // beforeunload covers Cmd-W / window close.
            assert!(
                html.contains("\"beforeunload\""),
                "missing beforeunload handler (Cmd-W / window close)"
            );
            // Dirty tracking is scoped to the editable artifact panels.
            assert!(
                html.contains("form.editor-form"),
                "guard must target the editable artifact panels"
            );
        }

        #[test]
        fn guard_reuses_typed_endpoint_and_skips_checkpoints() {
            let guard = save_on_close_guard();
            // No parallel persistence path: the guard posts to each form's own
            // action (the typed /api/scaffold/artifact endpoint), nothing new.
            assert!(
                guard.contains("form.getAttribute(\"action\")"),
                "guard must reuse the form's own typed save endpoint"
            );
            assert!(
                !guard.contains("checkpoint"),
                "checkpoint approval is a deliberate action and must not auto-flush"
            );
        }

        #[test]
        fn conflict_maps_to_http_409_and_editor_carries_revision() {
            let response = scaffold_error_response(ScaffoldError::Conflict {
                expected: "sha256:old".into(),
                actual: "sha256:new".into(),
            });
            assert_eq!(response.status(), StatusCode::CONFLICT);
            let html = render_editor(&fixture());
            assert!(html.contains("name=\"plan_id\" value=\"plan-a\""));
            assert!(html.contains("name=\"expected_hash\" value=\"sha256:test\""));
        }

        #[test]
        fn form_mutation_error_redirects_back_to_editor_status() {
            let response = redirect_after_mutation(
                "Vetcoders",
                "vibecrafted",
                "2026_0615",
                "plan-a",
                Some(ScaffoldError::Conflict {
                    expected: "sha256:old".into(),
                    actual: "sha256:new".into(),
                }),
            );

            assert_eq!(response.status(), StatusCode::SEE_OTHER);
            assert_eq!(
                response.headers().get(header::LOCATION).unwrap(),
                "/scaffold/editor?org=Vetcoders&repo=vibecrafted&day=2026_0615&plan_id=plan-a#status-error"
            );
        }

        #[test]
        fn selection_renders_searchable_plan_library_with_typed_editor_links() {
            let html = render_plan_picker(&[ScaffoldPlanCard {
                plan: ScaffoldPlanSummary {
                    plan_id: "runtime-truth-v1".into(),
                    org: "vetcoders".into(),
                    repo: "vibecrafted".into(),
                    day: "2026_0727".into(),
                    plan_root: "/tmp/runtime-truth-v1".into(),
                    artifact_count: 12,
                    legacy_read_only: false,
                },
                reviewable: true,
            }]);

            assert!(html.contains("Choose the truth"));
            assert!(html.contains("id=\"plan-search\""));
            assert!(html.contains(".normalize(\"NFD\")"));
            assert!(html.contains(
                "/scaffold/editor?org=vetcoders&amp;repo=vibecrafted&amp;day=2026_0727&amp;plan_id=runtime-truth-v1"
            ));
            assert!(!html.contains("scaffold plan selection required"));
        }

        #[test]
        fn blocked_plan_renders_doctor_truth_instead_of_dead_error_card() {
            let plan = ScaffoldPlanSummary {
                plan_id: "broken-plan".into(),
                org: "vetcoders".into(),
                repo: "vibecrafted".into(),
                day: "2026_0727".into(),
                plan_root: "/tmp/broken-plan".into(),
                artifact_count: 2,
                legacy_read_only: false,
            };
            let report = ScaffoldDoctorReport {
                valid: false,
                plan_id: plan.plan_id.clone(),
                plan_root: plan.plan_root.clone(),
                artifact_ids: vec!["driver".into()],
                errors: vec![control_core::ScaffoldDoctorError {
                    code: "frontmatter_missing".into(),
                    rule: Some("R11".into()),
                    artifact_id: Some("driver".into()),
                    path: Some("DRIVER.md".into()),
                    message: "frontmatter is required".into(),
                }],
            };
            let html = render_plan_blocked(&plan, Some(&report), "invalid manifest");

            assert!(html.contains("The plan exists."));
            assert!(html.contains("frontmatter_missing · R11"));
            assert!(html.contains("DRIVER.md"));
            assert!(html.contains("frontmatter is required"));
        }
    }
}
