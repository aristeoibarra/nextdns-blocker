use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum PendingCommands {
    /// List pending actions
    List(PendingListArgs),
    /// Show details of a pending action
    Show(PendingShowArgs),
    /// Cancel a pending action
    Cancel(PendingCancelArgs),
}

#[derive(Args)]
pub struct PendingListArgs {
    /// Filter by status
    #[arg(long)]
    pub status: Option<String>,
}

#[derive(Args)]
pub struct PendingShowArgs {
    /// Pending action ID
    pub id: String,
}

#[derive(Args)]
pub struct PendingCancelArgs {
    /// Pending action ID
    pub id: String,
}
