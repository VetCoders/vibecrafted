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
    /// absent. If rotation or truncation leaves `since_cursor` beyond the
    /// current EOF, resumes from byte 0 of the new generation. Never blocks.
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
        // Rotation/truncation replaces events.jsonl with a shorter stream. A
        // persisted byte cursor from the previous generation would otherwise
        // sit beyond EOF forever and miss every subsequent append.
        let file_len = file.metadata()?.len();
        let start_cursor = if since_cursor > file_len {
            0
        } else {
            since_cursor
        };
        file.seek(SeekFrom::Start(start_cursor))?;
        let mut reader = BufReader::new(file);

        let mut cursor = start_cursor;
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

#[cfg(test)]
mod tests {
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::EventStream;

    fn temp_events_path(label: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "vc-control-events-{label}-{}-{}.jsonl",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|duration| duration.as_nanos())
                .unwrap_or(0)
        ))
    }

    fn event_line(run_id: &str, message: &str) -> String {
        format!(
            r#"{{"ts":"2026-07-26T06:00:00+00:00","run_id":"{run_id}","kind":"state","message":"{message}","payload":{{}}}}"#
        )
    }

    #[test]
    fn cursor_beyond_eof_resets_after_rotation_or_truncation() {
        let path = temp_events_path("cursor-reset");
        let old_line = format!("{}\n", event_line("old-run", &"old".repeat(80)));
        fs::write(&path, &old_line).expect("write old event stream");
        let stream = EventStream::new(&path);
        let old = stream.read_since(0, &[]).expect("read old stream");
        assert_eq!(old.cursor, old_line.len() as u64);

        let new_line = format!("{}\n", event_line("new-run", "after rotation"));
        assert!(
            new_line.len() < old.cursor as usize,
            "fixture must leave the old cursor beyond the new EOF"
        );
        fs::write(&path, &new_line).expect("replace with shorter generation");

        let recovered = stream
            .read_since(old.cursor, &[])
            .expect("read rotated stream");
        assert_eq!(recovered.events.len(), 1);
        assert_eq!(recovered.events[0].run_id, "new-run");
        assert_eq!(recovered.events[0].message, "after rotation");
        assert_eq!(recovered.cursor, new_line.len() as u64);
        assert_eq!(recovered.events[0].cursor, recovered.cursor);

        fs::remove_file(path).ok();
    }
}
