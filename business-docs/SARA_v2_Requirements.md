# SARA v2 — Requirement Analysis & Development Spec

| | |
|---|---|
| เอกสาร | Requirement Analysis / Product Spec |
| เวอร์ชัน | 2.0 (draft) |
| วันที่ | 11 สิงหาคม 2569 |
| สถานะ | ร่างเพื่อให้ทีม dev เริ่มพัฒนา |
| อ้างอิงเวอร์ชันก่อน | `PRODUCT_OVERVIEW.md`, `ARCHITECTURE.md`, `PROJECT_STATUS.md` (v1) |

---

## 0. สรุปสำหรับคนที่มีเวลา 2 นาที

SARA v1 = อัดเสียง → สรุป → ยิงเมล → จบ
SARA v2 = **ระบบติดตามมติที่ประชุม** ที่จำการประชุมครั้งก่อนได้ และปิดวงจรจนมติถูกดำเนินการเสร็จ

**สิ่งที่เปลี่ยนในเชิงสถาปัตยกรรม:** จากเดิมที่ meeting เป็น entity สูงสุดและถูกประมวลผลแยกกันเป็นเอกเทศ v2 ยก **Resolution (มติ)** ขึ้นเป็น entity ชั้นหนึ่งที่มีวงจรชีวิตของตัวเอง และมีอายุยืนกว่าการประชุมที่ให้กำเนิดมัน

**สิ่งที่ต้องสร้างใหม่ (เรียงตามความสำคัญ):**
1. Resolution lifecycle + cross-meeting linking engine
2. Auto-generated วาระสืบเนื่อง + .docx export ตามระเบียบสารบรรณ
3. Speaker diarization + person registry
4. Resolution dashboard
5. MCP action layer แบบมี time-based trigger

**สิ่งที่ต้องรื้อทิ้ง:** silent fallback transcript, hardcoded recipient list, monolithic `page.tsx`

---

## 1. Product definition

### 1.1 One-liner

> ระบบสารบรรณการประชุมอัตโนมัติ ที่แปลงไฟล์เสียงเป็นรายงานการประชุมตามระเบียบราชการ และติดตามมติทุกข้อข้ามการประชุมจนกว่าจะปิดจ๊อบ

### 1.2 ปัญหาที่แก้ (เรียงตามความเจ็บจริง)

| # | ปัญหา | ใครเจ็บ | วันนี้แก้ยังไง |
|---|---|---|---|
| P1 | ทำวาระสืบเนื่องต้องเปิดรายงานเก่าไล่เองทีละครั้ง | เลขาฯ | เปิด Word ย้อนหลัง 3–6 ไฟล์ |
| P2 | ไม่มีใครรู้ว่ามติที่ออกไปแล้ว ตายกลางทางกี่ข้อ | ประธาน/ผู้บริหาร | ไม่มีใครรู้จริง ๆ |
| P3 | คนรับผิดชอบจำไม่ได้ว่ารับปากอะไรไว้ | ผู้เข้าประชุม | รอเลขาฯ ส่งรายงาน (ซึ่งมักช้า) |
| P4 | จดรายงานตามระเบียบสารบรรณกินเวลา 2–4 ชม./ครั้ง | เลขาฯ | จดมือ + เรียบเรียงเอง |
| P5 | ข้อมูลประชุมลับ ส่งขึ้น cloud ต่างประเทศไม่ได้ | ฝ่ายกฎหมาย/IT | ไม่ใช้ AI เลย |

### 1.3 ขอบเขตผู้ใช้เป้าหมาย

การประชุมที่ **รายงานการประชุมมีผลผูกพันทางกฎหมาย** และมีลักษณะ **เป็นชุดต่อเนื่อง** (ประชุมครั้งที่ 1, 2, 3...) เช่น:
- คณะกรรมการในหน่วยงานรัฐ / อปท. / รัฐวิสาหกิจ
- สภามหาวิทยาลัย / สภาวิชาการ / คณะกรรมการหลักสูตร
- คณะกรรมการบริษัท / ที่ประชุมผู้ถือหุ้น
- นิติบุคคลอาคารชุด / หมู่บ้านจัดสรร
- สหกรณ์ / คณะกรรมการจริยธรรมการวิจัย

> **หมายเหตุออกแบบ:** เงื่อนไข "เป็นชุดต่อเนื่อง" สำคัญกว่า "เป็นราชการ" — ถ้าประชุมครั้งเดียวจบ ฟีเจอร์หลักของ v2 ไม่มีประโยชน์เลย ทุก decision ในสเปกนี้ให้ยึดเงื่อนไขนี้เป็นหลัก

### 1.4 Persona

**A. เลขานุการที่ประชุม (ผู้ใช้หลัก — ใช้ระบบทุกวัน)**
ต้องการ: ลดเวลาทำรายงานและวาระ / กลัวที่สุดคือระบบจดผิดแล้วตัวเองต้องรับผิดชอบ
→ ทุกอย่างที่ AI ผลิตต้องแก้ไขได้ และต้องมีขั้นตอนยืนยันก่อนเผยแพร่เสมอ

**B. ประธาน / ผู้บริหาร (ผู้ใช้รอง — ใช้เดือนละครั้ง)**
ต้องการ: เห็นภาพรวมว่าอะไรค้าง ใครค้าง / ไม่อ่านอะไรที่ยาวเกิน 1 หน้าจอ
→ ต้องมีแดชบอร์ดที่เข้าใจได้ใน 10 วินาที

**C. ผู้รับผิดชอบมติ (ผู้ใช้แบบ passive — รับ notification อย่างเดียว)**
ต้องการ: รู้ชัดว่าตัวเองต้องทำอะไร ภายในเมื่อไหร่ และแจ้งกลับได้ง่าย
→ ต้องแจ้งสถานะกลับได้โดยไม่ต้องล็อกอิน (magic link)

---

## 2. Domain model (ศัพท์ที่ทีมต้องใช้ให้ตรงกัน)

| ศัพท์ | ความหมาย | หมายเหตุ |
|---|---|---|
| **Organization** | หน่วยงานเจ้าของข้อมูล | ขอบเขตของ data isolation |
| **Meeting Series** | ชุดการประชุมที่ต่อเนื่องกัน เช่น "คณะกรรมการบริหาร ปีงบ 2569" | **entity ใหม่ที่ v1 ไม่มี — เป็นแกนของทั้งระบบ** |
| **Meeting** | การประชุม 1 ครั้งใน series | มีเลขครั้งที่ เช่น 6/2569 |
| **Transcript Segment** | ท่อนคำพูด 1 ท่อน + ผู้พูด + timestamp | ผลจาก ASR + diarization |
| **Person** | คนในองค์กร (ชื่อจริง ตำแหน่ง อีเมล) | อยู่ใน registry ระดับ org |
| **Person Alias** | ชื่อเล่น/คำเรียกที่ map ไปหา Person | เช่น "พี่หนึ่ง", "ท่านรอง", "ฝ่ายพัสดุ" |
| **Resolution (มติ)** | ข้อตกลงที่มีผลผูกพันจากที่ประชุม | **entity แกนกลางของ v2** อายุยืนข้ามหลาย meeting |
| **Resolution Link** | ความสัมพันธ์ระหว่าง Resolution กับ Meeting | บอกว่า meeting นั้น "สร้าง / อ้างถึง / อัปเดต / ปิด" มตินั้น |
| **Agenda Draft** | ร่างระเบียบวาระที่ระบบสร้างให้ก่อนประชุมครั้งถัดไป | output หลักที่ผู้ใช้เห็นคุณค่าที่สุด |
| **Action** | งานย่อยใต้มติ (ใครทำอะไร ภายในเมื่อไหร่) | 1 Resolution มีได้หลาย Action |

### 2.1 ความแตกต่างจาก v1 ที่ต้องเข้าใจให้ตรง

v1: `Meeting → summary (text) → action_items (list) → email` แล้วจบ ข้อมูลไม่เชื่อมกัน
v2: `Series → Meeting[] → Resolution[] (ข้ามครั้ง) → Action[] → Agenda Draft (ครั้งถัดไป)`

**Resolution ไม่ใช่ property ของ Meeting** — มันเป็น entity อิสระที่ผูกกับ Series และมีหลาย Meeting มาอ้างอิงถึงมันตลอดวงจรชีวิต นี่คือจุดที่ทีมมักออกแบบผิดตอนเริ่ม

---

## 3. Functional requirements

รหัส: `FR-<module>-<number>` · ลำดับความสำคัญ: **M** = Must (ไม่มีไม่ได้), **S** = Should, **C** = Could, **W** = Won't (รอบนี้)

### M1 — Meeting Series management

| ID | Requirement | Pri |
|---|---|---|
| FR-M1-01 | สร้าง/แก้ไข/ลบ Meeting Series ได้ (ชื่อ, ประเภทคณะกรรมการ, ปีงบประมาณ) | M |
| FR-M1-02 | ผูก Meeting เข้ากับ Series พร้อมระบุ "ครั้งที่ X/ปี" และวันที่ประชุม | M |
| FR-M1-03 | เลือก template รายงานการประชุมต่อ Series ได้ | S |
| FR-M1-04 | กำหนดรายชื่อกรรมการประจำ Series (ดึงเข้า Person Registry อัตโนมัติ) | S |
| FR-M1-05 | ระบุรอบการประชุม (รายเดือน/รายไตรมาส) เพื่อคำนวณวันประชุมครั้งถัดไป | C |

**Acceptance:** อัปโหลดไฟล์เสียง 2 ไฟล์เข้า Series เดียวกัน ระบบต้องรู้ว่าไฟล์ที่ 2 คือครั้งถัดจากไฟล์แรก และดึงบริบทครั้งแรกมาใช้ได้

---

### M2 — Ingestion & Transcription

| ID | Requirement | Pri |
|---|---|---|
| FR-M2-01 | อัปโหลดไฟล์เสียง (mp3, wav, m4a) ขนาดไม่เกิน 500 MB | M |
| FR-M2-02 | อัปโหลด transcript ที่มีอยู่แล้ว (txt, docx) เพื่อข้ามขั้น ASR | S |
| FR-M2-03 | ประมวลผลแบบ background job พร้อมแสดงสถานะเป็นขั้น (upload → ASR → diarize → extract → done) | M |
| FR-M2-04 | **ถ้า ASR ล้มเหลว ต้องขึ้น error ชัดเจนและหยุด pipeline** ห้ามใส่ข้อมูลปลอมทดแทนเด็ดขาด | M |
| FR-M2-05 | รองรับ retry ด้วยมือเมื่อ job ล้มเหลว | S |
| FR-M2-06 | Speaker diarization — แยกผู้พูดเป็น SPEAKER_00, SPEAKER_01, ... | M |
| FR-M2-07 | UI ให้เลขาฯ map speaker label เข้ากับ Person จริง (ทำครั้งเดียว ระบบจำ voice profile ต่อ Series) | M |
| FR-M2-08 | เก็บ transcript เป็น segment พร้อม start/end timestamp เพื่ออ้างอิงหลักฐานได้ | M |

> **หนี้ทางเทคนิคที่ต้องล้างก่อน:** FR-M2-04 คือการลบ silent fallback ใน v1 ทิ้ง — ระบบปัจจุบันใส่ transcript ปลอมเมื่อ ASR พัง ซึ่งเป็นความเสี่ยงร้ายแรงทั้งตอนเดโมและตอนใช้จริง **ทำข้อนี้เป็นงานแรกของ sprint**

> **ทางเลือก diarization:** `pyannote.audio` (ต้อง accept license บน HuggingFace) หรือ `WhisperX` ถ้า ASR ของ AI4Thai ไม่คืน speaker label มาให้ ถ้าเวลาไม่พอจริง ๆ ให้ fallback เป็น "เลขาฯ ระบุผู้พูดเองในหน้า review" แต่ต้องมีช่องผู้พูดในโครงสร้างข้อมูลไว้ตั้งแต่แรก

---

### M3 — Person Registry & Entity Resolution

| ID | Requirement | Pri |
|---|---|---|
| FR-M3-01 | CRUD รายชื่อบุคคลระดับองค์กร (ชื่อ-นามสกุล, ตำแหน่ง, หน่วยงาน, อีเมล) | M |
| FR-M3-02 | เก็บ alias หลายค่าต่อคน ("พี่หนึ่ง", "ผอ.กองคลัง", "คุณสมชาย") | M |
| FR-M3-03 | เมื่อ LLM สกัดชื่อจาก transcript ให้ resolve เข้า Person ที่มีอยู่ก่อน ถ้าไม่มั่นใจให้ถามผู้ใช้ ห้ามเดาเอง | M |
| FR-M3-04 | ผู้ใช้ยืนยัน mapping ครั้งแรก → ระบบบันทึกเป็น alias ถาวร | M |
| FR-M3-05 | รองรับผู้รับผิดชอบที่เป็น "หน่วยงาน" ไม่ใช่บุคคล (เช่น "ฝ่ายพัสดุ") | S |
| FR-M3-06 | แสดง confidence score ของการ resolve ให้ผู้ใช้เห็น | C |

**ความเสี่ยงสูงสุดของโมดูลนี้:** ชื่อคนไทยในการประชุมจริงปนกันหมด (ชื่อเล่น + ตำแหน่ง + คำนำหน้า) การให้ LLM เดาเองจะพังแน่นอน **หลักการออกแบบคือ ให้มนุษย์ยืนยันครั้งแรก แล้วระบบจำ** ไม่ใช่ให้ AI แม่น 100% ตั้งแต่แรก

---

### M4 — Resolution extraction & lifecycle ⭐ โมดูลแกนกลาง

| ID | Requirement | Pri |
|---|---|---|
| FR-M4-01 | สกัด Resolution จาก transcript พร้อม: ข้อความมติ, ผู้เสนอ, ผู้รับผิดชอบ, กำหนดเสร็จ, timestamp อ้างอิง | M |
| FR-M4-02 | แยกแยะ "มติ" ออกจาก "การอภิปรายทั่วไป" — ต้องไม่สร้างมติจากประโยคที่แค่พูดลอย ๆ | M |
| FR-M4-03 | Resolution มีสถานะตาม state machine ข้อ 4.1 | M |
| FR-M4-04 | เมื่อประมวลผลประชุมครั้งใหม่ ระบบต้องดึงมติค้างของ Series มาเป็น context แล้ว**จับคู่**คำพูดใหม่กับมติเดิม | M |
| FR-M4-05 | ถ้าตรวจพบว่ามีการรายงานผลของมติเดิม → เสนอเปลี่ยนสถานะ พร้อมแนบหลักฐาน (ข้อความ + timestamp) | M |
| FR-M4-06 | **การปิดมติอัตโนมัติต้องผ่านการยืนยันจากมนุษย์เสมอ** ระบบเสนอได้ แต่ปิดเองไม่ได้ | M |
| FR-M4-07 | รองรับการที่มติใหม่มาแทนมติเก่า (superseded) พร้อมลิงก์อ้างอิงถึงกัน | S |
| FR-M4-08 | แก้ไขข้อความมติ / ผู้รับผิดชอบ / กำหนดเสร็จ ได้ด้วยมือ พร้อมเก็บประวัติการแก้ | M |
| FR-M4-09 | ตรวจจับมติที่ถูกเลื่อนกำหนดซ้ำเกิน 3 ครั้ง แล้วติดธง | S |

#### 4.1 Resolution state machine

```
proposed ──(เลขาฯ ยืนยัน / ที่ประชุมรับรองรายงาน)──> confirmed
confirmed ──(มีรายงานความคืบหน้า)──> in_progress
confirmed ──(ติดปัญหา)──> blocked
in_progress ──> blocked ──> in_progress
in_progress / confirmed / blocked ──(ยืนยันปิด)──> done
confirmed ──(ที่ประชุมมีมติยกเลิก)──> cancelled
confirmed ──(มีมติใหม่มาแทน)──> superseded ──> ลิงก์ไป resolution ใหม่
```

**กติกา:**
- ระบบเปลี่ยนสถานะเองได้เฉพาะ `proposed → confirmed` (เมื่อรับรองรายงานการประชุม)
- การเปลี่ยนไป `done` / `cancelled` ต้องมีคนกดยืนยันเสมอ
- ทุกการเปลี่ยนสถานะบันทึก: ใครเปลี่ยน, เมื่อไหร่, meeting ไหนเป็นต้นเหตุ, หลักฐานอะไร

#### 4.2 หลักการออกแบบที่ห้ามละเมิด

> **False close อันตรายกว่า missed close หลายเท่า**
> ระบบเผลอปิดมติที่ยังไม่เสร็จ = องค์กรลืมงาน = เสียความเชื่อถือถาวร
> ระบบไม่ปิดมติที่เสร็จแล้ว = เลขาฯ กดปิดเอง = เสียเวลา 5 วินาที
> **ให้ tune ทุกอย่างไปทาง conservative เสมอ**

---

### M5 — Agenda generation & Document export

| ID | Requirement | Pri |
|---|---|---|
| FR-M5-01 | สร้างร่างระเบียบวาระของการประชุมครั้งถัดไปอัตโนมัติจากมติค้างของ Series | M |
| FR-M5-02 | โครงวาระตามระเบียบสารบรรณ: วาระ 1 ประธานแจ้ง / 2 รับรองรายงานครั้งก่อน / 3 เรื่องสืบเนื่อง / 4 เรื่องเสนอเพื่อพิจารณา / 5 เรื่องอื่น ๆ | M |
| FR-M5-03 | วาระที่ 3 แต่ละข้อต้องแสดง: ข้อความมติเดิม, ที่มา (ครั้งที่/วาระที่), ผู้รับผิดชอบ, กำหนด, สถานะ, จำนวนวันที่เกิน | M |
| FR-M5-04 | Export ร่างวาระเป็น `.docx` ที่เปิดแก้ต่อใน Word ได้ | M |
| FR-M5-05 | Export รายงานการประชุมฉบับเต็มเป็น `.docx` ตาม template | M |
| FR-M5-06 | รองรับ template ต่อองค์กร (หัวกระดาษ, ฟอนต์ TH Sarabun, เลขวาระ, บล็อกลงนามผู้จด/ผู้ตรวจ) | S |
| FR-M5-07 | ผู้ใช้ลาก/ลบ/เพิ่มวาระ และแก้ลำดับได้ก่อน export | S |
| FR-M5-08 | Export PDF | C |

> **หมายเหตุ implementation:** ใช้ `python-docx` + ไฟล์ `.docx` ต้นแบบเป็น template แล้วแทนที่ placeholder — อย่าสร้างเอกสารจากศูนย์ด้วยโค้ด เพราะจัด format ราชการเองจะเสียเวลามาก ฟอนต์ต้องเป็น TH Sarabun New ขนาด 16 pt ตามระเบียบ

---

### M6 — Resolution dashboard

| ID | Requirement | Pri |
|---|---|---|
| FR-M6-01 | การ์ดสรุประดับ Series: มติทั้งหมด / ปิดแล้ว / ค้าง / เกินกำหนด | M |
| FR-M6-02 | อัตราการปิดมติ (closure rate) และเวลาเฉลี่ยจากมติถึงปิด | M |
| FR-M6-03 | รายการมติค้าง เรียงตามจำนวนวันที่เกินกำหนด | M |
| FR-M6-04 | กรองตามผู้รับผิดชอบ / หน่วยงาน / สถานะ / ช่วงเวลา | S |
| FR-M6-05 | ไฮไลต์มติที่ถูกเลื่อนซ้ำเกิน 3 ครั้ง | S |
| FR-M6-06 | Timeline view ของมติเดียว: เกิดครั้งไหน ถูกพูดถึงครั้งไหนบ้าง ปิดเมื่อไหร่ | S |
| FR-M6-07 | Export dashboard เป็น PDF สำหรับแนบวาระ | C |

---

### M7 — MCP action layer

| ID | Requirement | Pri |
|---|---|---|
| FR-M7-01 | ปรับ MCP server เดิมให้รับ recipient จริงจาก Person Registry (ลบ hardcode 2 อีเมลทิ้ง) | M |
| FR-M7-02 | Tool: `send_meeting_summary_email` — ส่งรายงาน + มติที่เกี่ยวข้องกับผู้รับแต่ละคน (personalized ต่อคน ไม่ใช่ส่งเหมือนกันทุกคน) | M |
| FR-M7-03 | Tool: `send_resolution_reminder` — เตือนก่อนครบกำหนด N วัน พร้อมข้อความมติเดิมคำต่อคำ | M |
| FR-M7-04 | Tool: `send_agenda_preview` — ส่งสรุปเรื่องค้างให้ประธานก่อนประชุม 1 วัน | S |
| FR-M7-05 | Tool: `create_jira_issue` — เป็น**หลักฐานว่า action layer สลับปลายทางได้** ไม่ใช่ฟีเจอร์หลัก | C |
| FR-M7-06 | Scheduler (Celery beat) สำหรับ trigger ตามเวลา | M |
| FR-M7-07 | **ทุก outbound action ต้องผ่านหน้า review/approve ก่อนส่ง** (ตั้ง auto ได้แต่ default = ต้องอนุมัติ) | M |
| FR-M7-08 | Magic link ในอีเมล ให้ผู้รับผิดชอบอัปเดตสถานะกลับได้โดยไม่ต้องล็อกอิน | S |
| FR-M7-09 | Log ทุก action ที่ส่งออก (ใคร ส่งอะไร ถึงใคร เมื่อไหร่ สำเร็จ/ล้มเหลว) | M |

> **การเปลี่ยนจุดยืนจาก v1:** v1 ชูเรื่อง "ส่งอัตโนมัติโดยไม่มีคนตรวจ" เป็นจุดขาย — v2 กลับด้าน ให้ human-in-the-loop เป็นค่าเริ่มต้น เพราะการส่งข้อมูลผิดคนในบริบทประชุมที่มีชั้นความลับคือเหตุ data breach ความอัตโนมัติยังอยู่ แต่เป็น config ไม่ใช่จุดขาย

---

### M8 — Cross-meeting Q&A

| ID | Requirement | Pri |
|---|---|---|
| FR-M8-01 | ถามคำถามข้ามทุกการประชุมใน Series ได้ | M |
| FR-M8-02 | คำตอบต้องอ้างอิงกลับไปที่ meeting + timestamp เสมอ | M |
| FR-M8-03 | คำถามเชิงมติ ("เรื่อง X เคยมีมติว่าอะไรบ้าง") ต้องตอบเป็น timeline ไม่ใช่ย่อหน้าเดียว | S |
| FR-M8-04 | ดึงจาก resolution table ก่อน แล้วค่อย fallback ไป semantic search บน transcript | S |

---

### M9 — Review & approval workflow

| ID | Requirement | Pri |
|---|---|---|
| FR-M9-01 | หน้า review หลังประมวลผลเสร็จ: ตรวจ transcript / ผู้พูด / มติที่สกัดได้ / การจับคู่มติเก่า | M |
| FR-M9-02 | แก้ไขได้ทุกฟิลด์ก่อนกดยืนยัน | M |
| FR-M9-03 | สถานะ Meeting: `draft` → `reviewed` → `approved` → `distributed` | M |
| FR-M9-04 | ห้ามส่งอีเมล/สร้างวาระ จาก meeting ที่ยังไม่ `approved` | M |
| FR-M9-05 | แสดงจุดที่ AI ไม่มั่นใจให้เด่น เพื่อให้คนตรวจโฟกัสถูกที่ | S |

---

### M10 — Security & multi-tenancy

| ID | Requirement | Pri |
|---|---|---|
| FR-M10-01 | Login (email + password หรือ OAuth) | S |
| FR-M10-02 | บังคับ auth ทุก endpoint (v1 มีตารางกับฟังก์ชันแล้วแต่ไม่ได้เอาไปใช้จริง) | S |
| FR-M10-03 | Data isolation ระดับ Organization | S |
| FR-M10-04 | Role: admin / secretary / viewer | C |
| FR-M10-05 | Audit log ทุกการเข้าถึงและแก้ไข | S |
| FR-M10-06 | ไฟล์เสียงเก็บใน object storage (MinIO สำหรับ on-prem / S3) ไม่ใช่ temp folder | S |

> สำหรับ**การแข่ง hackathon** โมดูลนี้ทั้งหมดลดเป็น Should/Could ได้ แต่สำหรับ**การใช้งานจริง** FR-M10-01 ถึง 03 เป็น Must แบบไม่มีข้อยกเว้น — ให้พูดถึงในสไลด์ "ก้าวต่อไป" แทนการทำจริงถ้าเวลาไม่พอ

---

## 5. Data model

### 5.1 ตารางหลัก

```sql
organization(id, name, created_at)

person(id, org_id, full_name, position, department, email, is_active)
person_alias(id, person_id, alias, source, confidence, created_at)

meeting_series(id, org_id, name, committee_type, fiscal_year,
               agenda_template_id, cadence, next_meeting_date)

meeting(id, series_id, sequence_no, fiscal_year, meeting_date,
        audio_uri, status, created_at)
  -- status: draft | processing | failed | reviewed | approved | distributed

transcript_segment(id, meeting_id, speaker_label, person_id,
                   start_ms, end_ms, text, confidence)

resolution(id, series_id, origin_meeting_id, origin_segment_id,
           text, category, status, proposer_person_id,
           due_date, original_due_date, postpone_count,
           closed_meeting_id, closed_at, superseded_by_id,
           created_at, updated_at)
  -- status: proposed | confirmed | in_progress | blocked
  --         | done | cancelled | superseded

resolution_assignee(resolution_id, person_id, department_name)

resolution_link(id, resolution_id, meeting_id, link_type,
                segment_id, evidence_text, confidence, created_at)
  -- link_type: created | referenced | progress_reported
  --            | closed | superseded

resolution_history(id, resolution_id, field, old_value, new_value,
                   changed_by, changed_at, reason)

agenda_draft(id, series_id, target_meeting_date, status, created_at)
agenda_item(id, agenda_draft_id, section_no, item_no, title,
            body, resolution_id, sort_order)

outbound_action(id, meeting_id, resolution_id, action_type,
                payload, status, approved_by, sent_at, error)

audit_log(id, org_id, actor_id, action, entity_type,
          entity_id, metadata, created_at)
```

### 5.2 ความสัมพันธ์ที่ต้องออกแบบให้ถูกตั้งแต่แรก

- `resolution.series_id` **ไม่ใช่** `meeting_id` — มติอยู่ระดับ Series ไม่ใช่ระดับ Meeting (นี่คือจุดที่ทำให้ระบบ "จำ" ได้)
- `resolution_link` เป็น many-to-many ระหว่าง Resolution กับ Meeting — มติหนึ่งข้อถูกพูดถึงได้หลายครั้งข้ามหลายการประชุม
- `evidence_text` + `segment_id` ใน link คือสิ่งที่ทำให้ระบบ **ตรวจสอบย้อนกลับได้** ห้ามตัดทิ้งเพื่อประหยัดเวลา — เป็นคำตอบของคำถาม "แล้วถ้า AI มั่วล่ะ"

---

## 6. API design (ร่าง)

```
POST   /series                          สร้าง series
GET    /series/{id}                     รายละเอียด + สถิติมติ
GET    /series/{id}/resolutions         ?status=&assignee=&overdue=

POST   /meetings                        สร้าง meeting ใน series
POST   /meetings/{id}/upload            อัปโหลดไฟล์เสียง → queue job
GET    /meetings/{id}/status            สถานะแบบเป็นขั้น
GET    /meetings/{id}/transcript        segment + speaker
PATCH  /meetings/{id}/speakers          map speaker → person
GET    /meetings/{id}/review            ชุดข้อมูลสำหรับหน้า review
POST   /meetings/{id}/approve           ยืนยันรายงาน
GET    /meetings/{id}/export?format=docx

GET    /resolutions/{id}                รายละเอียด + timeline
PATCH  /resolutions/{id}                แก้ไขฟิลด์
POST   /resolutions/{id}/status         เปลี่ยนสถานะ + เหตุผล
GET    /resolutions/{id}/links          ประวัติการถูกอ้างถึง

POST   /series/{id}/agenda/generate     สร้างร่างวาระครั้งถัดไป
GET    /agenda/{id}                     ร่างวาระ
PATCH  /agenda/{id}/items               จัดลำดับ/แก้ไข
GET    /agenda/{id}/export?format=docx

GET    /series/{id}/dashboard           ตัวเลขสรุป
POST   /series/{id}/ask                 Q&A ข้าม meeting

GET    /actions/pending                 รายการรออนุมัติส่ง
POST   /actions/{id}/approve            อนุมัติ → ส่งจริง
```

---

## 7. Non-functional requirements

| ด้าน | เป้าหมาย | หมายเหตุ |
|---|---|---|
| ความเร็วประมวลผล | เสียง 60 นาที เสร็จภายใน 10 นาที | ส่วนใหญ่ขึ้นกับ ASR API |
| ความแม่นยำการสกัดมติ | Recall ≥ 0.85, Precision ≥ 0.80 | ต้องวัดจริง ไม่ใช่เคลม |
| **False close rate** | **< 2%** | ตัวชี้วัดที่สำคัญที่สุดของระบบ |
| Diarization | DER < 25% บนเสียงห้องประชุมจริง | เสียงซ้อนกันคือจุดพัง |
| Availability | ไม่มี SLA ในเฟสนี้ | ยังเป็น pilot |
| Data residency | ต้อง deploy on-prem ได้ทั้งก้อน | จุดขายหลักในตลาดไทย |
| PDPA | ลบข้อมูลตามคำขอได้ / audit log / เก็บ consent | อย่าปล่อยไว้ทีหลัง |
| ภาษา | ไทยเป็นหลัก รองรับไทย-อังกฤษปน | |

---

## 8. งานล้างหนี้จาก v1 (ทำก่อนเริ่มฟีเจอร์ใหม่)

| # | งาน | เหตุผล | ประเมิน |
|---|---|---|---|
| 1 | ลบ silent fallback transcript | ความเสี่ยงร้ายแรงสุดในระบบ | 2 ชม. |
| 2 | ลบ hardcoded recipient 2 อีเมล | ทำให้ทดสอบ flow จริงไม่ได้ | 3 ชม. |
| 3 | แตก `page.tsx` (944 บรรทัด) เป็น component | ไม่แตกตอนนี้ = ทำ v2 ต่อไม่ไหว | 1 วัน |
| 4 | ใส่ Alembic migration | schema จะเปลี่ยนเยอะมากใน v2 | 3 ชม. |
| 5 | แก้ชื่อโมเดลให้ตรงกัน (`thaillm-8b` vs "Qwen 3.5") | จะโดนถามตอน Q&A แน่นอน | 30 นาที |
| 6 | แก้ page title จาก "Create Next App" | เสียภาพลักษณ์ฟรี ๆ | 5 นาที |
| 7 | เติมชื่อเจ้าของลิขสิทธิ์ใน LICENSE | ยังเป็น placeholder อยู่ | 5 นาที |

---

## 9. แผนพัฒนา (ปรับตามเวลาที่เหลือจริง)

### เฟส 0 — ล้างหนี้ (1–2 วัน)
งานข้อ 1–7 ในหมวด 8 · โดยเฉพาะข้อ 1, 3, 4

### เฟส 1 — แกนของ v2 (4–5 วัน)
- Schema ใหม่ทั้งหมด + migration
- Meeting Series + การผูก meeting เข้า series
- Resolution extraction (FR-M4-01, 02)
- Resolution state machine (FR-M4-03)
- Person registry + alias (FR-M3-01 ถึง 04)

### เฟส 2 — ฟีเจอร์ที่ทำให้ชนะ (4–5 วัน)
- Cross-meeting linking engine (FR-M4-04, 05, 06) ← **ใช้เวลามากที่สุด อย่าประเมินต่ำ**
- Agenda generation (FR-M5-01 ถึง 03)
- .docx export (FR-M5-04, 05)
- หน้า review (FR-M9-01 ถึง 04)

### เฟส 3 — ทำให้เห็นภาพ (2–3 วัน)
- Dashboard (FR-M6-01 ถึง 03)
- MCP reminder tool + scheduler (FR-M7-03, 06)
- Speaker diarization ถ้ายังไม่ได้ทำ (FR-M2-06, 07)

### เฟส 4 — เตรียมนำเสนอ (2 วัน)
- เตรียมไฟล์เสียงประชุมจำลอง 2 ครั้งที่ต่อเนื่องกัน (ดูหมวด 11)
- รันจริงตั้งแต่ต้นจนจบอย่างน้อย 5 รอบ
- เตรียมข้อมูลสำรองเผื่อ ASR API ล่มระหว่างนำเสนอ

**ถ้าเวลาเหลือน้อยกว่า 2 สัปดาห์:** ตัดเฟส 3 ข้อ diarization ออก แล้วให้เลขาฯ ระบุผู้พูดเองในหน้า review — แต่ยังต้องเก็บ `person_id` ใน `transcript_segment` ไว้ในโครงสร้างข้อมูล

---

## 10. แผนการประเมินผล (สิ่งที่ทำให้คำเคลมน่าเชื่อ)

สร้าง eval set: **เสียงประชุมไทย 20 ไฟล์** (ศัพท์ราชการ, ชื่อคนไทย, เสียงห้องประชุมจริง, มีเสียงซ้อน) โดยอย่างน้อย 3 ชุดต้องเป็นการประชุมต่อเนื่องกันเพื่อวัดฟีเจอร์แกน

| Metric | วิธีวัด | เป้า |
|---|---|---|
| WER | เทียบ transcript กับ ground truth | รายงานตามจริง |
| Resolution extraction F1 | เทียบมติที่สกัดได้กับที่คนอ่านแล้วชี้ | ≥ 0.80 |
| Linking accuracy | มติใหม่จับคู่กับมติเก่าถูกข้อหรือไม่ | ≥ 0.85 |
| **False close rate** | ปิดมติที่ยังไม่เสร็จ | **< 2%** |
| Agenda usefulness | % ของวาระสืบเนื่องที่เลขาฯ ยอมรับโดยไม่แก้ | ≥ 70% |
| เวลาที่ประหยัด | จับเวลาเลขาฯ ทำวาระด้วยมือ vs ใช้ระบบ | ตัวเลขนี้ขายได้ที่สุด |

> ตัวเลข "เวลาที่ประหยัด" คือหลักฐานชิ้นเดียวที่มีน้ำหนักที่สุดในการนำเสนอ ถ้ามีเวลาทำได้แค่อย่างเดียว ให้ทำอันนี้

---

## 11. สคริปต์เสียงสำหรับเดโม (ต้องเตรียม ห้ามใช้เสียงสุ่ม)

**ครั้งที่ 5/2569** — ต้องมี:
- มติ A: จัดซื้อครุภัณฑ์ → ฝ่ายพัสดุ ทำร่าง TOR (กำหนด 30 วัน) ← จะกลายเป็นมติค้างเกินกำหนด
- มติ B: ปรับปรุงระบบสารบรรณ → ฝ่าย IT (เคยเลื่อนมาแล้ว) ← จะแสดงธงเลื่อนซ้ำ
- มติ C: แต่งตั้งคณะทำงานงบประมาณ ← จะถูกปิดในครั้งที่ 6
- ใช้ชื่อเล่นปนชื่อจริงอย่างน้อย 1 จุด เพื่อโชว์ entity resolution

**ครั้งที่ 6/2569** — ต้องมี:
- ประโยครายงานผลมติ C ชัดเจน ("เรื่องคณะทำงานที่ค้างจากคราวที่แล้ว แต่งตั้งเรียบร้อยแล้ว")
- ไม่พูดถึงมติ A เลย ← เพื่อโชว์ว่าระบบยังจำได้และยกขึ้นวาระเอง
- มติใหม่ 1–2 ข้อ

---

## 12. ความเสี่ยง

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|---|---|---|
| Linking engine ทำไม่ทัน | ไม่เหลือจุดขาย | เริ่มเฟส 2 ให้เร็วที่สุด ตัดอย่างอื่นแทน |
| Entity resolution ชื่อไทยพัง | มติผูกผิดคน | ให้คนยืนยันครั้งแรก อย่าให้ AI เดา |
| False close | เสียความเชื่อถือ | บังคับยืนยันเสมอ + tune conservative |
| ASR API ล่มตอนนำเสนอ | เดโมพัง | เตรียม transcript สำรอง + โหมด offline |
| Diarization บนเสียงซ้อน | ระบุผู้พูดผิด | ให้แก้ในหน้า review ได้ |
| Template ราชการต่างกันแต่ละหน่วยงาน | ขยายลูกค้ายาก | ทำ template เป็น config ไม่ hardcode |

---

## 13. อยู่นอกขอบเขต (รอบนี้ไม่ทำ)

- Real-time transcription ระหว่างประชุม
- Mobile app
- เชื่อม Zoom / Teams / Google Meet โดยตรง
- ลายเซ็นดิจิทัลบนรายงาน
- รองรับหลายภาษานอกจากไทย-อังกฤษ
- Billing / subscription
- Voice biometric ระบุตัวตนผู้พูดอัตโนมัติข้าม series

---

## 14. คำถามที่ทีมต้องตัดสินใจก่อนเริ่ม

1. Diarization ใช้ pyannote, WhisperX หรือรอ AI4Thai คืน speaker label มาให้?
2. Template รายงานการประชุม จะยึดของหน่วยงานไหนเป็นต้นแบบ? (ควรหาไฟล์จริงมา 1 ไฟล์)
3. Q&A ข้าม meeting จะใช้ vector DB (pgvector) หรือ query จาก resolution table ตรง ๆ ก่อน?
4. On-prem deployment จะใช้ LLM ตัวไหน ถ้าลูกค้าห้ามเรียก API ออกนอก? (Typhoon / Qwen local)
5. เวลาที่เหลือจริงกี่วัน — คำตอบข้อนี้กำหนดว่าจะตัดเฟสไหนออก
