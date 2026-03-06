use clap::Args;

#[derive(Args)]
pub struct InitArgs {
    /// Force re-initialization (overwrites existing config)
    #[arg(long)]
    pub force: bool,
}
