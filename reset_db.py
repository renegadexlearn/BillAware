import os
import sys
from pathlib import Path
import getpass

import pymysql
from dotenv import load_dotenv


def must_get(key: str) -> str:
    val = os.getenv(key)
    if not val or not str(val).strip():
        raise SystemExit(f"Missing required env var: {key}")
    return val.strip()


def opt_get(key: str, default: str) -> str:
    val = os.getenv(key)
    return val.strip() if val and str(val).strip() else default


def sql_escape(s: str) -> str:
    # Safe enough for SQL literals in DDL statements
    return s.replace("\\", "\\\\").replace("'", "''")


def q_ident(name: str) -> str:
    # Quote identifiers like database names
    return f"`{name.replace('`', '``')}`"


def connect_root(host: str, port: int, password: str):
    return pymysql.connect(
        host=host,
        port=port,
        user="root",
        password=password,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    # Load .env from same folder as this script
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)

    db_name = must_get("DB_NAME")
    app_user = must_get("DB_USER")
    app_pw = must_get("DB_PASSWORD")

    db_host = opt_get("DB_HOST", "localhost")
    db_port = int(opt_get("DB_PORT", "3306"))

    root_pw = os.getenv("DB_ROOT_PASSWORD")
    if not root_pw:
        # fallback prompt if not in .env
        root_pw = getpass.getpass("Enter MariaDB root password: ")

    # where the app user should be allowed to login from
    # - localhost for local CLI/socket connections
    # - % for Docker containers / remote connections
    user_hosts = ["localhost", "%"]

    print("⚠️  WARNING: This will DROP and RECREATE the database and reset app user privileges.")
    print(f"    DB Host:   {db_host}:{db_port}")
    print(f"    Target DB: {db_name}")
    print(f"    App User:  {app_user} @ {user_hosts}")
    confirm = input("\nType EXACTLY 'YES' to proceed: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        return

    try:
        conn = connect_root(db_host, db_port, root_pw)
    except Exception as e:
        raise SystemExit(f"❌ Cannot connect as root: {e}")

    dbn = q_ident(db_name)
    app_user_esc = sql_escape(app_user)
    app_pw_esc = sql_escape(app_pw)

    with conn:
        with conn.cursor() as cur:
            # Drop + create DB
            cur.execute(f"DROP DATABASE IF EXISTS {dbn};")
            cur.execute(f"CREATE DATABASE {dbn} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

            # Create/update user + grant permissions for each host
            for host in user_hosts:
                host_esc = sql_escape(host)

                cur.execute(
                    f"CREATE USER IF NOT EXISTS '{app_user_esc}'@'{host_esc}' "
                    f"IDENTIFIED BY '{app_pw_esc}';"
                )
                # Ensure password is as expected
                cur.execute(
                    f"ALTER USER '{app_user_esc}'@'{host_esc}' "
                    f"IDENTIFIED BY '{app_pw_esc}';"
                )

                # Grant privileges only to this DB
                cur.execute(
                    f"GRANT ALL PRIVILEGES ON {dbn}.* TO '{app_user_esc}'@'{host_esc}';"
                )

            cur.execute("FLUSH PRIVILEGES;")

    print("✅ Done.")
    print("Next steps:")
    print("  1) flask db init   (if migrations folder doesn't exist yet)")
    print("  2) flask db migrate -m \"initial\"")
    print("  3) flask db upgrade")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
