"use client";

/** M10-05 — บันทึกการใช้งาน: ใครทำอะไร กับอะไร เมื่อไหร่ */

import { ShieldCheck } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Card, CardHead, EmptyState } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { useApp } from "@/lib/store";

const ACTION_LABEL: Record<string, string> = {
  create_series: "สร้างชุดการประชุม",
  upload_meeting: "อัปโหลดไฟล์การประชุม",
  approve_meeting: "รับรองรายงานการประชุม",
  meeting_approved: "รับรองรายงานการประชุม",
  meeting_reviewed: "ตรวจทานรายงาน",
  change_resolution_status: "เปลี่ยนสถานะมติ",
  create_person: "เพิ่มบุคคลในทะเบียน",
  add_alias: "บันทึกชื่อเรียก",
  confirm_alias: "ยืนยันชื่อเรียก",
  generate_agenda: "สร้างร่างระเบียบวาระ",
  approve_outbound_action: "อนุมัติการส่งออก",
};

export default function AuditPage() {
  const t = useT();
  const { db } = useApp();

  return (
    <>
      <PageHeader
        title={t("navAudit")}
        desc={t.pick(
          "ทุกการเปลี่ยนแปลงที่มีผลต่อเอกสารราชการถูกบันทึกไว้ พร้อมผู้กระทำและเวลา เพื่อให้ตรวจสอบย้อนกลับได้",
          "Every change affecting an official record is logged with actor and timestamp.",
        )}
      />

      <PageBody>
        <Card className="overflow-hidden">
          <CardHead title={`${t.pick("รายการล่าสุด", "Recent activity")} (${db.audit.length})`} />
          {db.audit.length === 0 ? (
            <EmptyState icon={<ShieldCheck size={20} />} title={t.pick("ยังไม่มีบันทึก", "No entries")} />
          ) : (
            <div className="divide-y divide-[var(--line)]">
              {db.audit.map((e) => (
                <div key={e.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-5 py-3">
                  <span className="tnum w-[132px] shrink-0 font-mono text-[12px] text-ink-3">
                    {e.created_at.replace("T", " ").slice(0, 16)}
                  </span>
                  <Badge tone="brand">{ACTION_LABEL[e.action] ?? e.action}</Badge>
                  <span className="text-[13px] text-ink">{e.metadata}</span>
                  <span className="ml-auto text-[12.5px] text-ink-3">{e.actor}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </PageBody>
    </>
  );
}
