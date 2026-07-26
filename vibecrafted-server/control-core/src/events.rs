//! Generation-aware event tailing — the SSE substrate.
//!
//! Python owns the append/rotate protocol. Every v1 segment begins with a
//! `stream.segment` header carrying one epoch UUID and a monotonic generation.
//! A wire cursor is therefore `v2:<epoch>:<generation>:<offset>` rather than a
//! generation-less byte offset. Archived segments bridge reconnects across
//! rotation; a missing generation yields an explicit gap and never silently
//! replays the current file.

use std::fmt;
use std::fs::{self, File};
use std::io::{self, BufRead, BufReader, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::str::FromStr;

use crate::model::Event;

pub const STREAM_SEGMENT_SCHEMA: &str = "vibecrafted.event-stream-segment.v1";
pub const STREAM_BATCH_MAX_EVENTS: usize = 128;
pub const STREAM_BATCH_MAX_BYTES: usize = 1024 * 1024;
pub const STREAM_LINE_MAX_BYTES: usize = 256 * 1024;

/// Durable position in the event stream.
///
/// `Legacy` exists only for generation-less clients during the v1 -> v2
/// migration. New clients should persist the opaque `Display` value.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum StreamCursor {
    Legacy(u64),
    V2 {
        epoch: String,
        generation: u64,
        offset: u64,
    },
}

impl StreamCursor {
    #[must_use]
    pub fn offset(&self) -> u64 {
        match self {
            Self::Legacy(offset) | Self::V2 { offset, .. } => *offset,
        }
    }

    #[must_use]
    pub fn is_v2(&self) -> bool {
        matches!(self, Self::V2 { .. })
    }

    /// Whether this cursor has reached a connection's captured high-watermark.
    #[must_use]
    pub fn reaches(&self, target: &Self) -> bool {
        match (self, target) {
            (Self::Legacy(current), Self::Legacy(target)) => current >= target,
            (
                Self::V2 {
                    epoch: current_epoch,
                    generation: current_generation,
                    offset: current_offset,
                },
                Self::V2 {
                    epoch: target_epoch,
                    generation: target_generation,
                    offset: target_offset,
                },
            ) if current_epoch == target_epoch => {
                current_generation > target_generation
                    || (current_generation == target_generation && current_offset >= target_offset)
            }
            _ => false,
        }
    }
}

impl fmt::Display for StreamCursor {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Legacy(offset) => write!(formatter, "{offset}"),
            Self::V2 {
                epoch,
                generation,
                offset,
            } => write!(formatter, "v2:{epoch}:{generation}:{offset}"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CursorParseError;

impl fmt::Display for CursorParseError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("invalid event stream cursor")
    }
}

impl std::error::Error for CursorParseError {}

impl FromStr for StreamCursor {
    type Err = CursorParseError;

    fn from_str(raw: &str) -> Result<Self, Self::Err> {
        let value = raw.trim();
        if let Ok(offset) = value.parse::<u64>() {
            return Ok(Self::Legacy(offset));
        }
        let mut parts = value.split(':');
        if parts.next() != Some("v2") {
            return Err(CursorParseError);
        }
        let epoch = parts.next().unwrap_or_default();
        let generation = parts
            .next()
            .and_then(|part| part.parse::<u64>().ok())
            .ok_or(CursorParseError)?;
        let offset = parts
            .next()
            .and_then(|part| part.parse::<u64>().ok())
            .ok_or(CursorParseError)?;
        if parts.next().is_some()
            || epoch.is_empty()
            || !epoch
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'))
        {
            return Err(CursorParseError);
        }
        Ok(Self::V2 {
            epoch: epoch.to_string(),
            generation,
            offset,
        })
    }
}

#[derive(Debug, Clone)]
pub struct StreamRecord {
    pub event: Event,
    pub cursor: StreamCursor,
}

#[derive(Debug, Clone)]
pub struct StreamBoundary {
    pub from: StreamCursor,
    pub to: StreamCursor,
}

#[derive(Debug, Clone)]
pub struct StreamGap {
    pub requested: String,
    pub resumed_at: StreamCursor,
    pub reason: String,
}

#[derive(Debug, Clone)]
pub enum StreamItem {
    Event(StreamRecord),
    Boundary(StreamBoundary),
    Gap(StreamGap),
}

#[derive(Debug, Clone)]
pub struct StreamBatch {
    pub items: Vec<StreamItem>,
    pub cursor: StreamCursor,
    pub scanned_events: usize,
    pub scanned_bytes: usize,
}

/// Compatibility batch for the old active-file-only byte-offset API.
#[derive(Debug, Clone)]
pub struct EventBatch {
    pub events: Vec<Event>,
    pub cursor: u64,
}

#[derive(Debug, Clone)]
pub struct EventStream {
    path: PathBuf,
}

#[derive(Debug, Clone)]
struct Segment {
    path: PathBuf,
    epoch: String,
    generation: u64,
    data_start: u64,
    len: u64,
    active: bool,
}

#[derive(Debug, Clone)]
enum CursorStyle {
    Legacy,
    V2 { epoch: String, generation: u64 },
}

impl CursorStyle {
    fn at(&self, offset: u64) -> StreamCursor {
        match self {
            Self::Legacy => StreamCursor::Legacy(offset),
            Self::V2 { epoch, generation } => StreamCursor::V2 {
                epoch: epoch.clone(),
                generation: *generation,
                offset,
            },
        }
    }
}

#[derive(Debug)]
struct Drain {
    items: Vec<StreamItem>,
    cursor: u64,
    scanned_events: usize,
    scanned_bytes: usize,
    at_eof: bool,
}

#[derive(Debug)]
struct BoundedLine {
    data: Vec<u8>,
    bytes: usize,
    complete: bool,
    too_long: bool,
}

#[derive(Debug, Clone, Copy, Default)]
struct DrainBudget {
    events: usize,
    bytes: usize,
}

impl EventStream {
    #[must_use]
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    fn open_active(&self) -> io::Result<Option<(File, Option<Segment>)>> {
        let mut file = match File::open(&self.path) {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(error),
        };
        let segment = read_v1_segment_from_file(&mut file, self.path.clone(), true)?;
        Ok(Some((file, segment)))
    }

    /// Cursor at the first event of the active segment.
    pub fn start_cursor(&self) -> io::Result<StreamCursor> {
        if let Some((_, Some(segment))) = self.open_active()? {
            return Ok(StreamCursor::V2 {
                epoch: segment.epoch,
                generation: segment.generation,
                offset: segment.data_start,
            });
        }
        Ok(StreamCursor::Legacy(0))
    }

    /// Last complete record boundary in the active segment.
    pub fn high_watermark(&self) -> io::Result<StreamCursor> {
        let Some((mut file, segment)) = self.open_active()? else {
            return Ok(StreamCursor::Legacy(0));
        };
        if let Some(segment) = segment {
            let offset = last_complete_offset_in_file(&mut file, segment.data_start)?;
            return Ok(StreamCursor::V2 {
                epoch: segment.epoch,
                generation: segment.generation,
                offset,
            });
        }
        Ok(StreamCursor::Legacy(last_complete_offset_in_file(
            &mut file, 0,
        )?))
    }

    /// Bounded generation-aware drain used by the SSE server.
    pub fn read_stream(&self, cursor: &StreamCursor, kinds: &[String]) -> io::Result<StreamBatch> {
        match cursor {
            StreamCursor::Legacy(offset) => self.read_legacy_stream(*offset, kinds),
            StreamCursor::V2 {
                epoch,
                generation,
                offset,
            } => self.read_v2_stream(epoch, *generation, *offset, kinds),
        }
    }

    fn read_legacy_stream(&self, offset: u64, kinds: &[String]) -> io::Result<StreamBatch> {
        let Some((file, segment)) = self.open_active()? else {
            return Ok(StreamBatch {
                items: Vec::new(),
                cursor: StreamCursor::Legacy(offset),
                scanned_events: 0,
                scanned_bytes: 0,
            });
        };
        let file_len = file.metadata()?.len();
        let data_start = segment.map_or(0, |segment| segment.data_start);
        let start = if offset == 0 { data_start } else { offset };
        if start > file_len {
            return self.gap_batch(cursor_string(offset), "legacy_cursor_beyond_eof");
        }
        let style = CursorStyle::Legacy;
        let drain = drain_file(
            file,
            start,
            true,
            &style,
            None,
            kinds,
            DrainBudget::default(),
        )?;
        Ok(StreamBatch {
            items: drain.items,
            cursor: style.at(drain.cursor),
            scanned_events: drain.scanned_events,
            scanned_bytes: drain.scanned_bytes,
        })
    }

    fn read_v2_stream(
        &self,
        epoch: &str,
        generation: u64,
        offset: u64,
        kinds: &[String],
    ) -> io::Result<StreamBatch> {
        let requested = StreamCursor::V2 {
            epoch: epoch.to_string(),
            generation,
            offset,
        };
        let segments = self.v1_segments()?;
        let matching: Vec<_> = segments
            .iter()
            .filter(|segment| segment.epoch == epoch && segment.generation == generation)
            .cloned()
            .collect();
        if matching.len() != 1 {
            let reason = if matching.is_empty() {
                "generation_expired_or_unknown"
            } else {
                "ambiguous_generation"
            };
            return self.gap_batch(requested.to_string(), reason);
        }
        let mut current = matching[0].clone();
        if offset < current.data_start || offset > current.len {
            return self.gap_batch(requested.to_string(), "cursor_outside_segment");
        }
        let mut cursor = requested;
        let mut items = Vec::new();
        let mut scanned_events = 0;
        let mut scanned_bytes = 0;

        loop {
            let style = CursorStyle::V2 {
                epoch: current.epoch.clone(),
                generation: current.generation,
            };
            let drain = drain_file(
                File::open(&current.path)?,
                cursor.offset(),
                current.active,
                &style,
                Some((&current.epoch, current.generation)),
                kinds,
                DrainBudget {
                    events: scanned_events,
                    bytes: scanned_bytes,
                },
            )?;
            items.extend(drain.items);
            scanned_events += drain.scanned_events;
            scanned_bytes += drain.scanned_bytes;
            cursor = style.at(drain.cursor);

            if !drain.at_eof
                || scanned_events >= STREAM_BATCH_MAX_EVENTS
                || scanned_bytes >= STREAM_BATCH_MAX_BYTES
            {
                break;
            }

            let next_generation = current.generation + 1;
            let next: Vec<_> = segments
                .iter()
                .filter(|segment| segment.epoch == epoch && segment.generation == next_generation)
                .cloned()
                .collect();
            if next.is_empty() {
                break;
            }
            if next.len() != 1 {
                return self.gap_batch(cursor.to_string(), "ambiguous_generation");
            }
            let next = next[0].clone();
            let next_cursor = StreamCursor::V2 {
                epoch: next.epoch.clone(),
                generation: next.generation,
                offset: next.data_start,
            };
            items.push(StreamItem::Boundary(StreamBoundary {
                from: cursor,
                to: next_cursor.clone(),
            }));
            cursor = next_cursor;
            current = next;
        }

        Ok(StreamBatch {
            items,
            cursor,
            scanned_events,
            scanned_bytes,
        })
    }

    fn gap_batch(&self, requested: String, reason: &str) -> io::Result<StreamBatch> {
        // Recovery skips to the active high-watermark. Replaying retained
        // effects after an unknown gap would be worse than missing them
        // silently; the explicit gap instructs the client to re-snapshot.
        let resumed_at = self.high_watermark()?;
        Ok(StreamBatch {
            items: vec![StreamItem::Gap(StreamGap {
                requested,
                resumed_at: resumed_at.clone(),
                reason: reason.to_string(),
            })],
            cursor: resumed_at,
            scanned_events: 0,
            scanned_bytes: 0,
        })
    }

    fn v1_segments(&self) -> io::Result<Vec<Segment>> {
        let mut segments = Vec::new();
        let archive = self
            .path
            .parent()
            .unwrap_or_else(|| Path::new("."))
            .join("events_archive");
        match fs::read_dir(archive) {
            Ok(entries) => {
                for entry in entries.flatten() {
                    let path = entry.path();
                    let mut file = File::open(&path)?;
                    if let Some(segment) = read_v1_segment_from_file(&mut file, path, false)? {
                        segments.push(segment);
                    }
                }
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound => {}
            Err(error) => return Err(error),
        }
        if let Some((_, Some(active))) = self.open_active()? {
            segments.push(active);
        }
        segments.sort_by(|left, right| {
            left.epoch
                .cmp(&right.epoch)
                .then(left.generation.cmp(&right.generation))
        });
        Ok(segments)
    }

    /// Legacy active-file-only reader retained for Rust API compatibility.
    pub fn read_since(&self, since_cursor: u64, kinds: &[String]) -> io::Result<EventBatch> {
        let mut file = match File::open(&self.path) {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::NotFound => {
                return Ok(EventBatch {
                    events: Vec::new(),
                    cursor: since_cursor,
                });
            }
            Err(error) => return Err(error),
        };
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
                break;
            }
            if !line.ends_with('\n') {
                break;
            }
            cursor += u64::try_from(read).unwrap_or(u64::MAX);
            let trimmed = line.trim_end();
            if trimmed.is_empty() {
                continue;
            }
            let Ok(mut event) = serde_json::from_str::<Event>(trimmed) else {
                continue;
            };
            if event.kind == "stream.segment" {
                continue;
            }
            if !kinds.is_empty() && !kinds.iter().any(|kind| kind == &event.kind) {
                continue;
            }
            event.cursor = cursor;
            events.push(event);
        }
        Ok(EventBatch { events, cursor })
    }

    pub fn read_all(&self) -> io::Result<EventBatch> {
        self.read_since(0, &[])
    }

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

fn cursor_string(offset: u64) -> String {
    StreamCursor::Legacy(offset).to_string()
}

fn read_v1_segment_from_file(
    file: &mut File,
    path: PathBuf,
    active: bool,
) -> io::Result<Option<Segment>> {
    let len = file.metadata()?.len();
    let Some((epoch, generation, data_start)) = read_segment_header_from_file(file)? else {
        return Ok(None);
    };
    Ok(Some(Segment {
        path,
        epoch,
        generation,
        data_start,
        len,
        active,
    }))
}

fn read_segment_header_from_file(file: &mut File) -> io::Result<Option<(String, u64, u64)>> {
    file.seek(SeekFrom::Start(0))?;
    let mut reader = BufReader::new(&mut *file);
    let mut raw = Vec::new();
    let read = reader
        .by_ref()
        .take(u64::try_from(STREAM_LINE_MAX_BYTES + 1).unwrap_or(u64::MAX))
        .read_until(b'\n', &mut raw)?;
    if read == 0 || read > STREAM_LINE_MAX_BYTES || raw.last().copied() != Some(b'\n') {
        return Ok(None);
    }
    Ok(parse_segment_header(&raw)
        .map(|(epoch, generation)| (epoch, generation, u64::try_from(read).unwrap_or(u64::MAX))))
}

fn parse_segment_header(raw: &[u8]) -> Option<(String, u64)> {
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(raw) else {
        return None;
    };
    let payload = value.get("payload").and_then(serde_json::Value::as_object);
    let schema = payload
        .and_then(|object| object.get("schema"))
        .and_then(serde_json::Value::as_str);
    let epoch = payload
        .and_then(|object| object.get("epoch"))
        .and_then(serde_json::Value::as_str);
    let generation = payload
        .and_then(|object| object.get("generation"))
        .and_then(serde_json::Value::as_u64);
    if value.get("kind").and_then(serde_json::Value::as_str) != Some("stream.segment")
        || schema != Some(STREAM_SEGMENT_SCHEMA)
        || epoch.is_none()
        || generation.is_none()
    {
        return None;
    }
    Some((
        epoch.unwrap_or_default().to_string(),
        generation.unwrap_or_default(),
    ))
}

fn drain_file(
    mut file: File,
    start: u64,
    active: bool,
    style: &CursorStyle,
    expected_segment: Option<(&str, u64)>,
    kinds: &[String],
    prior: DrainBudget,
) -> io::Result<Drain> {
    if let Some((expected_epoch, expected_generation)) = expected_segment {
        let observed = read_segment_header_from_file(&mut file)?;
        if observed
            .as_ref()
            .map(|(epoch, generation, _)| (epoch.as_str(), *generation))
            != Some((expected_epoch, expected_generation))
        {
            return Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "event segment rotated before drain",
            ));
        }
    }
    file.seek(SeekFrom::Start(start))?;
    let mut reader = BufReader::new(file);
    let mut cursor = start;
    let mut items = Vec::new();
    let mut scanned_events = 0;
    let mut scanned_bytes = 0;
    let mut at_eof = false;

    while prior.events + scanned_events < STREAM_BATCH_MAX_EVENTS
        && prior.bytes + scanned_bytes < STREAM_BATCH_MAX_BYTES
    {
        let line_start = cursor;
        let line = read_bounded_line(&mut reader)?;
        if line.bytes == 0 {
            at_eof = true;
            break;
        }
        if prior.bytes + scanned_bytes + line.bytes > STREAM_BATCH_MAX_BYTES
            && prior.events + scanned_events > 0
        {
            break;
        }
        if line.too_long {
            cursor = cursor.saturating_add(u64::try_from(line.bytes).unwrap_or(u64::MAX));
            scanned_events += 1;
            scanned_bytes += line.bytes;
            items.push(StreamItem::Gap(StreamGap {
                requested: style.at(line_start).to_string(),
                resumed_at: style.at(cursor),
                reason: "line_too_large".to_string(),
            }));
            continue;
        }
        if !line.complete {
            if active {
                break;
            }
            cursor = cursor.saturating_add(u64::try_from(line.bytes).unwrap_or(u64::MAX));
            scanned_bytes += line.bytes;
            items.push(StreamItem::Gap(StreamGap {
                requested: style.at(line_start).to_string(),
                resumed_at: style.at(cursor),
                reason: "partial_archived_line".to_string(),
            }));
            at_eof = true;
            break;
        }

        cursor = cursor.saturating_add(u64::try_from(line.bytes).unwrap_or(u64::MAX));
        scanned_events += 1;
        scanned_bytes += line.bytes;
        let Ok(mut event) = serde_json::from_slice::<Event>(&line.data) else {
            items.push(StreamItem::Gap(StreamGap {
                requested: style.at(line_start).to_string(),
                resumed_at: style.at(cursor),
                reason: "malformed_event".to_string(),
            }));
            continue;
        };
        if event.kind == "stream.segment" {
            continue;
        }
        if !kinds.is_empty() && !kinds.iter().any(|kind| kind == &event.kind) {
            continue;
        }
        event.cursor = cursor;
        items.push(StreamItem::Event(StreamRecord {
            event,
            cursor: style.at(cursor),
        }));
    }

    Ok(Drain {
        items,
        cursor,
        scanned_events,
        scanned_bytes,
        at_eof,
    })
}

fn read_bounded_line(reader: &mut impl BufRead) -> io::Result<BoundedLine> {
    let mut data = Vec::new();
    let mut bytes = 0;
    let mut complete = false;
    let mut too_long = false;

    loop {
        let available = reader.fill_buf()?;
        if available.is_empty() {
            break;
        }
        let budget = STREAM_LINE_MAX_BYTES + 1 - bytes;
        let visible = available.len().min(budget);
        let newline = available[..visible].iter().position(|byte| *byte == b'\n');
        let take = newline.map_or(visible, |position| position + 1);
        if data.len() + take <= STREAM_LINE_MAX_BYTES {
            data.extend_from_slice(&available[..take]);
        } else {
            too_long = true;
            data.clear();
        }
        reader.consume(take);
        bytes += take;
        if newline.is_some() {
            complete = true;
            break;
        }
        if bytes > STREAM_LINE_MAX_BYTES {
            too_long = true;
            break;
        }
    }
    Ok(BoundedLine {
        data,
        bytes,
        complete,
        too_long,
    })
}

fn last_complete_offset_in_file(file: &mut File, minimum: u64) -> io::Result<u64> {
    let len = file.metadata()?.len();
    if len <= minimum {
        return Ok(minimum.min(len));
    }
    file.seek(SeekFrom::End(-1))?;
    let mut final_byte = [0_u8; 1];
    file.read_exact(&mut final_byte)?;
    if final_byte[0] == b'\n' {
        return Ok(len);
    }

    let mut end = len;
    let mut buffer = vec![0_u8; 8192];
    while end > minimum {
        let start = end.saturating_sub(u64::try_from(buffer.len()).unwrap_or(u64::MAX));
        let start = start.max(minimum);
        let size = usize::try_from(end - start).unwrap_or(buffer.len());
        file.seek(SeekFrom::Start(start))?;
        file.read_exact(&mut buffer[..size])?;
        if let Some(position) = buffer[..size].iter().rposition(|byte| *byte == b'\n') {
            return Ok(start + u64::try_from(position + 1).unwrap_or(u64::MAX));
        }
        end = start;
    }
    Ok(minimum)
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    use super::{
        EventStream, STREAM_BATCH_MAX_BYTES, STREAM_BATCH_MAX_EVENTS, STREAM_SEGMENT_SCHEMA,
        StreamCursor, StreamItem,
    };

    fn temp_dir(label: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "vc-control-events-{label}-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|duration| duration.as_nanos())
                .unwrap_or(0)
        ))
    }

    fn header(epoch: &str, generation: u64) -> String {
        format!(
            r#"{{"ts":"2026-07-26T06:00:00+00:00","run_id":"","kind":"stream.segment","message":"generation","payload":{{"schema":"{STREAM_SEGMENT_SCHEMA}","epoch":"{epoch}","generation":{generation}}}}}"#
        )
    }

    fn event_line(run_id: &str, message: &str) -> String {
        format!(
            r#"{{"ts":"2026-07-26T06:00:00+00:00","run_id":"{run_id}","kind":"state","message":"{message}","payload":{{}}}}"#
        )
    }

    fn write_segment(path: &std::path::Path, epoch: &str, generation: u64, events: &[String]) {
        let mut lines = vec![header(epoch, generation)];
        lines.extend_from_slice(events);
        fs::write(path, format!("{}\n", lines.join("\n"))).expect("write segment");
    }

    fn event_records(batch: &super::StreamBatch) -> Vec<&super::StreamRecord> {
        batch
            .items
            .iter()
            .filter_map(|item| match item {
                StreamItem::Event(record) => Some(record),
                StreamItem::Boundary(_) | StreamItem::Gap(_) => None,
            })
            .collect()
    }

    #[test]
    fn v2_cursor_round_trips() {
        let cursor: StreamCursor = "v2:123e4567-e89b-12d3-a456-426614174000:7:991"
            .parse()
            .expect("parse cursor");
        assert_eq!(
            cursor.to_string(),
            "v2:123e4567-e89b-12d3-a456-426614174000:7:991"
        );
    }

    #[test]
    fn same_generation_resume_has_no_skip_or_duplicate() {
        let dir = temp_dir("same-generation");
        fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("events.jsonl");
        write_segment(
            &path,
            "epoch-a",
            0,
            &[
                event_line("run-a", "one"),
                event_line("run-a", "two"),
                event_line("run-a", "three"),
            ],
        );
        let stream = EventStream::new(&path);
        let first = stream
            .read_stream(&stream.start_cursor().expect("start"), &[])
            .expect("first drain");
        let records = event_records(&first);
        assert_eq!(records.len(), 3);
        let middle = records[1].cursor.clone();
        let resumed = stream.read_stream(&middle, &[]).expect("resume");
        let messages: Vec<_> = event_records(&resumed)
            .iter()
            .map(|record| record.event.message.as_str())
            .collect();
        assert_eq!(messages, vec!["three"]);
        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn archived_generation_bridges_to_larger_new_generation() {
        let dir = temp_dir("archive-bridge");
        let archive = dir.join("events_archive");
        fs::create_dir_all(&archive).expect("mkdir archive");
        let path = dir.join("events.jsonl");
        let old = archive.join("events-epoch-b-g00000000000000000000.jsonl");
        write_segment(&old, "epoch-b", 0, &[event_line("old", "old")]);
        let old_stream = EventStream::new(&old);
        let old_batch = old_stream
            .read_stream(&old_stream.start_cursor().expect("old start"), &[])
            .expect("old drain");
        let saved = old_batch.cursor;
        write_segment(
            &path,
            "epoch-b",
            1,
            &[event_line("new", &"new".repeat(400))],
        );
        assert!(fs::metadata(&path).expect("new metadata").len() > saved.offset());

        let stream = EventStream::new(&path);
        let bridged = stream.read_stream(&saved, &[]).expect("bridge");
        assert!(
            bridged
                .items
                .iter()
                .any(|item| matches!(item, StreamItem::Boundary(_)))
        );
        let records = event_records(&bridged);
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].event.run_id, "new");
        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn expired_generation_emits_gap_without_replaying_active_effects() {
        let dir = temp_dir("expired");
        fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("events.jsonl");
        write_segment(&path, "epoch-c", 2, &[event_line("new", "do not replay")]);
        let stream = EventStream::new(&path);
        let expired = StreamCursor::V2 {
            epoch: "epoch-c".to_string(),
            generation: 0,
            offset: 100,
        };
        let batch = stream.read_stream(&expired, &[]).expect("gap");
        assert_eq!(batch.items.len(), 1);
        assert!(matches!(batch.items[0], StreamItem::Gap(_)));
        assert!(event_records(&batch).is_empty());
        assert_eq!(
            batch.cursor,
            stream.high_watermark().expect("high watermark")
        );
        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn generation_drain_is_bounded_and_resumable() {
        let dir = temp_dir("batch-bounds");
        fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("events.jsonl");
        let events: Vec<_> = (0..200)
            .map(|index| event_line("busy", &format!("event-{index}")))
            .collect();
        write_segment(&path, "epoch-d", 0, &events);
        let stream = EventStream::new(&path);
        let first = stream
            .read_stream(&stream.start_cursor().expect("start"), &[])
            .expect("first bounded batch");
        assert_eq!(first.scanned_events, STREAM_BATCH_MAX_EVENTS);
        assert!(first.scanned_bytes <= STREAM_BATCH_MAX_BYTES);
        assert_eq!(event_records(&first).len(), STREAM_BATCH_MAX_EVENTS);
        let second = stream
            .read_stream(&first.cursor, &[])
            .expect("second bounded batch");
        assert_eq!(event_records(&second).len(), 200 - STREAM_BATCH_MAX_EVENTS);
        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn oversized_line_is_a_bounded_explicit_gap() {
        let dir = temp_dir("line-bound");
        fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("events.jsonl");
        write_segment(
            &path,
            "epoch-e",
            0,
            &[event_line(
                "oversized",
                &"x".repeat(STREAM_BATCH_MAX_BYTES * 2),
            )],
        );
        let stream = EventStream::new(&path);
        let batch = stream
            .read_stream(&stream.start_cursor().expect("start"), &[])
            .expect("bounded gap");
        assert!(batch.scanned_bytes <= STREAM_BATCH_MAX_BYTES);
        assert!(batch.items.iter().any(|item| {
            matches!(
                item,
                StreamItem::Gap(gap) if gap.reason == "line_too_large"
            )
        }));
        fs::remove_dir_all(dir).ok();
    }

    #[test]
    fn legacy_cursor_beyond_eof_resets_for_compatibility_api() {
        let dir = temp_dir("legacy-reset");
        fs::create_dir_all(&dir).expect("mkdir");
        let path = dir.join("events.jsonl");
        let old_line = format!("{}\n", event_line("old-run", &"old".repeat(80)));
        fs::write(&path, &old_line).expect("write old stream");
        let stream = EventStream::new(&path);
        let old = stream.read_since(0, &[]).expect("read old stream");
        let new_line = format!("{}\n", event_line("new-run", "after rotation"));
        fs::write(&path, &new_line).expect("replace shorter");
        let recovered = stream
            .read_since(old.cursor, &[])
            .expect("legacy compatibility read");
        assert_eq!(recovered.events.len(), 1);
        assert_eq!(recovered.events[0].run_id, "new-run");
        fs::remove_dir_all(dir).ok();
    }
}
