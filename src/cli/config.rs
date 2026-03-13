use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum ConfigCommands {
    /// Show current configuration
    Show(ConfigShowArgs),
    /// Set a configuration value
    Set(ConfigSetArgs),
    /// Store a secret in .env file
    SetSecret(ConfigSetSecretArgs),
    /// Remove a secret from .env file
    RemoveSecret(ConfigRemoveSecretArgs),
    /// Validate configuration
    Validate(ConfigValidateArgs),
    /// Send a test notification
    TestNotification(ConfigTestNotificationArgs),
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
pub struct ConfigSetSecretArgs {
    /// Secret name (api-key or profile-id)
    pub name: String,
    /// Secret value
    pub value: String,
}

#[derive(Args)]
pub struct ConfigRemoveSecretArgs {
    /// Secret name (api-key or profile-id)
    pub name: String,
}

#[derive(Args)]
pub struct ConfigValidateArgs {}

#[derive(Args)]
pub struct ConfigTestNotificationArgs {}
