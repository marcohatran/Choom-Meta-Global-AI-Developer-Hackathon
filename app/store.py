"""Persistence: Firestore in production, in-memory for local dev and tests (STORE=memory)."""

import os
import time
import uuid
from datetime import datetime, timezone

MEMORY = os.environ.get("STORE", "firestore") == "memory"


def now() -> float:
    return time.time()


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class MemoryStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def get(self, path: str) -> dict | None:
        d = self.docs.get(path)
        return dict(d) if d else None

    async def set(self, path: str, data: dict, merge: bool = True):
        self.docs[path] = {**(self.docs.get(path) or {}), **data} if merge else dict(data)

    async def add(self, coll: str, data: dict) -> str:
        i = uuid.uuid4().hex[:16]
        self.docs[f"{coll}/{i}"] = {**data, "id": i}
        return i

    async def list(self, coll: str, limit: int = 50) -> list[dict]:
        pre = coll + "/"
        rows = [v for k, v in self.docs.items() if k.startswith(pre) and "/" not in k[len(pre):]]
        return sorted(rows, key=lambda r: r.get("created", 0), reverse=True)[:limit]

    async def incr(self, path: str, field: str, by: int = 1) -> int:
        d = self.docs.setdefault(path, {})
        d[field] = d.get(field, 0) + by
        return d[field]


class FirestoreStore:
    def __init__(self):
        from google.cloud import firestore
        self.fs = firestore
        self.db = firestore.AsyncClient(database=os.environ.get("FIRESTORE_DB", "choom-muse"))

    async def get(self, path: str) -> dict | None:
        snap = await self.db.document(path).get()
        return snap.to_dict() if snap.exists else None

    async def set(self, path: str, data: dict, merge: bool = True):
        await self.db.document(path).set(data, merge=merge)

    async def add(self, coll: str, data: dict) -> str:
        ref = self.db.collection(coll).document()
        await ref.set({**data, "id": ref.id})
        return ref.id

    async def list(self, coll: str, limit: int = 50) -> list[dict]:
        q = self.db.collection(coll).order_by("created", direction=self.fs.Query.DESCENDING).limit(limit)
        return [d.to_dict() async for d in q.stream()]

    async def incr(self, path: str, field: str, by: int = 1) -> int:
        ref = self.db.document(path)
        await ref.set({field: self.fs.Increment(by)}, merge=True)
        return ((await ref.get()).to_dict() or {}).get(field, by)


db = MemoryStore() if MEMORY else FirestoreStore()
