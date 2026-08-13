# SARA v2 — ระบบสารบรรณการประชุมอัตโนมัติ

แปลงไฟล์เสียงประชุมเป็นรายงานการประชุมตามระเบียบสารบรรณ และ **ติดตามมติทุกข้อข้ามการประชุมจนกว่าจะปิดจ๊อบ**

v1 = อัดเสียง → สรุป → ยิงเมล → จบ
v2 = **Resolution (มติ) เป็น entity แกนกลาง** ที่มีวงจรชีวิตของตัวเองและอายุยืนกว่าการประชุมที่ให้กำเนิดมัน

รายละเอียดข้อกำหนดทั้งหมดอยู่ใน `business-docs/SARA_v2_Requirements.md`

---

## เริ่มใช้งานใน 3 คำสั่ง

```bash
cp .env.example .env        # ใส่ APP_AI4THAI_API_KEY และ SMTP ของจริง
docker compose up -d --build
# เปิด http://localhost:3000
```

`docker compose` จะรัน migration + สร้างข้อมูลตั้งต้นให้อัตโนมัติ (service `migrate`)

| บริการ | พอร์ต | หน้าที่ |
|---|---|---|
| frontend | 3000 | หน้าจอทั้งหมด (Next.js) |
| backend | 8000 | REST API · เอกสาร OpenAPI ที่ `/docs` |
| mcp_server | 8001 | ชั้น action — ทุกอีเมลออกทางนี้ทางเดียว |
| celery_worker | — | ถอดเสียง สกัดมติ จับคู่ข้ามการประชุม ส่งอีเมล |
| celery_beat | — | สแกนมติใกล้ครบกำหนดทุกเช้า สร้างรายการเตือนเข้าคิวรออนุมัติ |
| db · redis | 5432 · 6379 | PostgreSQL · คิวงาน |

> ถ้าเครื่องมี PostgreSQL ของตัวเองอยู่แล้ว พอร์ต 5432 จะชนกัน — แก้ port mapping ใน `docker-compose.yaml` เป็น `5433:5432`

---

## สถาปัตยกรรม

```mermaid
graph TD
    UI[Next.js · หน้าตรวจทาน/แดชบอร์ด] -->|1. อัปโหลดไฟล์เสียง| API[FastAPI]
    API -->|2. เก็บไฟล์| Storage[(Volume / object storage)]
    API -->|3. เข้าคิว| Redis[(Redis)]
    Redis -->|4. รับงาน| Worker[Celery worker]
    Worker -->|5. ถอดเสียง| ASR[AI4Thai ASR]
    Worker -->|6. สกัดมติ + จับคู่มติค้างของ series| LLM[AI4Thai Pathumma]
    Worker -->|7. บันทึกเป็น Proposal ที่ยังไม่มีผล| DB[(PostgreSQL)]
    UI -->|8. คนกดยืนยันทีละรายการ| API
    API -->|9. มติเปลี่ยนสถานะจริง + เก็บหลักฐาน| DB
    Beat[Celery beat] -->|10. เตือนก่อนครบกำหนด| DB
    UI -->|11. อนุมัติก่อนส่ง| MCP[MCP server]
    MCP -->|12. ส่งอีเมลรายบุคคล| SMTP[SMTP]
```

**จุดที่ต่างจากระบบสรุปประชุมทั่วไป:** ขั้นที่ 7–9 ระบบ *เสนอ* ได้อย่างเดียว มติไม่เปลี่ยนสถานะจนกว่าคนจะกดยืนยัน

---

## หลักการที่บังคับใช้ในโค้ด ไม่ใช่แค่ในเอกสาร

| หลักการ | บังคับที่ไหน |
|---|---|
| ASR ล้มเหลว = หยุด pipeline ไม่สร้างข้อมูลปลอม (FR-M2-04) | `app/services/asr.py` โยน `AsrError` · `app/workers/tasks.py` ตั้งสถานะ failed |
| ระบบปิดมติเองไม่ได้ (FR-M4-06 · §4.2) | `change_status(system_initiated=True)` ปฏิเสธ done/cancelled |
| ปิดมติต้องมีเหตุผลเสมอ | `app/services/resolutions.py` คืน 422 ถ้าเหตุผลว่าง |
| เปลี่ยนสถานะข้ามขั้นไม่ได้ | `ResolutionStatus.TRANSITIONS` ตาม §4.1 |
| ไม่เดาชื่อคนไทย (§12) | `extraction.resolve_person` คืน None เมื่อชื่อชนกัน แล้วสร้างข้อเสนอถามคนแทน |
| ข้อเสนอปิดมติที่ไม่มั่นใจถูกลดชั้น | `CLOSE_CONFIDENCE_FLOOR` ใน `extraction.py` |
| ห้ามสร้างวาระจากรายงานที่ยังไม่รับรอง (FR-M9-04) | `POST /series/{id}/agenda/generate` คืน 409 |
| ทุกอีเมลต้องผ่านการอนุมัติ (FR-M7-07) | `outbound_action.status` เริ่มที่ `pending_approval` เสมอ |

---

## ตรวจสอบก่อนส่งงาน

```bash
cd backend  && python -m unittest discover -s tests   # 24 เคส
cd frontend && npm run check && npm run lint && npm run build
```

---

## สิ่งที่ยังไม่ได้ทำ (พูดตามตรง)

| เรื่อง | สถานะ |
|---|---|
| **Auth / multi-tenancy (M10)** | ยังไม่มี — ผู้กระทำมาจากหัวข้อ `X-Actor` ซึ่งปลอมได้ **ต้องทำก่อนใช้งานจริง** |
| **Speaker diarization (FR-M2-06)** | ใช้ speaker label จาก ASR ถ้ามี ถ้าไม่มีให้เลขาฯ ระบุเองในหน้าตรวจทาน (fallback ที่ §M2 อนุญาต) ยังไม่ได้ต่อ pyannote |
| **Q&A แบบ semantic (§14 ข้อ 3)** | ใช้ n-gram ระดับตัวอักษร ยังไม่ได้ใช้ pgvector |
| **template .docx ขององค์กร** | รองรับผ่าน `AGENDA_TEMPLATE_PATH` / `MINUTES_TEMPLATE_PATH` แต่ยังไม่มีไฟล์ต้นแบบจริง |
| **create_jira_issue (FR-M7-05)** | เป็น stub ที่บอกตามตรงว่ายังไม่ได้ต่อระบบจริง |
| **วัดผลตาม §10** | ยังไม่ได้ทำ eval set 20 ไฟล์ ตัวเลข F1 / false close rate จึงยังเคลมไม่ได้ |

