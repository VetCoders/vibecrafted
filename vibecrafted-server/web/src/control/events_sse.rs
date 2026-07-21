//! `GET /api/control/events` — Server-Sent Events over the control-plane
//! `events.jsonl` cursor stream.
//!
//! Read-only: the server never writes a resume file or mutates the control
//! plane. The client holds the cursor via SSE `id:` / `Last-Event-ID` /
//! `?since=`. Polling is in-process only (`read_since` on a tick).

use std::collections::VecDeque;
use std::convert::Infallible;
use std::time::Duration;

use axum::extract::Query;
use axum::http::HeaderMap;
use axum::response::sse::{Event as SseEvent, KeepAlive, Sse};
use control_core::{ControlPlane, Event as ControlEvent};
use futures_util::stream::{self, Stream};
use serde::Deserialize;

/// Default poll when the file is quiet (ms). Overridable via
/// `VC_CONTROL_SSE_POLL_MS` (tests use a short interval).
const DEFAULT_POLL_MS: u64 = 500;

/// Default SSE comment keepalive (ms). Spec requires ≤30s; default 15s.
/// Overridable via `VC_CONTROL_SSE_KEEPALIVE_MS`.
const DEFAULT_KEEPALIVE_MS: u64 = 15_000;

#[derive(Debug, Default, Deserialize)]
pub(crate) struct EventsQuery {
    /// Byte-offset cursor into `events.jsonl` (same unit as
    /// [`control_core::EventStream::read_since`]).
    pub since: Option<u64>,
}

struct StreamState {
    cursor: u64,
    pending: VecDeque<ControlEvent>,
}

/// Resolve the start cursor: explicit `?since=` wins over `Last-Event-ID`.
fn resolve_cursor(query: &EventsQuery, headers: &HeaderMap) -> u64 {
    if let Some(since) = query.since {
        return since;
    }
    headers
        .get("last-event-id")
        .or_else(|| headers.get("Last-Event-ID"))
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.trim().parse::<u64>().ok())
        .unwrap_or(0)
}

fn env_ms(name: &str, default: u64) -> u64 {
    std::env::var(name)
        .ok()
        .and_then(|v| v.parse::<u64>().ok())
        .filter(|&n| n > 0)
        .unwrap_or(default)
}

/// JSON payload for `data:` — on-disk shape (no reader-stamped `cursor`).
fn event_data_json(event: &ControlEvent) -> String {
    let mut value = serde_json::to_value(event).unwrap_or_else(|_| serde_json::json!({}));
    if let Some(obj) = value.as_object_mut() {
        obj.remove("cursor");
    }
    value.to_string()
}

fn to_sse_frame(event: &ControlEvent) -> SseEvent {
    SseEvent::default()
        .id(event.cursor.to_string())
        .data(event_data_json(event))
}

/// Long-lived SSE response: drains [`ControlPlane::events`] from `cursor`,
/// yields one frame per event, and heartbeats with `: ping` under silence.
pub(crate) async fn events_sse(
    Query(query): Query<EventsQuery>,
    headers: HeaderMap,
) -> Sse<impl Stream<Item = Result<SseEvent, Infallible>>> {
    let start = resolve_cursor(&query, &headers);
    let poll_ms = env_ms("VC_CONTROL_SSE_POLL_MS", DEFAULT_POLL_MS);
    let keepalive_ms = env_ms("VC_CONTROL_SSE_KEEPALIVE_MS", DEFAULT_KEEPALIVE_MS);

    let state = StreamState {
        cursor: start,
        pending: VecDeque::new(),
    };

    let event_stream = stream::unfold(state, move |mut state| async move {
        loop {
            if let Some(event) = state.pending.pop_front() {
                let frame = to_sse_frame(&event);
                return Some((Ok::<_, Infallible>(frame), state));
            }

            let plane = ControlPlane::from_env();
            match plane.events().read_since(state.cursor, &[]) {
                Ok(batch) => {
                    state.cursor = batch.cursor;
                    if batch.events.is_empty() {
                        tokio::time::sleep(Duration::from_millis(poll_ms)).await;
                        continue;
                    }
                    state.pending.extend(batch.events);
                }
                Err(_) => {
                    // Transient open/read failure — keep the connection; client
                    // distinguishes silence from death via keepalive.
                    tokio::time::sleep(Duration::from_millis(poll_ms)).await;
                }
            }
        }
    });

    Sse::new(event_stream).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_millis(keepalive_ms))
            // field() formats as `: <text>` → `: ping` (SSE comment heartbeat).
            .text("ping"),
    )
}
