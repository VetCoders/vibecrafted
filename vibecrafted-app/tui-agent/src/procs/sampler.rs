//! sysinfo-based process sampler.

use std::collections::HashMap;
use std::time::Instant;

use sysinfo::{Pid, ProcessesToUpdate, System};

use super::gpu::probe_gpu;
use super::model::{FamilyAggregate, FamilyTag, MonitorSnapshot, ProcessRow, sort_by_rss};

pub struct Sampler {
    system: System,
    self_pid: Pid,
}

impl Sampler {
    pub fn new() -> Self {
        let mut system = System::new_all();
        system.refresh_all();
        Self {
            system,
            self_pid: Pid::from_u32(std::process::id()),
        }
    }

    pub fn sample(&mut self) -> MonitorSnapshot {
        self.system.refresh_cpu_usage();
        self.system.refresh_memory();
        self.system.refresh_processes(ProcessesToUpdate::All, true);

        let mut snap = MonitorSnapshot {
            system_cpu_percent: self.system.global_cpu_usage(),
            system_ram_used: self.system.used_memory(),
            system_ram_total: self.system.total_memory(),
            sampled_at: Instant::now(),
            ..MonitorSnapshot::default()
        };

        if let Some(proc) = self.system.process(self.self_pid) {
            snap.self_cpu = proc.cpu_usage();
            snap.self_rss = proc.memory();
        }

        let mut processes = Vec::new();
        for (pid, proc) in self.system.processes() {
            let name = proc.name().to_string_lossy().to_string();
            let cmd = proc
                .cmd()
                .iter()
                .map(|s| s.to_string_lossy())
                .collect::<Vec<_>>()
                .join(" ");
            let display_cmd = if cmd.is_empty() { name.clone() } else { cmd };
            let family = FamilyTag::classify(&name, &display_cmd);
            // Keep VC fleet + self; skip pure system noise for readability.
            if family == FamilyTag::Other && *pid != self.self_pid {
                continue;
            }
            let identity = format!(
                "{}:{}",
                pid.as_u32(),
                display_cmd.chars().take(48).collect::<String>()
            );
            processes.push(ProcessRow {
                pid: pid.as_u32(),
                ppid: proc.parent().map(|p| p.as_u32()).unwrap_or(0),
                name,
                command: display_cmd,
                cpu: proc.cpu_usage(),
                rss: proc.memory(),
                family,
                identity,
            });
        }
        sort_by_rss(&mut processes);

        let mut fam: HashMap<FamilyTag, FamilyAggregate> = HashMap::new();
        for row in &processes {
            let agg = fam.entry(row.family).or_insert(FamilyAggregate {
                family: row.family,
                count: 0,
                cpu: 0.0,
                rss: 0,
            });
            agg.count += 1;
            agg.cpu += row.cpu;
            agg.rss += row.rss;
        }
        let mut families: Vec<_> = fam.into_values().collect();
        families.sort_by_key(|family| std::cmp::Reverse(family.rss));

        let gpu = probe_gpu();
        snap.gpu_util_percent = gpu.util_percent;
        snap.gpu_memory_used = gpu.memory_used;
        snap.gpu_memory_total = gpu.memory_total;
        snap.gpu_status = gpu.status;
        snap.families = families;
        snap.processes = processes;
        snap
    }
}

impl Default for Sampler {
    fn default() -> Self {
        Self::new()
    }
}
