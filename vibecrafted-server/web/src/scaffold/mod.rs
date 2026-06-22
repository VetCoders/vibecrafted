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
    use axum::extract::{Form, Query};
    use axum::http::{StatusCode, header};
    use axum::response::{Html, IntoResponse, Response};
    use axum::routing::{get, post};
    use axum::{Json, Router};
    use control_core::{
        ScaffoldArtifact, ScaffoldArtifactPatch, ScaffoldArtifactStore, ScaffoldCheckpointPatch,
        ScaffoldWorkspace, vibecrafted_home,
    };
    use serde::Deserialize;

    #[derive(Debug, Clone, Deserialize)]
    pub struct ScaffoldQuery {
        org: Option<String>,
        repo: Option<String>,
        day: Option<String>,
    }

    #[derive(Debug, Clone, Deserialize)]
    pub struct SaveArtifactForm {
        org: String,
        repo: String,
        day: String,
        artifact_id: String,
        content: String,
    }

    #[derive(Debug, Clone, Deserialize)]
    pub struct CheckpointForm {
        org: String,
        repo: String,
        day: String,
        artifact_id: String,
        #[serde(default)]
        approved: Option<String>,
        #[serde(default)]
        note: String,
    }

    pub fn scaffold_routes() -> Router<leptos::config::LeptosOptions> {
        Router::<leptos::config::LeptosOptions>::new()
            .route("/scaffold/editor", get(editor))
            .route("/api/scaffold/artifacts", get(artifacts))
            .route("/api/scaffold/changes", get(changes))
            .route("/api/scaffold/artifact", post(save_artifact))
            .route("/api/scaffold/checkpoint", post(save_checkpoint))
    }

    async fn editor(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        match load_workspace(query) {
            Ok(workspace) => Html(render_editor(&workspace)).into_response(),
            Err(error) => (
                StatusCode::NOT_FOUND,
                Html(render_empty(&format!(
                    "Scaffold artifacts unavailable: {error}"
                ))),
            )
                .into_response(),
        }
    }

    async fn artifacts(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        match load_workspace(query) {
            Ok(workspace) => Json(workspace).into_response(),
            Err(error) => (
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({ "error": error.to_string() })),
            )
                .into_response(),
        }
    }

    async fn changes(Query(query): Query<ScaffoldQuery>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let (org, repo, day) = resolve_query(query, &store);
        match store.changes(&org, &repo, &day) {
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
            ScaffoldArtifactPatch {
                artifact_id: form.artifact_id,
                content: form.content,
            },
        );
        redirect_after_mutation(&form.org, &form.repo, &form.day, result.err())
    }

    async fn save_checkpoint(Form(form): Form<CheckpointForm>) -> impl IntoResponse {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        let result = store.checkpoint(
            &form.org,
            &form.repo,
            &form.day,
            ScaffoldCheckpointPatch {
                artifact_id: form.artifact_id,
                approved: form.approved.is_some(),
                note: form.note,
            },
        );
        redirect_after_mutation(&form.org, &form.repo, &form.day, result.err())
    }

    fn redirect_after_mutation(
        org: &str,
        repo: &str,
        day: &str,
        error: Option<std::io::Error>,
    ) -> Response {
        let status = if error.is_some() { "error" } else { "saved" };
        let location = format!(
            "/scaffold/editor?org={}&repo={}&day={}#status-{status}",
            url_component(org),
            url_component(repo),
            url_component(day)
        );
        (StatusCode::SEE_OTHER, [(header::LOCATION, location)]).into_response()
    }

    fn load_workspace(query: ScaffoldQuery) -> std::io::Result<ScaffoldWorkspace> {
        let store = ScaffoldArtifactStore::new(vibecrafted_home());
        if query.org.is_none() && query.repo.is_none() && query.day.is_none() {
            return store.latest_workspace();
        }
        let (org, repo, day) = resolve_query(query, &store);
        store.workspace(&org, &repo, &day)
    }

    fn resolve_query(
        query: ScaffoldQuery,
        store: &ScaffoldArtifactStore,
    ) -> (String, String, String) {
        let fallback = store.latest_workspace().ok();
        let org = query
            .org
            .or_else(|| fallback.as_ref().map(|workspace| workspace.org.clone()))
            .unwrap_or_else(|| "VetCoders".to_string());
        let repo = query
            .repo
            .or_else(|| fallback.as_ref().map(|workspace| workspace.repo.clone()))
            .unwrap_or_else(|| "vibecrafted".to_string());
        let day = query
            .day
            .or_else(|| fallback.as_ref().map(|workspace| workspace.day.clone()))
            .unwrap_or_else(|| "2026_0606".to_string());
        (org, repo, day)
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
    <a class="api-link" href="/api/scaffold/artifacts?org={}&repo={}&day={}">artifact endpoint</a>
    <a class="api-link" href="/api/scaffold/changes?org={}&repo={}&day={}">change endpoint</a>
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
            url_component(&workspace.org),
            url_component(&workspace.repo),
            url_component(&workspace.day),
            panels,
            save_on_close_guard()
        )
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
            artifact.kind.as_str()
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
            artifact.kind.as_str(),
            escape_html(&artifact.title),
            escape_html(&artifact.relative_path),
            status,
            hidden_context(workspace, &artifact.id),
            escape_html(&artifact.content),
            hidden_context(workspace, &artifact.id),
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

    fn hidden_context(workspace: &ScaffoldWorkspace, artifact_id: &str) -> String {
        format!(
            r#"<input type="hidden" name="org" value="{}">
<input type="hidden" name="repo" value="{}">
<input type="hidden" name="day" value="{}">
<input type="hidden" name="artifact_id" value="{}">"#,
            escape_attr(&workspace.org),
            escape_attr(&workspace.repo),
            escape_attr(&workspace.day),
            escape_attr(artifact_id)
        )
    }

    fn editor_css() -> &'static str {
        r#"
:root{color-scheme:dark;--bg:#0d0f10;--panel:#151819;--line:#2b3033;--text:#f3eee7;--muted:#a9b1b4;--accent:#b8ef7d;--warn:#ffd166;--bad:#ff8a8a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,sans-serif}
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
@media(max-width:820px){.review-shell{grid-template-columns:1fr}.review-sidebar{position:relative;height:auto}.artifact-panel{min-height:auto}}
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
            ScaffoldArtifact, ScaffoldArtifactKind, ScaffoldCheckpoint, ScaffoldWorkspace,
        };

        fn fixture() -> ScaffoldWorkspace {
            ScaffoldWorkspace {
                org: "VetCoders".into(),
                repo: "vibecrafted".into(),
                day: "2026_0615".into(),
                operator_dir: "/tmp/op".into(),
                changes_path: "/tmp/op/.scaffold-changes.jsonl".into(),
                checkpoints_path: "/tmp/op/.scaffold-checkpoints.json".into(),
                artifacts: vec![ScaffoldArtifact {
                    id: "master-dispatch".into(),
                    title: "Master Dispatch".into(),
                    kind: ScaffoldArtifactKind::WaveAtlas,
                    path: "/tmp/op/master-dispatch.md".into(),
                    relative_path: "operator/master-dispatch.md".into(),
                    content: "# atlas".into(),
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
    }
}
