use argon2::Argon2;
use password_hash::{PasswordHash, PasswordHasher, PasswordVerifier, SaltString};

use crate::db::Database;
use crate::error::AppError;

/// Hash a PIN using Argon2id.
pub fn hash_pin(pin: &str) -> Result<String, AppError> {
    let salt = SaltString::generate(&mut password_hash::rand_core::OsRng);
    let argon2 = Argon2::default();
    let hash = argon2
        .hash_password(pin.as_bytes(), &salt)
        .map_err(|e| AppError::General {
            message: format!("Failed to hash PIN: {e}"),
            hint: None,
        })?;
    Ok(hash.to_string())
}

/// Verify a PIN against its hash.
pub fn verify_pin(pin: &str, hash: &str) -> Result<bool, AppError> {
    let parsed = PasswordHash::new(hash).map_err(|e| AppError::General {
        message: format!("Invalid stored PIN hash: {e}"),
        hint: None,
    })?;
    Ok(Argon2::default()
        .verify_password(pin.as_bytes(), &parsed)
        .is_ok())
}

/// Set a new PIN (requires current PIN if one exists).
pub fn set_pin(db: &Database, new_pin: &str, current_pin: Option<&str>) -> Result<(), AppError> {
    db.with_conn(|conn| {
        let has_pin = crate::db::pin::has_pin(conn)?;

        if has_pin {
            // Require current PIN
            let Some(current) = current_pin else {
                return Err(rusqlite::Error::InvalidQuery);
            };
            let hash = crate::db::pin::get_pin_hash(conn)?.expect("PIN exists");
            let valid =
                verify_pin(current, &hash).map_err(|_| rusqlite::Error::InvalidQuery)?;
            if !valid {
                return Err(rusqlite::Error::InvalidQuery);
            }
        }

        let new_hash = hash_pin(new_pin).map_err(|_| rusqlite::Error::InvalidQuery)?;
        crate::db::pin::set_pin_hash(conn, &new_hash)?;
        Ok(())
    })
    .map_err(|_| AppError::Permission {
        message: "Invalid current PIN".to_string(),
        hint: Some("Provide the correct current PIN with --current".to_string()),
    })
}

/// Verify PIN and create a session. Returns session ID.
pub fn verify_and_create_session(db: &Database, pin: &str) -> Result<String, AppError> {
    db.with_conn(|conn| {
        // Check lockout
        if crate::db::pin::is_locked_out(conn)? {
            return Err(rusqlite::Error::InvalidQuery);
        }

        let hash = crate::db::pin::get_pin_hash(conn)?
            .ok_or(rusqlite::Error::InvalidQuery)?;

        let valid = verify_pin(pin, &hash).map_err(|_| rusqlite::Error::InvalidQuery)?;

        if !valid {
            crate::db::pin::record_failed_attempt(conn)?;
            return Err(rusqlite::Error::InvalidQuery);
        }

        crate::db::pin::reset_failed_attempts(conn)?;

        let session_id = uuid::Uuid::new_v4().to_string();
        crate::db::pin::create_session(conn, &session_id)?;

        Ok(session_id)
    })
    .map_err(|_| AppError::Permission {
        message: "PIN verification failed".to_string(),
        hint: Some("Check PIN and try again. Too many attempts will lock you out.".to_string()),
    })
}
