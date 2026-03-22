import json
import threading
import time
from dataclasses import asdict, fields

from .engine import CHALLENGE_TTL, Challenge, Engine, Policy, Rule


class RedisStore:
    def __init__(self, client, prefix="tollbooth", ttl=CHALLENGE_TTL):
        self._r = client
        self._prefix = prefix
        self._ttl = ttl

    def _key(self, cid):
        return f"{self._prefix}:c:{cid}"

    def set(self, challenge):
        elapsed = time.time() - challenge.created_at
        remaining = max(1, int(self._ttl - elapsed))
        self._r.set(
            self._key(challenge.id),
            json.dumps(
                {
                    "id": challenge.id,
                    "random_data": challenge.random_data,
                    "difficulty": challenge.difficulty,
                    "ip_hash": challenge.ip_hash,
                    "created_at": challenge.created_at,
                    "spent": challenge.spent,
                }
            ),
            ex=remaining,
        )

    def get(self, cid):
        raw = self._r.get(self._key(cid))
        if not raw:
            return None
        return Challenge(**json.loads(raw))


class RedisEngine(Engine):
    def __init__(
        self,
        client,
        *,
        secret=None,
        prefix="tollbooth",
        auto_sync=True,
        **kwargs,
    ):
        self._r = client
        self._prefix = prefix
        self._channel = f"{prefix}:sync"

        secret = self._resolve_secret(secret)
        super().__init__(secret, **kwargs)
        self._push_config()

        self.store = RedisStore(
            client,
            prefix,
            self.policy.challenge_ttl,
        )

        self._listener = None
        if auto_sync:
            self._start_listener()

    def _rkey(self, name):
        return f"{self._prefix}:{name}"

    def _resolve_secret(self, secret):
        key = self._rkey("secret")
        if secret:
            val = secret.encode() if isinstance(secret, str) else secret
            self._r.set(key, val)
            return val

        stored = self._r.get(key)
        if stored:
            return stored if isinstance(stored, bytes) else stored.encode()
        raise ValueError("No secret provided and none found in Redis")

    def _push_config(self):
        cfg = {
            f.name: getattr(self.policy, f.name)
            for f in fields(Policy)
            if f.name != "rules"
        }
        self._r.set(self._rkey("config"), json.dumps(cfg))
        self._r.set(
            self._rkey("rules"),
            json.dumps([asdict(r) for r in self.policy.rules]),
        )

    def _pull_config(self):
        raw_cfg = self._r.get(self._rkey("config"))
        raw_rules = self._r.get(self._rkey("rules"))
        if not raw_cfg or not raw_rules:
            return

        for k, v in json.loads(raw_cfg).items():
            setattr(self.policy, k, v)

        self.policy.rules = [Rule(**r) for r in json.loads(raw_rules)]

    def sync(self):
        stored = self._r.get(self._rkey("secret"))
        if stored:
            self.secret = stored if isinstance(stored, bytes) else stored.encode()
        self._pull_config()

    def update_secret(self, secret):
        self.secret = secret.encode() if isinstance(secret, str) else secret
        self._r.set(self._rkey("secret"), self.secret)
        self._r.publish(self._channel, "secret")

    def update_policy(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self.policy, k, v)
        self._push_config()
        self._r.publish(self._channel, "config")

    def update_rules(self, rules):
        self.policy.rules = rules
        self._push_config()
        self._r.publish(self._channel, "rules")

    def _start_listener(self):
        def listen():
            ps = self._r.pubsub()
            ps.subscribe(self._channel)
            for msg in ps.listen():
                if msg["type"] == "message":
                    self.sync()

        thread = threading.Thread(
            target=listen,
            daemon=True,
        )
        thread.start()
        self._listener = thread
