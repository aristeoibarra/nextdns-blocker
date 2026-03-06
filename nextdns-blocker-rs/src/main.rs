use clap::Parser;

mod api;
mod cli;
mod common;
mod config;
mod db;
mod error;
mod handlers;
mod notifications;
mod output;
mod pending;
mod protection;
mod retry;
mod scheduler;
mod sync;
mod types;
mod watchdog;

use cli::{Cli, Commands, generate_completions};
use error::ExitCode;

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let cli = Cli::parse();
    let format = cli.output.resolve();

    if cli.verbose {
        tracing_subscriber::fmt()
            .with_env_filter("ndb=debug")
            .with_writer(std::io::stderr)
            .init();
    }

    if let Commands::Completions { shell } = &cli.command {
        generate_completions(*shell);
        return std::process::ExitCode::SUCCESS;
    }

    let result = run(cli.command, format).await;

    match result {
        Ok(code) => code.into(),
        Err(err) => {
            let code = err.exit_code();
            output::render_error(&err, "unknown", format);
            code.into()
        }
    }
}

async fn run(command: Commands, format: types::ResolvedFormat) -> Result<ExitCode, error::AppError> {
    match command {
        Commands::Init(args) => handlers::init::handle(args, format).await,
        Commands::Status(args) => handlers::status::handle(args, format),
        Commands::Sync(args) => handlers::sync::handle(args, format).await,
        Commands::Unblock(args) => handlers::unblock::handle(args, format).await,
        Commands::Fix(args) => handlers::fix::handle(args, format),
        Commands::Denylist(cmd) => handlers::denylist::handle(cmd, format),
        Commands::Allowlist(cmd) => handlers::allowlist::handle(cmd, format),
        Commands::Category(cmd) => handlers::category::handle(cmd, format),
        Commands::Nextdns(cmd) => handlers::nextdns::handle(cmd, format),
        Commands::Config(cmd) => handlers::config::handle(cmd, format),
        Commands::Pending(cmd) => handlers::pending::handle(cmd, format),
        Commands::Protection(cmd) => handlers::protection::handle(cmd, format),
        Commands::Watchdog(cmd) => handlers::watchdog::handle(cmd, format).await,
        Commands::Schema(cmd) => handlers::schema::handle(cmd, format),
        Commands::Completions { .. } => unreachable!("handled before run()"),
    }
}
