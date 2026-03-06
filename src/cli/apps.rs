use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum AppsCommands {
    /// List app mappings and their block status
    List(AppsListArgs),
    /// Scan installed apps and show which have known mappings
    Scan(AppsScanArgs),
    /// Create a domain-to-app mapping
    Map(AppsMapArgs),
    /// Remove a domain-to-app mapping
    Unmap(AppsUnmapArgs),
    /// Restore all blocked apps (emergency recovery)
    Restore(AppsRestoreArgs),
}

#[derive(Args)]
pub struct AppsListArgs {}

#[derive(Args)]
pub struct AppsScanArgs {}

#[derive(Args)]
pub struct AppsMapArgs {
    /// Domain to map (e.g., whatsapp.com)
    pub domain: String,
    /// macOS bundle ID (e.g., net.whatsapp.WhatsApp)
    pub bundle_id: String,
    /// App display name (optional, auto-detected if omitted)
    #[arg(long)]
    pub name: Option<String>,
}

#[derive(Args)]
pub struct AppsUnmapArgs {
    /// Domain to unmap
    pub domain: String,
    /// Bundle ID to unmap
    pub bundle_id: String,
}

#[derive(Args)]
pub struct AppsRestoreArgs {}
