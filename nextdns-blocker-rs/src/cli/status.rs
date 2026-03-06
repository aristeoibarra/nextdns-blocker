use clap::Args;

#[derive(Args)]
pub struct StatusArgs {
    /// Show detailed status including per-domain info
    #[arg(long)]
    pub detailed: bool,
}
