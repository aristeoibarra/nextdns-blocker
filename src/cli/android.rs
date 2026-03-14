use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum AndroidCommands {
    /// Compute blocked packages, push to Firebase, and show status
    Sync(AndroidSyncArgs),
    /// Pull installed apps from Android device and update local mappings
    Scan(AndroidScanArgs),
    /// List current Android package mappings
    List(AndroidListArgs),
}

#[derive(Args)]
pub struct AndroidSyncArgs {}

#[derive(Args)]
pub struct AndroidScanArgs {}

#[derive(Args)]
pub struct AndroidListArgs {}
