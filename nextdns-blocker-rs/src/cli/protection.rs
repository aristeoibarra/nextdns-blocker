use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum ProtectionCommands {
    /// Show protection status
    Status(ProtectionStatusArgs),
    /// Request unlock for a protected item
    UnlockRequest(UnlockRequestArgs),
    /// Cancel an unlock request
    Cancel(ProtectionCancelArgs),
    /// List unlock requests
    List(ProtectionListArgs),
    /// Set or change the PIN
    PinSet(PinSetArgs),
    /// Remove the PIN
    PinRemove(PinRemoveArgs),
    /// Show PIN status
    PinStatus(PinStatusArgs),
    /// Verify PIN (create session)
    PinVerify(PinVerifyArgs),
}

#[derive(Args)]
pub struct ProtectionStatusArgs {}

#[derive(Args)]
pub struct UnlockRequestArgs {
    /// Target type (domain, category, service)
    #[arg(long)]
    pub target_type: String,

    /// Target ID
    #[arg(long)]
    pub target_id: String,

    /// Reason for unlock
    #[arg(long)]
    pub reason: String,
}

#[derive(Args)]
pub struct ProtectionCancelArgs {
    /// Unlock request ID
    pub id: String,
}

#[derive(Args)]
pub struct ProtectionListArgs {
    /// Filter by status
    #[arg(long)]
    pub status: Option<String>,
}

#[derive(Args)]
pub struct PinSetArgs {
    /// New PIN
    pub pin: String,

    /// Current PIN (required if changing)
    #[arg(long)]
    pub current: Option<String>,
}

#[derive(Args)]
pub struct PinRemoveArgs {
    /// Current PIN
    pub pin: String,
}

#[derive(Args)]
pub struct PinStatusArgs {}

#[derive(Args)]
pub struct PinVerifyArgs {
    /// PIN to verify
    pub pin: String,
}
