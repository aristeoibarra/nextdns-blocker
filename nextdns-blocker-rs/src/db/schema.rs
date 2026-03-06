/// Return all migrations as (version, name, sql).
///
/// The initial migration SQL is embedded from the migrations/ directory.
/// The schema_migrations table is created in Database::migrate() bootstrap,
/// so we skip re-creating it here and just run the rest of the schema.
pub fn get_migrations() -> Vec<(i64, &'static str, &'static str)> {
    vec![(
        1,
        "initial",
        include_str!("../../migrations/001_initial.sql"),
    )]
}
