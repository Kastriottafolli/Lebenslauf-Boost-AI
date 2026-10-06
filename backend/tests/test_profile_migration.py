"""The deployed profile schema expands additively without changing account credentials."""

from sqlalchemy import create_engine, inspect, text

from backend.account_migration import PROFILE_COLUMNS, migrate_account_profiles
from backend.database import Base
from backend.services.account_service import migrate_existing_accounts


def test_legacy_profile_expansion_is_idempotent_and_preserves_all_existing_values(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "old-profile.db"))
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE account_profiles (
            account_id VARCHAR(36) PRIMARY KEY, display_name VARCHAR(200) NOT NULL,
            first_name VARCHAR(100) NOT NULL, last_name VARCHAR(100) NOT NULL,
            phone VARCHAR(100) NOT NULL, location VARCHAR(300) NOT NULL,
            headline VARCHAR(300) NOT NULL, language VARCHAR(2) NOT NULL,
            email_notifications BOOLEAN NOT NULL, updated_at DATETIME NOT NULL)"""))
        connection.execute(text("""INSERT INTO account_profiles VALUES (
            'legacy', 'Preserved name', 'First', 'Last', '+491234', 'Berlin',
            'Original headline', 'sq', 1, '2025-01-02 03:04:05.123456')"""))
    migrate_account_profiles(engine)
    migrate_account_profiles(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM account_profiles")).mappings().one()
        assert row["display_name"] == "Preserved name" and row["language"] == "sq"
        assert row["phone"] == "+491234" and row["email_notifications"] == 1
        assert row["updated_at"] == "2025-01-02 03:04:05.123456"
        assert row["gender"] == "undisclosed" and row["date_of_birth"] is None
        assert row["spoken_languages"] == "[]"
        assert all(row[field] == "" for field in ("street", "postal_code", "city", "country"))
    assert set(PROFILE_COLUMNS).issubset({column["name"] for column in inspect(engine).get_columns("account_profiles")})
    engine.dispose()


def test_security_and_profile_gaps_are_independent_without_overwriting_existing_profiles(tmp_path):
    from sqlalchemy.orm import sessionmaker

    from backend.account_models import AccountProfile, AccountSecurity
    from backend.models import Account, AdminAccess

    engine = create_engine("sqlite:///" + str(tmp_path / "profile-gaps.db"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        legacy = Account(email="legacy@example.com", password_hash="legacy-hash", recovery_hash="legacy-recovery")
        pending = Account(email="pending@example.com", password_hash="pending-hash", recovery_hash="pending-recovery")
        admin = Account(email="info@tafolli.net", password_hash="admin-hash", recovery_hash="admin-recovery")
        db.add_all([legacy, pending, admin])
        db.flush()
        db.add_all([
            AccountProfile(account_id=legacy.id, first_name="Keep existing", city="Keep city", spoken_languages='["Deutsch"]'),
            AccountSecurity(account_id=pending.id, verification_source="email_pending", credential_version=2),
            AdminAccess(account_id=admin.id, enabled=True, secret_cipher="unchanged-mfa", last_counter=99),
        ])
        db.commit()
        ids = legacy.id, pending.id, admin.id
    migrate_existing_accounts(engine)
    migrate_existing_accounts(engine)
    with factory() as db:
        assert db.query(AccountProfile).count() == db.query(AccountSecurity).count() == 3
        assert db.get(AccountProfile, ids[0]).first_name == "Keep existing"
        assert db.get(AccountProfile, ids[0]).city == "Keep city"
        assert db.get(AccountProfile, ids[0]).spoken_languages == '["Deutsch"]'
        assert db.get(AccountSecurity, ids[0]).verification_source == "legacy_existing"
        assert db.get(AccountSecurity, ids[1]).verified_at is None
        assert db.get(AccountSecurity, ids[1]).credential_version == 2
        assert db.get(Account, ids[0]).password_hash == "legacy-hash"
        assert db.get(Account, ids[2]).password_hash == "admin-hash"
        assert db.get(AdminAccess, ids[2]).secret_cipher == "unchanged-mfa"
        assert db.get(AdminAccess, ids[2]).last_counter == 99
    engine.dispose()
