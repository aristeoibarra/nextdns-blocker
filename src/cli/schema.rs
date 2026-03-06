use clap::{Args, Subcommand};

#[derive(Subcommand)]
pub enum SchemaCommands {
    /// List all available commands with their arguments
    Commands(SchemaCommandsArgs),
    /// Show the JSON output schema for a specific command
    Output(SchemaOutputArgs),
    /// Show all exit codes
    ExitCodes(SchemaExitCodesArgs),
    /// Show the JSON envelope format
    Envelope(SchemaEnvelopeArgs),
}

#[derive(Args)]
pub struct SchemaCommandsArgs {}

#[derive(Args)]
pub struct SchemaOutputArgs {
    /// Command path (e.g., "denylist add")
    pub command: Vec<String>,
}

#[derive(Args)]
pub struct SchemaExitCodesArgs {}

#[derive(Args)]
pub struct SchemaEnvelopeArgs {}
