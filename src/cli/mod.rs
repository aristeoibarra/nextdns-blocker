pub mod allowlist;
pub mod apps;
pub mod audit;
pub mod block;
pub mod category;
pub mod config;
pub mod denylist;
pub mod fix;
pub mod hosts;
pub mod init;
pub mod nextdns;
pub mod pending;
pub mod schema;
pub mod status;
pub mod sync;
pub mod unblock;
pub mod watchdog;

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "ndb",
    version = env!("CARGO_PKG_VERSION"),
    about = "NextDNS domain blocker with scheduling and notifications",
    long_about = None,
    after_help = "Use `ndb <command> --help` for more information about a command."
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Initialize ndb configuration and database
    Init(init::InitArgs),

    /// Show current status of all blocking rules
    Status(status::StatusArgs),

    /// Sync local configuration to NextDNS API
    Sync(sync::SyncArgs),

    /// Block one or more domains
    Block(block::BlockArgs),

    /// Unblock a domain or category
    Unblock(unblock::UnblockArgs),

    /// Diagnose and fix common issues
    Fix(fix::FixArgs),

    /// Manage app mappings and local app blocking
    #[command(subcommand)]
    Apps(apps::AppsCommands),

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

    /// View audit log
    #[command(subcommand)]
    Audit(audit::AuditCommands),

    /// Manage the watchdog scheduler service
    #[command(subcommand)]
    Watchdog(watchdog::WatchdogCommands),

    /// Manage /etc/hosts blocking entries
    #[command(subcommand)]
    Hosts(hosts::HostsCommands),

    /// Introspect command schemas and output formats
    #[command(subcommand)]
    Schema(schema::SchemaCommands),
}
