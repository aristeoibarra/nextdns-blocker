use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum WatchdogCommands {
    /// Install the watchdog scheduler service
    Install(WatchdogInstallArgs),
    /// Uninstall the watchdog service
    Uninstall(WatchdogUninstallArgs),
    /// Show watchdog service status
    Status(WatchdogStatusArgs),
    /// Run a single watchdog cycle (used by the service)
    Run(WatchdogRunArgs),
}

#[derive(Args)]
pub struct WatchdogInstallArgs {
    /// Sync interval (e.g., "5m", "15m", "1h")
    #[arg(long, default_value = "5m")]
    pub interval: String,
}

#[derive(Args)]
pub struct WatchdogUninstallArgs {}

#[derive(Args)]
pub struct WatchdogStatusArgs {}

#[derive(Args)]
pub struct WatchdogRunArgs {}
