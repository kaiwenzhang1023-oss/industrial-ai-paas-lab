"""Opt-in local SQLite control ledger; never automatically replays ambiguous business effects.

Not a distributed transaction with the external business system. SQLite stores no secrets.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from .recovery import decide

class LedgerConflict(ValueError): pass

class DurableLedger:
    def __init__(self, path):
        self.path = str(Path(path))
        with self._connect() as c:
            self._enable_wal(c)
            c.execute('''CREATE TABLE IF NOT EXISTS calls (
                tenant TEXT NOT NULL, principal TEXT NOT NULL, request_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
                created REAL NOT NULL, updated REAL NOT NULL,
                PRIMARY KEY (tenant, principal, request_key))''')
            c.execute('''CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL,
                principal TEXT NOT NULL, request_key TEXT NOT NULL,
                event TEXT NOT NULL, occurred REAL NOT NULL)''')
    def _connect(self):
        c=sqlite3.connect(self.path, timeout=10, isolation_level=None)
        c.execute('PRAGMA busy_timeout=10000')
        return c

    @staticmethod
    def _enable_wal(connection, timeout=10.0):
        # Multiple workers may construct the ledger for the same file at
        # startup. SQLite can return SQLITE_BUSY from journal_mode=WAL even
        # when busy_timeout is configured; retry this one-time mode change.
        deadline = time.monotonic() + timeout
        while True:
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                return
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if not any(token in message for token in ('locked', 'busy')):
                    raise
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.025)
    @staticmethod
    def fingerprint(tool, arguments):
        raw=json.dumps([tool,arguments],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
    def _event(self,c,tenant,principal,key,event,now):
        c.execute('INSERT INTO events(tenant,principal,request_key,event,occurred) VALUES(?,?,?,?,?)',(tenant,principal,key,event,now))
    def claim(self,tenant,principal,key,tool,arguments):
        if not all(isinstance(x,str) and x and len(x)<=256 for x in (tenant,principal,key,tool)):
            raise ValueError('INVALID_IDENTITY_OR_KEY')
        digest=self.fingerprint(tool,arguments)
        now=time.time()
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                row=c.execute('SELECT fingerprint,state,result FROM calls WHERE tenant=? AND principal=? AND request_key=?',(tenant,principal,key)).fetchone()
                if row:
                    if row[0]!=digest:
                        self._event(c,tenant,principal,key,'CONFLICT_DENIED',now)
                        c.execute('COMMIT')
                        raise LedgerConflict('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD')
                    action='RETURN_CACHED' if row[1]=='DONE' and row[2] is not None else 'DO_NOT_REPLAY'
                    self._event(c,tenant,principal,key,action,now)
                    c.execute('COMMIT')
                    return {'action':action,'result':json.loads(row[2]) if action=='RETURN_CACHED' else None}
                c.execute('INSERT INTO calls VALUES(?,?,?,?,?,?,?,?)',(tenant,principal,key,digest,'IN_PROGRESS',None,now,now))
                self._event(c,tenant,principal,key,'CLAIMED',now)
                c.execute('COMMIT')
                return {'action':'EXECUTE_ONCE','result':None}
            except Exception:
                if c.in_transaction: c.execute('ROLLBACK')
                raise
    def complete(self,tenant,principal,key,tool,arguments,result):
        digest=self.fingerprint(tool,arguments)
        payload=json.dumps(result,sort_keys=True,allow_nan=False)
        now=time.time()
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                row=c.execute('SELECT fingerprint,state,result FROM calls WHERE tenant=? AND principal=? AND request_key=?',(tenant,principal,key)).fetchone()
                if row is None or row[0]!=digest: raise LedgerConflict('MISSING_OR_MISMATCHED_CLAIM')
                if row[1]=='DONE':
                    if row[2]!=payload: raise LedgerConflict('RESULT_MISMATCH')
                elif row[1]=='IN_PROGRESS':
                    c.execute('UPDATE calls SET state=?,result=?,updated=? WHERE tenant=? AND principal=? AND request_key=?',('DONE',payload,now,tenant,principal,key))
                    self._event(c,tenant,principal,key,'RESULT_COMMITTED',now)
                else: raise LedgerConflict('INVALID_STATE')
                c.execute('COMMIT')
            except Exception:
                if c.in_transaction: c.execute('ROLLBACK')
                raise
    def inspect(self,tenant,principal,key,*,timeout=300):
        with self._connect() as c:
            row=c.execute('SELECT state,result,updated FROM calls WHERE tenant=? AND principal=? AND request_key=?',(tenant,principal,key)).fetchone()
        if row is None: return {'action':'NOT_FOUND'}
        decision=decide(row[0],max(0,time.time()-row[2]),timeout=timeout,persisted_result=row[1] is not None)
        return {'action':decision.action,'reason':decision.reason}
    def audit(self,tenant,principal,key):
        with self._connect() as c:
            return [r[0] for r in c.execute('SELECT event FROM events WHERE tenant=? AND principal=? AND request_key=? ORDER BY id',(tenant,principal,key))]
