use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum DenylistCommands {
    /// Add domains to the denylist
    Add(DenylistAddArgs),
    /// Remove domains from the denylist
    Remove(DenylistRemoveArgs),
    /// List all domains in the denylist
    List(DenylistListArgs),
    /// Import domains from a file
    Import(DenylistImportArgs),
    /// Export domains to a file
    Export(DenylistExportArgs),
}

#[derive(Args)]
pub struct DenylistAddArgs {
    /// Domains to add
    #[arg(required = true)]
    pub domains: Vec<String>,

    /// Description for the domains
    #[arg(long, short)]
    pub description: Option<String>,

    /// Category to assign
    #[arg(long, short)]
    pub category: Option<String>,

    /// Schedule (JSON string or "none")
    #[arg(long)]
    pub schedule: Option<String>,
}

#[derive(Args)]
pub struct DenylistRemoveArgs {
    /// Domains to remove
    #[arg(required = true)]
    pub domains: Vec<String>,

}

#[derive(Args)]
pub struct DenylistListArgs {
    /// Show all domains (including inactive)
    #[arg(long)]
    pub all: bool,

    /// Filter by category
    #[arg(long, short)]
    pub category: Option<String>,
}

#[derive(Args)]
pub struct DenylistImportArgs {
    /// Path to file with domains (one per line or JSON)
    pub file: String,

    /// Description for imported domains
    #[arg(long, short)]
    pub description: Option<String>,
}

#[derive(Args)]
pub struct DenylistExportArgs {
    /// Output file path (stdout if not specified)
    pub file: Option<String>,

    /// Export format: lines or json
    #[arg(long, default_value = "lines")]
    pub format: String,
}
