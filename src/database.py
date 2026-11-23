"""Connect to the project MySQL instance and load one validated release set."""
import csv
import getpass
import os
from pathlib import Path
import subprocess

import mysql.connector

HOST = os.getenv("JOBBANK_MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("JOBBANK_MYSQL_PORT", "3307"))
DATABASE = os.getenv("JOBBANK_MYSQL_DATABASE", "jobbank")


def connect(role="loader"):
    user = os.getenv(f"JOBBANK_{role.upper()}_USER", f"jobbank_{role}")
    password = os.getenv(f"JOBBANK_{role.upper()}_PASSWORD")
    if password is None and os.name == "nt" and HOST in ("localhost", "127.0.0.1") and PORT == 3307:
        credential = Path(os.environ["LOCALAPPDATA"]) / "JobBankMySQL" / "instance" / f"jobbank_{role}.xml"
        if user == f"jobbank_{role}" and credential.is_file():
            password = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "(Import-Clixml -LiteralPath $env:JOBBANK_CREDENTIAL_FILE).GetNetworkCredential().Password"],
                env={**os.environ, "JOBBANK_CREDENTIAL_FILE": str(credential)}, text=True,
            ).rstrip("\r\n")
    if password is None:
        password = getpass.getpass(f"MySQL password for {user}: ")
    options = {}
    if os.getenv("JOBBANK_MYSQL_CA"):
        options.update(ssl_ca=os.environ["JOBBANK_MYSQL_CA"], ssl_verify_cert=True, ssl_verify_identity=True)
    return mysql.connector.connect(host=HOST, port=PORT, database=DATABASE, user=user,
                                   password=password, charset="utf8mb4", **options)


def create_schema(cursor, columns, dtype, analysis):
    fields = ",\n".join(f"{k} {dtype(k)}" for k in columns)
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS postings (
        {fields}, PRIMARY KEY(snapshot_id), UNIQUE(release_month,source_record),
        INDEX idx_month_noc(posting_month,noc),
        INDEX idx_month_place(posting_month,province,economic_region)
        ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS releases (
        release_month CHAR(7) PRIMARY KEY, filename VARCHAR(255), url TEXT, sha256 CHAR(64),
        bytes BIGINT UNSIGNED) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin""")
    execute_file(cursor, analysis.with_name("relational.sql"))
    execute_file(cursor, analysis)


def execute_file(cursor, analysis):
    for statement in analysis.read_text(encoding="utf-8").split(";"):
        if statement.strip():
            cursor.execute(statement)


def reload(cursor, tmp, columns):
    cursor.execute("DELETE FROM postings")
    cursor.execute("DELETE FROM releases")
    with (tmp / "sources.csv").open(encoding="utf-8", newline="") as f:
        source = csv.reader(f)
        next(source)
        cursor.executemany("INSERT INTO releases VALUES (%s,%s,%s,%s,%s)", list(source))
    fields = ",".join(columns)
    slots = ",".join(["%s"] * len(columns))
    statement = f"INSERT INTO postings ({fields}) VALUES ({slots})"
    with (tmp / "postings.csv").open(encoding="utf-8", newline="") as f:
        source = csv.reader(f)
        assert next(source) == columns
        from itertools import islice
        while batch := list(islice(source, 700)):
            cursor.executemany(statement, [tuple(value or None for value in row) for row in batch])
