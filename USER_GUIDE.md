# SARA (Smart Agenda & Resolution Assistant) — Deployment & Developer User Guide

คู่มือฉบับสมบูรณ์สำหรับการ Deploy ระบบ, การตั้งค่า GitLab CI/CD Variables, วิธีการใช้งาน API เส้นหลักสำหรับนักพัฒนา, และคู่มือการใช้งานสำหรับผู้ใช้ทั่วไป

---

## 🌐 ลิงก์ระบบบน Production (AI FOR THAI Infra)

- **Web Application UI**: [https://team14.aiforthai.in.th](https://team14.aiforthai.in.th)
- **Interactive OpenAPI (Swagger UI)**: [https://team14.aiforthai.in.th/api/docs](https://team14.aiforthai.in.th/api/docs)
- **ReDoc API Documentation**: [https://team14.aiforthai.in.th/api/redoc](https://team14.aiforthai.in.th/api/redoc)
- **Health Check Status**: [https://team14.aiforthai.in.th/api/health](https://team14.aiforthai.in.th/api/health)

---

## 🚀 1. วิธีการ Deploy (Deployment Guide)

ระบบ SARA ออกแบบในรูปแบบ Multi-container Microservices รันด้วย Docker Compose ผ่านระบบการ Deploy อัตโนมัติด้วย GitLab CI/CD บน Infrastructure ของ AI FOR THAI

### 1.1 การ Deploy อัตโนมัติผ่าน GitLab CI/CD (แนะนำ)
เมื่อมีการ Push โค้ดไปยังสาขา `main` ระบบ GitLab CI/CD Pipeline (`.gitlab-ci.yml`) จะทำงานอัตโนมัติ 3 Stages:
1. **Stage `check`**: ตรวจสอบ Port bindings (`20130`, `20131`), Bind Mounts (`/data/hack/team14`), Resource limits, และ Healthcheck
2. **Stage `deploy`**: อ่านค่า Secret Variables ดึง Container Build ใหม่ และสั่ง `docker compose up -d --build` พร้อมรอจนกว่า Healthcheck อุดมสมบูรณ์ (`healthy`)
3. **Stage `ops`**: ให้ผู้ดูแลระบบกดสั่ง Manual Commands ผ่าน GitLab UI (เช่น `logs`, `ps`, `restart`, `migrate`, `reset-db`)

### 1.2 การ Deploy ด้วยตนเองผ่าน Docker Compose (Local / Manual)
```bash
# 1. Clone repository
git clone https://github.com/PaweekornS/SARA.git
cd SARA

# 2. สร้างไฟล์ .env
cp .env.example .env
# แก้ไขค่าใน .env เช่น APP_AI4THAI_API_KEY และ SECRET_KEY

# 3. สั่ง Build และรันบริการทั้งหมดแบบ Background
docker compose up --build -d

# 4. ตรวจสอบสถานะการทำงานของ Container
docker compose ps

# 5. ดู Log การทำงานของบริการทั้งหมด
docker compose logs -f
```

---

## 🔐 2. การตั้งค่า GitLab CI/CD Variables (CI/CD Environment Setup)

ในระบบ `.gitlab-ci.yml` ของ SARA ตัวแปรสภาพแวดล้อมทั้งหมดที่ขึ้นต้นด้วย **`APP_`** จะถูกนำไปเขียนลงไฟล์ `.env` บนเครื่อง Server โดยอัตโนมัติในขั้นตอน Build Script (`printenv | grep '^APP_' > .env`)

ให้เข้าไปที่ **GitLab Repository** -> **Settings** -> **CI/CD** -> **Variables** และตั้งค่าตัวแปรดังต่อไปนี้ (เลือกติ๊ก `Mask variable` สำหรับค่า Secret):

| Variable Name | Type | Masked / Flags | Description / Example Value |
| :--- | :--- | :--- | :--- |
| `APP_AI4THAI_API_KEY` | Variable | **Masked** | API Key จาก AI FOR THAI (สำหรับ ASR & Pathumma LLM) |
| `APP_PATHUMMA_BASE_URL` | Variable | Expanded | `https://tokenmind.pathumma.in.th/v1` (LLM Gateway) |
| `APP_PATHUMMA_MODEL_NAME` | Variable | Expanded | `thaillm-8b` (ชื่อโมเดล LLM ภาษาไทย) |
| `APP_ASR_URL` | Variable | Expanded | `https://tokenmind.pathumma.in.th` (ASR Endpoint) |
| `APP_ASR_MODEL` | Variable | Expanded | `ptm-asr-1` (ชื่อโมเดล Speech-to-Text) |
| `APP_SECRET_KEY` | Variable | **Masked** | Secret Key สำหรับเซ็น HMAC-SHA256 Magic Link Tokens |
| `APP_API_KEY` | Variable | **Masked** | *(Optional)* Inbound API Key สำหรับป้องกันการเข้าถึง API |
| `APP_PUBLIC_BASE_URL` | Variable | Expanded | `https://team14.aiforthai.in.th` |
| `APP_UPLOAD_DIR` | Variable | Expanded | `/data/uploads` (Shared Upload Directory) |
| `APP_MAX_UPLOAD_MB` | Variable | Expanded | `500` (ขนาดไฟล์อัปโหลดสูงสุดในหน่วย MB) |

---

## 🔌 3. API เส้นหลักๆ สำหรับนักพัฒนา (Main API Endpoints)

### 3.1 สรุปรายการ Endpoint หลัก

1. **`GET /api/health`**: ตรวจสอบสถานะความพร้อมของระบบ API, Database, และโมเดล AI4Thai ASR / Pathumma LLM
2. **`GET /api/series`**: ดึงรายการชุดการประชุม / คณะกรรมการทั้งหมด
3. **`POST /api/meetings`**: สร้างรายการการประชุมใหม่ (ระบุชุดการประชุม, ครั้งที่, วันที่ประชุม)
4. **`POST /api/meetings/{id}/upload`**: อัปโหลดไฟล์เสียง (`.mp3`, `.wav`) หรือไฟล์ Transcript เข้าคิวประมวลผล ASR & LLM
5. **`GET /api/meetings/{id}/status`**: ติดตามสถานะ Pipeline การประมวลผล (`upload` -> `asr` -> `extract` -> `done`)
6. **`GET /api/meetings/{id}`**: ดึงรายละเอียดการประชุมและบทสรุปภาพรวม (Meeting Summary)
7. **`GET /api/meetings/{id}/segments`**: ดึงท่อนข้อความถอดเสียงจาก ASR พร้อม timestamp และผู้พูด
8. **`PATCH /api/meetings/{id}/speakers`**: เปลี่ยนชื่อผู้พูด (`SPEAKER_00` -> ชื่อจริง) พร้อมบันทึก Alias
9. **`GET /api/meetings/{id}/proposals`**: ดึงรายการมติที่ AI สกัดและเสนอขึ้นมา
10. **`POST /api/meetings/{id}/proposals/{proposal_id}`**: กดอนุมัติ (Approve) หรือปฏิเสธ (Reject) มติที่ AI เสนอ
11. **`GET /api/resolutions`**: ค้นหาและติดตามมติการประชุมข้ามคณะกรรมการ (กรองสถานะ/ผู้รับผิดชอบ/วันครบกำหนด)
12. **`POST /api/agenda/generate`**: สั่งสร้างและดาวน์โหลดไฟล์รายงานการประชุม `.docx` รูปแบบหนังสือราชการ
13. **`POST /api/series/{id}/ask`**: ระบบตอบคำถามข้ามการประชุม (Cross-Meeting RAG QA)

---

### 3.2 ตัวอย่างโค้ดเรียกใช้งาน API (Code Examples)

#### 1) สร้างการประชุมใหม่ (Create Meeting)
```bash
curl -X POST "https://team14.aiforthai.in.th/api/meetings" \
  -H "Content-Type: application/json" \
  -H "X-Actor: AdminUser" \
  -d '{
        "series_id": "f5ddf472-3020-4392-95e8-a6c0cf852583",
        "sequence_no": 1,
        "meeting_date": "2026-08-17",
        "title": "การประชุมคณะกรรมการบริหาร ครั้งที่ 1/2569"
      }'
```

#### 2) อัปโหลดไฟล์เสียงประมวลผล ASR & LLM (Upload Audio & Process)
```python
import requests

meeting_id = "aef322f9-a354-4fd8-b6fc-e4fbcb5a8a8b"
url = f"https://team14.aiforthai.in.th/api/meetings/{meeting_id}/upload"
headers = {"X-Actor": "AdminUser"}

with open("test_file/sampelaudio.mp3", "rb") as f:
    files = {"file": ("sampelaudio.mp3", f, "audio/mpeg")}
    response = requests.post(url, headers=headers, files=files)

print("Status Code:", response.status_code)
print("Response:", response.json())
```

#### 3) ดึงท่อนข้อความถอดเสียง ASR & บทสรุปการประชุม (Fetch Transcript & Summary)
```javascript
const meetingId = "aef322f9-a354-4fd8-b6fc-e4fbcb5a8a8b";

// 1. ดึงบทสรุปภาพรวมการประชุม (Summary)
const resMeeting = await fetch(`https://team14.aiforthai.in.th/api/meetings/${meetingId}`);
const meetingData = await resMeeting.json();
console.log("Meeting Summary:", meetingData.summary);

// 2. ดึงท่อนข้อความถอดเสียง (Segments)
const resSegments = await fetch(`https://team14.aiforthai.in.th/api/meetings/${meetingId}/segments`);
const segmentsData = await resSegments.json();
console.log(`Extracted ${segmentsData.length} transcript segments.`);
```

---

## 👥 4. คู่มือการใช้งานสำหรับผู้ใช้งานทั่วไป (End-User Manual)

ผู้ใช้งานทั่วไปสามารถใช้งานระบบ SARA ผ่านหน้าเว็บไคลเอนต์ที่ **[https://team14.aiforthai.in.th](https://team14.aiforthai.in.th)** ตามลำดับขั้นตอนดังนี้:

```
[1. หน้าหลัก Dashboard] ──► [2. สร้างประชุม & อัปโหลดไฟล์เสียง] ──► [3. ตรวจทานข้อความถอดเสียง ASR]
                                                                                │
[6. ถาม-ตอบ RAG QA] ◄── [5. สั่งพิมพ์รายงาน DOCX ราชการ] ◄── [4. อนุมัติสกัดมติ & Action Items]
```

### ขั้นตอนที่ 1: เข้าสู่ระบบและเลือกชุดการประชุม (Dashboard & Series)
1. เปิดหน้าเว็บ [https://team14.aiforthai.in.th](https://team14.aiforthai.in.th)
2. หน้า **Overview Dashboard** จะแสดงสถิติมติการประชุมทั้งหมด, งานที่ค้างชำระ (Overdue), มติที่อยู่ระหว่างดำเนินการ, และกิจกรรมล่าสุด

### ขั้นตอนที่ 2: สร้างการประชุมและอัปโหลดไฟล์เสียง (Meeting Creation & Upload)
1. คลิกเมนู **"การประชุม (Meetings)"** -> ปุ่ม **"สร้างการประชุมใหม่"**
2. เลือกชุดการประชุม/คณะกรรมการ, ระบุครั้งที่ประชุม, วันที่, สถานที่จัดประชุม, ประธาน และเลขานุการ
3. ลากวางไฟล์เสียงการประชุม (`.mp3`, `.wav`, `.m4a`) แล้วกด **"เริ่มประมวลผล"**
4. ระบบ Celery จะทำ Audio Dynamic Chunking และส่งถอดเสียงกับ AI4Thai ASR โดยอัตโนมัติ

### ขั้นตอนที่ 3: ตรวจทานแก้ไขข้อความถอดเสียงและระบุตัวตนผู้พูด (Transcript Editor)
1. เข้าสู่หน้าการประชุม เล่นไฟล์เสียงควบคู่กับท่อนข้อความถอดเสียง (Audio Synchronized Playback)
2. สามารถแก้ไขข้อความที่ถอดความคลาดเคลื่อนได้ทันที
3. เปลี่ยนชื่อผู้พูดจากแท็กเริ่มต้น (เช่น `SPEAKER_00` -> `นายสมชาย ใจดี`) พร้อมเลือกให้ระบบจำชื่อผู้พูดถาวร

### ขั้นตอนที่ 4: อนุมัติมติการประชุมและมอบหมายงาน (Resolutions Review & Registry)
1. กดปุ่ม **"สกัดมติการประชุมด้วย AI"** ระบบ Pathumma LLM จะทำการวิเคราะห์และเสนอรายการมติ, ข้อตกลง, ผู้รับผิดชอบ, และวันครบกำหนด
2. ตรวจสอบรายการมติที่ AI เสนอขึ้นมา สามารถแก้ไขรายละเอียดและกด **"อนุมัติมติ (Approve)"**
3. รายการมติที่อนุมัติแล้วจะถูกบันทึกลง **Resolution Registry** และผู้รับผิดชอบจะได้รับ Magic Link สำหรับอัปเดตความก้าวหน้า

### ขั้นตอนที่ 5: สร้างเอกสารรายงานการประชุมตามรูปแบบหนังสือราชการ (.docx)
1. เข้าเมนู **"สร้างรายงานการประชุม (Agenda & Minutes Builder)"**
2. จัดเรียงวาระการประชุม และเลือกมติที่ต้องการใส่ในรายงาน
3. กดปุ่ม **"ส่งออกเอกสาร (.docx)"** เพื่อดาวน์โหลดไฟล์รายงานการประชุมภาษาไทยตามระเบียบงานสารบรรณ

### ขั้นตอนที่ 6: ระบบตอบคำถามข้ามการประชุม (Cross-Meeting RAG QA)
1. เข้าเมนู **"ถาม-ตอบการประชุม (Series QA)"**
2. เลือกชุดคณะกรรมการ และพิมพ์คำถามภาษาไทย (เช่น *"มติเรื่องการจัดซื้ออุปกรณ์ไอทีในเดือนที่แล้วเป็นอย่างไร"* )
3. ระบบ AI จะค้นหาคำตอบข้ามฐานข้อมูลการประชุมในอดีตทั้งหมด พร้อมอ้างอิงท่อนข้อความและครั้งที่ประชุมให้อัตโนมัติ
