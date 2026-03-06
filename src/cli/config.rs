use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum ConfigCommands {
    /// Show current configuration
    Show(ConfigShowArgs),
    /// Set a configuration value
    Set(ConfigSetArgs),
    /// Validate configuration
    Validate(ConfigValidateArgs),
    /// Push local config to NextDNS API
    Push(ConfigPushArgs),
    /// Show diff between local config and NextDNS API
    Diff(ConfigDiffArgs),
}

#[derive(Args)]
pub struct ConfigShowArgs {
    /// Show only a specific key
    pub key: Option<String>,
}

#[derive(Args)]
pub struct ConfigSetArgs {
    /// Configuration key
    pub key: String,
    /// Configuration value
    pub value: String,
}

#[derive(Args)]
pub struct ConfigValidateArgs {}

#[derive(Args)]
pub struct ConfigPushArgs {
    /// Dry run: show changes without applying
    #[arg(long)]
    pub dry_run: bool,
}

#[derive(Args)]
pub struct ConfigDiffArgs {}
