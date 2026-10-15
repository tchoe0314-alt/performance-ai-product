"""Atomic shared sliding-window limits using the application's existing DB.

No Redis/new service is assumed. No raw IP, email or bearer token is persisted.
Storage/policy errors fail closed; no process-local bypass or active eviction.
"""
import hashlib
import json
import math
import time


class RateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, math.ceil(retry_after))


class RateLimitUnavailable(Exception):
    pass


class RateLimitStore:
    def __init__(self, db, *, max_buckets=10000):
        if type(max_buckets) is not int or not 1 <= max_buckets <= 100000:
            raise ValueError("Invalid rate-limit capacity.")
        self.db=db; self.max_buckets=max_buckets

    def consume(self, bucket, identity, *, limit, window_seconds, now=None):
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("Rate limit must be an integer from1 to10000.")
        if type(window_seconds) is not int or not 1 <= window_seconds <= 86400:
            raise ValueError("Rate window must be an integer from1 to86400 seconds.")
        if not isinstance(bucket,str) or not bucket or len(bucket)>100 or not isinstance(identity,str) or not identity or len(identity)>1024:
            raise ValueError("Invalid rate-limit identity.")
        if now is not None and (type(now) not in (int,float) or not math.isfinite(now)):
            raise ValueError("Invalid rate-limit clock.")
        digest=hashlib.sha256(json.dumps([bucket,identity],separators=(",",":")).encode()).hexdigest()
        connection=None
        try:
            connection=self.db.connect()
            postgres=self.db.storage_kind=="postgres"
            if not postgres:connection.execute("BEGIN IMMEDIATE")
            suffix=" FOR UPDATE" if postgres else ""
            query="SELECT * FROM rate_limit_buckets WHERE identity_digest=?"+suffix
            row=connection.execute(query,(digest,)).fetchone()
            if row is None:
                # Only admission of new identities needs the global capacity lock.
                control=connection.execute("SELECT singleton_id FROM rate_limit_control WHERE singleton_id=1"+suffix).fetchone()
                if control is None:raise RateLimitUnavailable("Rate-limit capacity control is missing.")
                row=connection.execute(query,(digest,)).fetchone()
            # Read DB time AFTER waiting for row locks, otherwise a concurrent
            # replica can legitimately have committed an event after our clock.
            current=float(now if now is not None else connection.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp())").fetchone()[0] if postgres else time.time())
            if not math.isfinite(current):raise RateLimitUnavailable("Invalid shared rate-limit clock.")
            if row is None:
                connection.execute("DELETE FROM rate_limit_buckets WHERE expires_at<=?",(current,))
                count=connection.execute("SELECT COUNT(*) FROM rate_limit_buckets").fetchone()[0]
                if count>=self.max_buckets:raise RateLimitUnavailable("Rate-limit capacity reached.")
            events=[]
            if row is not None:
                if row["expires_at"] > current and (row["limit_count"] != limit or row["window_seconds"] != window_seconds):
                    raise RateLimitUnavailable("Rate-limit replicas have inconsistent policy.")
                if len(row["events_json"])>400000:raise RateLimitUnavailable("Invalid rate-limit state size.")
                events=json.loads(row["events_json"])
                if not isinstance(events,list) or any(type(value) not in (int,float) or not math.isfinite(value) for value in events):
                    raise RateLimitUnavailable("Invalid rate-limit state.")
                if events != sorted(events) or len(events)>10000:
                    raise RateLimitUnavailable("Invalid rate-limit state.")
                if events and events[-1]>current:raise RateLimitUnavailable("Rate-limit clock moved backwards.")
                events=[value for value in events if value>current-window_seconds]
            if len(events)>=limit:raise RateLimitExceeded(events[0]+window_seconds-current)
            events.append(current)
            connection.execute("""INSERT INTO rate_limit_buckets
                (identity_digest,events_json,expires_at,limit_count,window_seconds) VALUES (?,?,?,?,?)
                ON CONFLICT(identity_digest) DO UPDATE SET events_json=excluded.events_json,
                    expires_at=excluded.expires_at,limit_count=excluded.limit_count,window_seconds=excluded.window_seconds""",
                (digest,json.dumps(events),current+window_seconds,limit,window_seconds))
            connection.commit()
        except (RateLimitExceeded,RateLimitUnavailable):
            if connection is not None:connection.rollback()
            raise
        except Exception as exc:
            if connection is not None:connection.rollback()
            raise RateLimitUnavailable("Rate-limit storage unavailable.") from exc
        finally:
            if connection is not None:connection.close()
