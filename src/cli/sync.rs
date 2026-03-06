use clap::Args;

#[derive(Args)]
pub struct SyncArgs {
    /// Dry run: show what would be synced without making changes
    #[arg(long)]
    pub dry_run: bool,

    /// Force sync even if no changes detected
    #[arg(long)]
    pub force: bool,

    /// Only sync the denylist
    #[arg(long)]
    pub denylist_only: bool,

    /// Only sync the allowlist
    #[arg(long)]
    pub allowlist_only: bool,
}
