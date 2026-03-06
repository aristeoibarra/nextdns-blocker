use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum HostsCommands {
    /// List /etc/hosts entries managed by ndb
    List(HostsListArgs),
    /// Configure sudoers for passwordless /etc/hosts access
    Setup(HostsSetupArgs),
    /// Remove all ndb entries from /etc/hosts
    Restore(HostsRestoreArgs),
}

#[derive(Args)]
pub struct HostsListArgs {}

#[derive(Args)]
pub struct HostsSetupArgs {}

#[derive(Args)]
pub struct HostsRestoreArgs {}
