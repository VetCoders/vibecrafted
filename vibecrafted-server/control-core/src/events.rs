//! Cursor-based event tailing — the SSE substrate.
//!
//! The cursor is a **byte offset** into `events.jsonl`, exactly like the Python
//! `subscribe_events` (`cursor = handle.tell()`). A W2 axum SSE route drains
//! [`EventStream::read_since`] on a tick, streams the returned events, and
//! remembers `EventBatch::cursor` as the `Last-Event-ID` to resume from.
//!
//! Deliberate divergence from `control_plane.subscribe_events`: this reader is
//! non-blocking (no `time.sleep` poll loop — the async runtime owns the tick)
//! and it refuses to consume a partial trailing line (one Python writes mid-
//! `append`). The Python version advances the cursor past a half-written line
//! and drops it on the `JSONDecodeError`; here the cursor stops *before* the
//! partial line so the next drain re-reads it once complete. Documented in
//! `docs/superpowers/specs/2026-05-31-control-core-design.md`.

use std::fs::File;
use std::io::{self, BufRead, BufReader, Seek, SeekFrom};
use std::path::PathBuf;

use crate::model::Event;

/// A read-only tail over a control-plane `events.jsonl`.
#[derive(Debug, Clone)]
pub struct EventStream {
    path: PathBuf,
}

/// A drained batch plus the cursor to resume from.
#[derive(Debug, Clone)]
pub struct EventBatch {
    /// Events decoded in this drain, oldest-first, each stamped with its
    /// resume cursor (byte offset just past its line).
    pub events: Vec<Event>,
    /// Byte offset to pass as `since_cursor` on the next drain. Points at the
    /// start of any partial trailing line, or end-of-file.
    pub cursor: u64,
}

impl EventStream {
    /// Bind to an `events.jsonl` path (the file need not exist yet).
    #[must_use]
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    /// The bound path.
    #[must_use]
    pub fn path(&self) -> &std::path::Path {
        &self.path
    }

    /// Read complete events from `since_cursor` to end-of-file. When `kinds`
    /// is non-empty, only events whose `kind` is in the set are returned (but
    /// the cursor still advances past filtered lines, matching Python).
    ///
    /// Returns an empty batch with `cursor == since_cursor` when the file is
    /// absent. Never blocks.
    pub fn read_since(&self, since_cursor: u64, kinds: &[String]) -> io::Result<EventBatch> {
        let mut file = match File::open(&self.path) {
            Ok(file) => file,
            Err(err) if err.kind() == io::ErrorKind::NotFound => {
                return Ok(EventBatch {
                    events: Vec::new(),
                    cursor: since_cursor,
                });
            }
            Err(err) => return Err(err),
        };
        file.seek(SeekFrom::Start(since_cursor))?;
        let mut reader = BufReader::new(file);

        let mut cursor = since_cursor;
        let mut events = Vec::new();
        let mut line = String::new();
        loop {
            line.clear();
            let read = reader.read_line(&mut line)?;
            if read == 0 {
                break; // EOF
            }
            if !line.ends_with('\n') {
                break; // partial trailing line — do not consume, do not advance
            }
            cursor += read as u64;
            let trimmed = line.trim_end();
            if trimmed.is_empty() {
                continue;
            }
            let Ok(mut event) = serde_json::from_str::<Event>(trimmed) else {
                continue; // malformed but complete line — skip, cursor already advanced
            };
            if !kinds.is_empty() && !kinds.iter().any(|k| k == &event.kind) {
                continue;
            }
            event.cursor = cursor;
            events.push(event);
        }
        Ok(EventBatch { events, cursor })
    }

    /// Convenience: drain from the start with no kind filter.
    pub fn read_all(&self) -> io::Result<EventBatch> {
        self.read_since(0, &[])
    }

    /// Newest-first tail of up to `limit` events. Mirrors
    /// `control_plane.read_event_tail` (which reverses to newest-first).
    pub fn tail(&self, limit: usize) -> io::Result<Vec<Event>> {
        let mut batch = self.read_all()?;
        if batch.events.len() > limit {
            let start = batch.events.len() - limit;
            batch.events.drain(..start);
        }
        batch.events.reverse();
        Ok(batch.events)
    }
}
