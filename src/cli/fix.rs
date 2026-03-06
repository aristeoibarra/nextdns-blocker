use clap::Args;

#[derive(Args)]
pub struct FixArgs {
    /// Run all fixes without prompting
    #[arg(long)]
    pub auto: bool,

    /// Only check, don't fix
    #[arg(long)]
    pub check_only: bool,
}
