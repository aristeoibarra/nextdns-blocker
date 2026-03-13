use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum AuditCommands {
    /// List recent audit log entries
    List(AuditListArgs),
}

#[derive(Args)]
pub struct AuditListArgs {
    /// Maximum entries to return
    #[arg(long, short, default_value = "50")]
    pub limit: i64,

    /// Number of entries to skip
    #[arg(long, default_value = "0")]
    pub offset: i64,

    /// Filter by domain (searches target_id and details)
    #[arg(long, short)]
    pub domain: Option<String>,

    /// Filter by action (e.g., block, unblock, enforce_failed)
    #[arg(long, short)]
    pub action: Option<String>,

    /// Filter by source (cli, schedule, watchdog, preflight, pending, retry, system)
    #[arg(long, short)]
    pub source: Option<String>,
}
