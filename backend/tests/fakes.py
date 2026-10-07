"""ของปลอมที่ใช้ร่วมกันในการทดสอบ"""

from __future__ import annotations

import hashlib
import math


class HashEmbedder:
    """
    embedding แบบกำหนดผลได้แน่นอน: นับ character 3-gram ลงถัง 128 ช่องแล้ว normalize
    ข้อความที่มีคำซ้ำกันมากจะได้ cosine สูง — พอให้ทดสอบลำดับผลค้นหาได้โดยไม่ต้องโหลดโมเดลจริง
    """

    dim = 128

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            clean = "".join(text.lower().split())
            for i in range(max(1, len(clean) - 2)):
                gram = clean[i : i + 3]
                vec[int(hashlib.md5(gram.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors
