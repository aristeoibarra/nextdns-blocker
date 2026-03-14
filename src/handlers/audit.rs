use crate::cli::audit::*;
use crate::db::audit::AuditFilter;
use crate::db::Database;
use crate::error::{AppError, ExitCode};
use crate::output::{self, Renderable};

pub fn handle(cmd: AuditCommands) -> Result<ExitCode, AppError> {
    let db = Database::open(&crate::common::platform::db_path())?;
    match cmd {
        AuditCommands::List(args) => handle_list(&db, args),
        AuditCommands::Clean(args) => handle_clean(&db, args),
    }
}

fn handle_list(db: &Database, args: AuditListArgs) -> Result<ExitCode, AppError> {
    let filter = AuditFilter {
        domain: args.domain,
        action: args.action,
        source: args.source,
    };
    let entries = db.with_conn(|conn| crate::db::audit::list_audit(conn, args.limit, args.offset, &filter))?;
    let total = db.with_conn(|conn| crate::db::audit::count_audit(conn, &filter))?;
    let result = AuditListResult { entries, total };
    output::render(&result);
    Ok(ExitCode::Success)
}

fn handle_clean(db: &Database, args: AuditCleanArgs) -> Result<ExitCode, AppError> {
    let cutoff = crate::common::time::now_unix() - (args.older_than as i64 * 86_400);
    let deleted = db.with_conn(|conn| crate::db::audit::clean_old_entries(conn, cutoff))?;
    let result = AuditCleanResult { deleted, older_than_days: args.older_than };
    output::render(&result);
    Ok(ExitCode::Success)
}

struct AuditCleanResult { deleted: usize, older_than_days: u64 }
impl Renderable for AuditCleanResult {
    fn command_name(&self) -> &str { "audit clean" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "deleted": self.deleted, "older_than_days": self.older_than_days }
        })
    }
}

struct AuditListResult { entries: Vec<crate::types::AuditEntry>, total: i64 }
impl Renderable for AuditListResult {
    fn command_name(&self) -> &str { "audit list" }
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "data": { "entries": self.entries },
            "summary": { "returned": self.entries.len(), "total": self.total }
        })
    }
}
