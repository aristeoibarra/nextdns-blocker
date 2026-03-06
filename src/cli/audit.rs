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
}
