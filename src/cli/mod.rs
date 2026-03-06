pub mod allowlist;
pub mod category;
pub mod config;
pub mod denylist;
pub mod fix;
pub mod init;
pub mod nextdns;
pub mod pending;
pub mod protection;
pub mod schema;
pub mod status;
pub mod sync;
pub mod unblock;
pub mod watchdog;

use clap::{Parser, Subcommand};

use crate::types::OutputFormat;

#[derive(Parser)]
#[command(
    name = "ndb",
    version = env!("CARGO_PKG_VERSION"),
    about = "NextDNS domain blocker with scheduling, protection, and notifications",
    long_about = None,
    after_help = "Use `ndb <command> --help` for more information about a command."
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,

    /// Output format (auto, json, human)
    #[arg(long, global = true, default_value = "auto", env = "NDB_OUTPUT")]
    pub output: OutputFormat,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Initialize ndb configuration and database
    Init(init::InitArgs),

    /// Show current status of all blocking rules
    Status(status::StatusArgs),

    /// Sync local configuration to NextDNS API
    Sync(sync::SyncArgs),

    /// Temporarily unblock a domain or category
    Unblock(unblock::UnblockArgs),

    /// Diagnose and fix common issues
    Fix(fix::FixArgs),

    /// Manage the denylist (blocked domains)
    #[command(subcommand)]
    Denylist(denylist::DenylistCommands),

    /// Manage the allowlist (allowed domains)
    #[command(subcommand)]
    Allowlist(allowlist::AllowlistCommands),

    /// Manage domain categories
    #[command(subcommand)]
    Category(category::CategoryCommands),

    /// Manage NextDNS native categories and services
    #[command(subcommand)]
    Nextdns(nextdns::NextdnsCommands),

    /// View and modify configuration
    #[command(subcommand)]
    Config(config::ConfigCommands),

    /// Manage pending scheduled actions
    #[command(subcommand)]
    Pending(pending::PendingCommands),

    /// Manage protection settings and PIN
    #[command(subcommand)]
    Protection(protection::ProtectionCommands),

    /// Manage the watchdog scheduler service
    #[command(subcommand)]
    Watchdog(watchdog::WatchdogCommands),

    /// Introspect command schemas and output formats
    #[command(subcommand)]
    Schema(schema::SchemaCommands),
}
