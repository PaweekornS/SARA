"""
ดัชนีเวกเตอร์ของบันทึกการประชุมใน Qdrant — ใช้ค้นหาเชิงความหมายสำหรับถาม-ตอบ

เก็บเฉพาะเนื้อหาที่ไม่เปลี่ยนหลังประมวลผลเสร็จ: สรุปของการประชุม + บันทึกคำต่อคำ (sliding window)
action items แก้ไข/ติ๊กเสร็จได้ตลอด จึงอ่านสดจาก DB แทน (ดู services/qa.py)

ทุกจุดมี payload user_id / collection_id / meeting_id และทุกการค้นต้องกรองด้วย user_id เสมอ
ถ้า Qdrant หรือ embedding มีปัญหา ฟังก์ชันจะโยน VectorStoreError ให้ผู้เรียกถอยไปใช้การค้นแบบคำได้
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from qdrant_client import QdrantClient, models

from app.core.config import settings

logger = logging.getLogger(__name__)

WINDOW = 3
BATCH = 64


class VectorStoreError(RuntimeError):
    """Qdrant หรือ embedding ใช้งานไม่ได้"""


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """โหลดโมเดลครั้งแรกที่ใช้ (ช้าราว 1-2 วินาทีถ้ามีไฟล์ใน cache แล้ว)"""

    def __init__(self, model_name: str, cache_dir: str | None) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name, cache_dir=cache_dir or None)
        self.dim = len(next(iter(self._model.embed(["probe"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts, batch_size=BATCH)]


@dataclass
class Chunk:
    meeting_id: UUID
    kind: str  # summary | transcript
    text: str
    segment_id: UUID | None = None
    start_ms: int | None = None


@dataclass
class Hit:
    meeting_id: UUID
    kind: str
    text: str
    segment_id: UUID | None
    start_ms: int | None
    score: float


_lock = threading.Lock()
_client: QdrantClient | None = None
_embedder: Embedder | None = None
_ready_collection = False


def configure(client: QdrantClient | None = None, embedder: Embedder | None = None) -> None:
    """ใช้ใน test เพื่อแทนที่ด้วย Qdrant ในหน่วยความจำและ embedder ปลอม"""
    global _client, _embedder, _ready_collection
    _client, _embedder, _ready_collection = client, embedder, False


def _get() -> tuple[QdrantClient, Embedder]:
    global _client, _embedder, _ready_collection
    with _lock:
        try:
            if _embedder is None:
                _embedder = FastEmbedder(settings.EMBEDDING_MODEL, settings.EMBEDDING_CACHE_DIR)
            if _client is None:
                _client = QdrantClient(url=settings.QDRANT_URL, timeout=10)
            if not _ready_collection:
                _ensure_collection(_client, _embedder.dim)
                _ready_collection = True
        except Exception as err:  # noqa: BLE001
            raise VectorStoreError(f"เชื่อมต่อ Qdrant/embedding ไม่ได้: {err}") from err
    return _client, _embedder


def _ensure_collection(client: QdrantClient, dim: int) -> None:
    name = settings.QDRANT_COLLECTION
    if not client.collection_exists(name):
        client.create_collection(name, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
    for field in ("user_id", "collection_id", "meeting_id"):
        client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)


def _match(**fields: UUID) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key=k, match=models.MatchValue(value=str(v))) for k, v in fields.items()]
    )


def build_chunks(meeting_id: UUID, summary: str, segments: list) -> list[Chunk]:
    """segments คือ TranscriptSegment (หรืออะไรก็ได้ที่มี id, speaker_label, speaker_name, start_ms, text) เรียงตามเวลา"""
    chunks = [Chunk(meeting_id, "summary", summary)] if summary.strip() else []
    for i in range(0, len(segments), WINDOW - 1):
        part = segments[i : i + WINDOW]
        text = " ".join(f"{s.speaker_name or s.speaker_label}: {s.text}" for s in part)
        chunks.append(Chunk(meeting_id, "transcript", text, part[0].id, part[0].start_ms))
    return chunks


def index_meeting(user_id: UUID, collection_id: UUID, meeting_id: UUID, chunks: list[Chunk]) -> int:
    """แทนที่จุดเดิมทั้งหมดของการประชุมนี้ด้วยชุดใหม่ (เรียกซ้ำได้ไม่ซ้อนกัน)"""
    client, embedder = _get()
    try:
        client.delete(settings.QDRANT_COLLECTION, points_selector=_match(meeting_id=meeting_id))
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start : start + BATCH]
            vectors = embedder.embed([c.text for c in batch])
            client.upsert(
                settings.QDRANT_COLLECTION,
                points=[
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "user_id": str(user_id),
                            "collection_id": str(collection_id),
                            "meeting_id": str(meeting_id),
                            "kind": c.kind,
                            "text": c.text,
                            "segment_id": str(c.segment_id) if c.segment_id else None,
                            "start_ms": c.start_ms,
                        },
                    )
                    for c, vector in zip(batch, vectors)
                ],
            )
    except VectorStoreError:
        raise
    except Exception as err:  # noqa: BLE001
        raise VectorStoreError(f"บันทึกดัชนีไม่สำเร็จ: {err}") from err
    return len(chunks)


def search(user_id: UUID, collection_id: UUID, question: str, limit: int) -> list[Hit]:
    client, embedder = _get()
    try:
        vector = embedder.embed([question])[0]
        points = client.query_points(
            settings.QDRANT_COLLECTION,
            query=vector,
            query_filter=_match(user_id=user_id, collection_id=collection_id),
            limit=limit,
            score_threshold=settings.VECTOR_MIN_SCORE,
            with_payload=True,
        ).points
    except Exception as err:  # noqa: BLE001
        raise VectorStoreError(f"ค้นหาใน Qdrant ไม่สำเร็จ: {err}") from err

    return [
        Hit(
            meeting_id=UUID(p.payload["meeting_id"]),
            kind=p.payload["kind"],
            text=p.payload["text"],
            segment_id=UUID(p.payload["segment_id"]) if p.payload.get("segment_id") else None,
            start_ms=p.payload.get("start_ms"),
            score=p.score,
        )
        for p in points
    ]


def delete_meetings(meeting_ids: list[UUID]) -> None:
    """ลบแบบ best-effort — ถ้า Qdrant ล่ม จุดที่ค้างจะไม่ถูกค้นเจออยู่ดีเพราะ QA กรองด้วย meeting ที่ยังอยู่ใน DB"""
    if not meeting_ids:
        return
    try:
        client, _ = _get()
        client.delete(
            settings.QDRANT_COLLECTION,
            points_selector=models.Filter(
                must=[models.FieldCondition(key="meeting_id", match=models.MatchAny(any=[str(i) for i in meeting_ids]))]
            ),
        )
    except Exception as err:  # noqa: BLE001
        logger.warning("ลบดัชนีของการประชุม %s ไม่สำเร็จ: %s", meeting_ids, err)


def move_meeting(meeting_id: UUID, collection_id: UUID) -> None:
    try:
        client, _ = _get()
        client.set_payload(
            settings.QDRANT_COLLECTION,
            payload={"collection_id": str(collection_id)},
            points=_match(meeting_id=meeting_id),
        )
    except Exception as err:  # noqa: BLE001
        logger.warning("ย้ายดัชนีของการประชุม %s ไม่สำเร็จ: %s", meeting_id, err)
