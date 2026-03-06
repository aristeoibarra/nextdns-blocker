use clap::Parser;

use nextdns_blocker::cli::{Cli, Commands};
use nextdns_blocker::error::ExitCode;
use nextdns_blocker::handlers;
use nextdns_blocker::output;
use nextdns_blocker::types::ResolvedFormat;

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let cli = Cli::parse();
    let format = cli.output.resolve();

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

async fn run(command: Commands, format: ResolvedFormat) -> Result<ExitCode, nextdns_blocker::error::AppError> {
    match command {
        Commands::Init(args) => handlers::init::handle(args, format),
        Commands::Status(args) => handlers::status::handle(args, format),
        Commands::Sync(args) => handlers::sync::handle(args, format).await,
        Commands::Unblock(args) => handlers::unblock::handle(args, format),
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
    }
}
