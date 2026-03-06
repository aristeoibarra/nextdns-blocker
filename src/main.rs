use clap::Parser;

use nextdns_blocker::cli::{Cli, Commands};
use nextdns_blocker::error::ExitCode;
use nextdns_blocker::handlers;
use nextdns_blocker::output;

fn main() -> std::process::ExitCode {
    let cli = Cli::parse();

    let result = run(cli.command);

    match result {
        Ok(code) => code.into(),
        Err(err) => {
            let code = err.exit_code();
            output::render_error(&err, "unknown");
            code.into()
        }
    }
}

fn run(command: Commands) -> Result<ExitCode, nextdns_blocker::error::AppError> {
    match command {
        Commands::Init(args) => handlers::init::handle(args),
        Commands::Status(args) => handlers::status::handle(args),
        Commands::Sync(args) => handlers::sync::handle(args),
        Commands::Block(args) => handlers::block::handle(args),
        Commands::Unblock(args) => handlers::unblock::handle(args),
        Commands::Fix(args) => handlers::fix::handle(args),
        Commands::Apps(cmd) => handlers::apps::handle(cmd),
        Commands::Denylist(cmd) => handlers::denylist::handle(cmd),
        Commands::Allowlist(cmd) => handlers::allowlist::handle(cmd),
        Commands::Category(cmd) => handlers::category::handle(cmd),
        Commands::Nextdns(cmd) => handlers::nextdns::handle(cmd),
        Commands::Config(cmd) => handlers::config::handle(cmd),
        Commands::Pending(cmd) => handlers::pending::handle(cmd),
        Commands::Audit(cmd) => handlers::audit::handle(cmd),
        Commands::Watchdog(cmd) => handlers::watchdog::handle(cmd),
        Commands::Schema(cmd) => handlers::schema::handle(cmd),
    }
}
