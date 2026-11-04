"""Private OAuth credentials and durable Tasks links; never returned as workspace data."""
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

_path = None


def configure(path):
    global _path
    _path = path


@contextmanager
def database():
    path = Path(_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS google_accounts (user_id TEXT PRIMARY KEY, secret TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS google_task_links (user_id TEXT, account TEXT, handover_id TEXT, item_id TEXT, payload TEXT NOT NULL, PRIMARY KEY(user_id,account,handover_id,item_id))')
        db.execute('CREATE TABLE IF NOT EXISTS google_batch_runs (day TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS google_leases (name TEXT PRIMARY KEY, owner TEXT, expires REAL)')
        db.commit()
        yield db
        db.commit()
    finally:
        db.close()


def cipher():
    # The key must travel with the private data backup, never with the repository.
    path = Path(_path()).parent / 'google-oauth.key'
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(Fernet.generate_key())
        except FileExistsError:
            pass
    return Fernet(path.read_bytes())


def account(user_id):
    with database() as db:
        row = db.execute('SELECT secret FROM google_accounts WHERE user_id=?', (user_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(cipher().decrypt(row[0].encode()))
    except (InvalidToken, ValueError):
        raise HTTPException(409, '저장된 Google 연결을 읽지 못했습니다. 연결을 해제한 뒤 다시 연결해 주세요.')


def save_account(user_id, value):
    with database() as db:
        secret = cipher().encrypt(json.dumps(value).encode()).decode()
        db.execute('INSERT OR REPLACE INTO google_accounts VALUES (?,?)', (user_id, secret))


def delete_account(user_id):
    with database() as db:
        db.execute('DELETE FROM google_accounts WHERE user_id=?', (user_id,))


def links(user_id, account_id, handover_id):
    with database() as db:
        rows = db.execute('SELECT item_id,payload FROM google_task_links WHERE user_id=? AND account=? AND handover_id=?', (user_id, account_id, handover_id)).fetchall()
    return {key: json.loads(value) for key, value in rows}


def save_link(user_id, account_id, handover_id, item_id, value):
    with database() as db:
        db.execute('INSERT OR REPLACE INTO google_task_links VALUES (?,?,?,?,?)', (user_id, account_id, handover_id, item_id, json.dumps(value, ensure_ascii=False)))


def targets():
    with database() as db:
        return db.execute('SELECT DISTINCT user_id,account,handover_id FROM google_task_links').fetchall()


def batch_run(day, value=None):
    with database() as db:
        if value is not None:
            db.execute('INSERT OR REPLACE INTO google_batch_runs VALUES (?,?)', (day, json.dumps(value, ensure_ascii=False)))
        row = db.execute('SELECT payload FROM google_batch_runs WHERE day=?', (day,)).fetchone()
    return json.loads(row[0]) if row else None


def acquire(name, seconds=180):
    owner = uuid.uuid4().hex
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT expires FROM google_leases WHERE name=?', (name,)).fetchone()
        if row and row[0] > time.time():
            return None
        db.execute('INSERT OR REPLACE INTO google_leases VALUES (?,?,?)', (name, owner, time.time()+seconds))
    return owner


def renew(name, owner, seconds=180):
    with database() as db:
        return db.execute('UPDATE google_leases SET expires=? WHERE name=? AND owner=?', (time.time()+seconds, name, owner)).rowcount == 1


def release(name, owner):
    with database() as db:
        db.execute('DELETE FROM google_leases WHERE name=? AND owner=?', (name, owner))
