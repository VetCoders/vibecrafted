//! Best-effort macOS GPU probe via ioreg (optional telemetry).

use std::process::Command;

#[derive(Debug, Clone)]
pub struct GpuProbe {
    pub util_percent: Option<f32>,
    pub memory_used: Option<u64>,
    pub memory_total: Option<u64>,
    pub status: String,
}

pub fn probe_gpu() -> GpuProbe {
    #[cfg(not(target_os = "macos"))]
    {
        return GpuProbe {
            util_percent: None,
            memory_used: None,
            memory_total: None,
            status: "GPU telemetry only on macOS".into(),
        };
    }

    #[cfg(target_os = "macos")]
    {
        for class in ["AGXAcceleratorG15X", "IOAccelerator"] {
            let output = Command::new("ioreg")
                .args(["-l", "-w", "0", "-r", "-c", class, "-d", "1"])
                .output();
            let Ok(output) = output else { continue };
            if !output.status.success() {
                continue;
            }
            let stdout = String::from_utf8_lossy(&output.stdout);
            if let Some(util) = extract_u64(&stdout, "Device Utilization %")
                .or_else(|| extract_u64(&stdout, "Renderer Utilization %"))
            {
                let used = extract_u64(&stdout, "In use system memory");
                let total = extract_u64(&stdout, "Alloc system memory");
                return GpuProbe {
                    util_percent: Some(util as f32),
                    memory_used: used,
                    memory_total: total,
                    status: format!("Available ({class})"),
                };
            }
        }
        GpuProbe {
            util_percent: None,
            memory_used: None,
            memory_total: None,
            status: "GPU Unavailable: telemetry keys not found".into(),
        }
    }
}

fn extract_u64(hay: &str, key: &str) -> Option<u64> {
    let needle = format!("\"{key}\"=");
    let idx = hay.find(&needle)?;
    let rest = &hay[idx + needle.len()..];
    let digits: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_device_util() {
        let sample = r#""PerformanceStatistics" = {"Device Utilization %"=13,"In use system memory"=1874984960}"#;
        assert_eq!(extract_u64(sample, "Device Utilization %"), Some(13));
        assert_eq!(
            extract_u64(sample, "In use system memory"),
            Some(1_874_984_960)
        );
    }
}
