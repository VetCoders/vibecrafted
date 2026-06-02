use anyhow::Result;
use image::{GenericImageView, imageops::FilterType};
use tray_icon::Icon;

use crate::types::TrayStatus;

const ICON_BYTES: &[u8] = include_bytes!("../assets/icon.png");
const ICON_SIZE: u32 = 44;

pub fn load_custom_icon(status: TrayStatus) -> Result<Icon> {
    let img = image::load_from_memory(ICON_BYTES)?;
    let resized = img.resize_exact(ICON_SIZE, ICON_SIZE, FilterType::Lanczos3);
    let (width, height) = resized.dimensions();
    let mut rgba = resized.to_rgba8().into_raw();
    draw_status_glyph(&mut rgba, width, height, status);
    Icon::from_rgba(rgba, width, height)
        .map_err(|error| anyhow::anyhow!("failed to create tray icon: {error}"))
}

fn color(status: TrayStatus) -> (u8, u8, u8) {
    match status {
        TrayStatus::Idle => (80, 200, 100),
        TrayStatus::Routing => (60, 130, 220),
        TrayStatus::Saturated => (255, 165, 0),
        TrayStatus::Restarting => (255, 220, 60),
        TrayStatus::Spawning { .. } => (80, 210, 210),
        TrayStatus::Failed => (255, 50, 50),
    }
}

fn draw_status_glyph(rgba: &mut [u8], width: u32, height: u32, status: TrayStatus) {
    let (cx, cy, radius) = (width as i32 - 8, height as i32 - 8, 6);
    let color = color(status);
    for y in (cy - radius).max(0)..(cy + radius).min(height as i32) {
        for x in (cx - radius).max(0)..(cx + radius).min(width as i32) {
            let dx = x - cx;
            let dy = y - cy;
            let in_circle = dx * dx + dy * dy <= radius * radius;
            let is_x = (dx - dy).abs() <= 2 || (dx + dy).abs() <= 2;
            if in_circle && (status != TrayStatus::Failed || is_x) {
                paint(rgba, width, x, y, color);
            }
        }
    }
}

fn paint(rgba: &mut [u8], width: u32, x: i32, y: i32, color: (u8, u8, u8)) {
    let idx = ((y as u32 * width + x as u32) * 4) as usize;
    rgba[idx] = color.0;
    rgba[idx + 1] = color.1;
    rgba[idx + 2] = color.2;
    rgba[idx + 3] = 255;
}

pub fn create_fallback_icon(status: TrayStatus) -> Result<Icon> {
    const SIZE: u32 = 22;
    let mut rgba = vec![0; (SIZE * SIZE * 4) as usize];
    let color = color(status);
    for y in 0..SIZE as i32 {
        for x in 0..SIZE as i32 {
            let dx = x - 11;
            let dy = y - 11;
            if dx * dx + dy * dy <= 100 {
                paint(&mut rgba, SIZE, x, y, color);
            }
        }
    }
    Icon::from_rgba(rgba, SIZE, SIZE)
        .map_err(|error| anyhow::anyhow!("failed to create fallback icon: {error}"))
}
