fn main() {
    uniffi::generate_scaffolding("./src/shell_agent_ffi.udl").unwrap_or(());
}
