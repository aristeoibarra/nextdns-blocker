use clap::Args;

#[derive(Args)]
pub struct BlockArgs {
    /// Domains to block
    #[arg(required = true)]
    pub domains: Vec<String>,

    /// Description for the blocked domains
    #[arg(long, short)]
    pub description: Option<String>,

    /// Category to assign
    #[arg(long, short)]
    pub category: Option<String>,

    /// Duration to block for (e.g., "30m", "2h", "1d") — auto-unblocks after
    #[arg(long)]
    pub duration: Option<String>,
}
