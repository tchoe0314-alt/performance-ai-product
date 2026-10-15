"""Shared abuse limits against synthetic DBs, never hosted services."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from backend.services.database import Database
from backend.services.rate_limit_store import RateLimitExceeded,RateLimitStore,RateLimitUnavailable


class SharedRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="civora-rate-test-")
        self.path=Path(self.temp.name)/"synthetic.sqlite"
        self.db=Database(self.path,database_url="sqlite-local-only")
        self.store=RateLimitStore(self.db)

    def tearDown(self):self.temp.cleanup()

    def consume(self,identity="source",now=100,**kwargs):
        return self.store.consume("auth",identity,limit=kwargs.get("limit",2),window_seconds=60,now=now)

    def test_different_instances_share_exact_sliding_window(self):
        other=RateLimitStore(Database(self.path,database_url="sqlite-local-only"))
        self.consume(now=100)
        other.consume("auth","source",limit=2,window_seconds=60,now=130)
        with self.assertRaises(RateLimitExceeded) as error:self.consume(now=159)
        self.assertEqual(error.exception.retry_after,1)
        self.consume(now=160)  # first event, not entire bucket, expires
        with self.assertRaises(RateLimitExceeded) as error:self.consume(now=161)
        self.assertEqual(error.exception.retry_after,29)

    def test_concurrent_instances_cannot_each_claim_full_limit(self):
        instances=[RateLimitStore(Database(self.path,database_url="sqlite-local-only")) for _ in range(4)]
        def consume(index):
            try:instances[index%4].consume("auth","same",limit=5,window_seconds=60,now=100);return "allowed"
            except RateLimitExceeded:return "limited"
        with ThreadPoolExecutor(max_workers=8) as pool:outcomes=list(pool.map(consume,range(24)))
        self.assertEqual(outcomes.count("allowed"),5)
        self.assertEqual(outcomes.count("limited"),19)

    def test_capacity_does_not_evict_active_protection(self):
        self.store=RateLimitStore(self.db,max_buckets=2)
        self.consume("a");self.consume("b")
        with self.assertRaises(RateLimitUnavailable):self.consume("c")
        self.consume("a")
        with self.assertRaises(RateLimitExceeded):self.consume("a")
        self.consume("c",now=160)

    def test_persisted_identity_does_not_contain_email_or_ip(self):
        self.consume("account:synthetic@example.test")
        connection=self.db.connect()
        try:
            rows=connection.execute("SELECT identity_digest FROM rate_limit_buckets").fetchall()
            self.assertEqual(len(rows),1);self.assertEqual(len(rows[0][0]),64)
            self.assertNotIn("synthetic",rows[0][0])
        finally:connection.close()

    def test_corrupt_state_and_clock_rollback_fail_closed(self):
        self.consume()
        with self.assertRaises(RateLimitUnavailable):self.consume(now=99)
        connection=self.db.connect()
        try:
            connection.execute("UPDATE rate_limit_buckets SET events_json='[true]'");connection.commit()
        finally:connection.close()
        with self.assertRaises(RateLimitUnavailable):self.consume()

    def test_inconsistent_replica_policy_does_not_reset_active_bucket(self):
        self.consume()
        with self.assertRaises(RateLimitUnavailable):self.consume(limit=100)
        self.consume(now=160,limit=100)

    def test_storage_failure_never_falls_back_to_fresh_local_counters(self):
        class Broken:
            def connect(self):raise RuntimeError("synthetic storage outage")
        with self.assertRaises(RateLimitUnavailable):
            RateLimitStore(Broken()).consume("auth","source",limit=2,window_seconds=60)

    def test_invalid_limits_cannot_disable_protection(self):
        for limit in (True,0,-1,10001,1.5):
            with self.subTest(limit=limit),self.assertRaises(ValueError):self.consume(limit=limit)

    def test_postgres_clock_is_read_after_lock_query_not_before_wait(self):
        # SQL-order contract only; not a substitute for a real PostgreSQL race.
        calls=[]
        class Connection:
            def execute(self,sql,params=()):
                calls.append(sql)
                if "FROM rate_limit_buckets WHERE" in sql:
                    value={"events_json":"[100]","expires_at":160,"limit_count":2,"window_seconds":60}
                elif "clock_timestamp" in sql:value=(101,)
                else:value=None
                class Result:
                    def fetchone(self):return value
                return Result()
            def commit(self):pass
            def rollback(self):pass
            def close(self):pass
        class FakePostgres:
            storage_kind="postgres"
            def connect(self):return Connection()
        RateLimitStore(FakePostgres()).consume("auth","source",limit=2,window_seconds=60)
        self.assertIn("FOR UPDATE",calls[0])
        self.assertIn("clock_timestamp",calls[1])


if __name__=="__main__":unittest.main()
