use clap::Args;

#[derive(Args)]
pub struct UnblockArgs {
    /// Domain or category to unblock
    pub target: String,

    /// Duration to unblock for (e.g., "30m", "2h", "1d")
    #[arg(long, short)]
    pub duration: Option<String>,

    /// PIN for protected items
    #[arg(long)]
    pub pin: Option<String>,
}
