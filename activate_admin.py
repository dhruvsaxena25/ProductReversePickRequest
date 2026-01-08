#!/usr/bin/env python3
"""
Reactivate Admin User Script
Directly updates database to set admin user as active
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database connection string
DATABASE_URL = "sqlite:///storage/db/warehouse.db"  # Change if using PostgreSQL/MySQL

def reactivate_admin():
    """Reactivate the admin user directly in database"""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Update admin user to active
        result = session.execute(
            text("UPDATE users SET is_active = 1 WHERE username = :username"),
            {"username": "admin"}
        )

        session.commit()

        if result.rowcount > 0:
            print("✅ SUCCESS: Admin user reactivated!")
            print("You can now log in again.")
        else:
            print("❌ ERROR: Admin user not found in database")
            print("Please check if username is correct")

        session.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\nMake sure:")
        print("1. Database file exists")
        print("2. You're in the correct directory")
        print("3. Database is not locked by another process")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("REACTIVATE ADMIN USER")
    print("=" * 60)
    print()
    reactivate_admin()
    print()
    print("=" * 60)