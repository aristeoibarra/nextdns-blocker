use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum AllowlistCommands {
    /// Add domains to the allowlist
    Add(AllowlistAddArgs),
    /// Remove domains from the allowlist
    Remove(AllowlistRemoveArgs),
    /// List all domains in the allowlist
    List(AllowlistListArgs),
    /// Import domains from a file
    Import(AllowlistImportArgs),
    /// Export domains to a file
    Export(AllowlistExportArgs),
}

#[derive(Args)]
pub struct AllowlistAddArgs {
    /// Domains to add
    #[arg(required = true)]
    pub domains: Vec<String>,

    /// Description for the domains
    #[arg(long, short)]
    pub description: Option<String>,
}

#[derive(Args)]
pub struct AllowlistRemoveArgs {
    /// Domains to remove
    #[arg(required = true)]
    pub domains: Vec<String>,
}

#[derive(Args)]
pub struct AllowlistListArgs {
    /// Show all domains (including inactive)
    #[arg(long)]
    pub all: bool,
}

#[derive(Args)]
pub struct AllowlistImportArgs {
    /// Path to file with domains
    pub file: String,

    /// Description for imported domains
    #[arg(long, short)]
    pub description: Option<String>,
}

#[derive(Args)]
pub struct AllowlistExportArgs {
    /// Output file path (stdout if not specified)
    pub file: Option<String>,

    /// Export format: lines or json
    #[arg(long, default_value = "lines")]
    pub format: String,
}
