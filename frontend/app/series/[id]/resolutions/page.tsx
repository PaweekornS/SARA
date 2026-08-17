"use client";

/** ทะเบียนมติของชุดการประชุม พร้อมตัวกรองตาม 3 สถานะ: กำลังดำเนินการ, เสร็จ, เกินกำหนด */

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, ListChecks, Search, SlidersHorizontal } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { ResolutionDrawer, ResolutionRow } from "@/components/resolution-detail";
import { Badge, Button, Card, EmptyState, Input, Segmented, Select, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { assigneeNames, overdueDays, useApp } from "@/lib/store";

type StageKey = "all" | "in_progress" | "done" | "overdue";
type SortKey = "overdue" | "due" | "recent" | "ref";

export default function ResolutionsPage() {
  const t = useT();
  const { db } = useApp();
  const seriesId = useParams<{ id: string }>().id;

  const [bucket, setBucket] = useState<StageKey>("all");
  const [status, setStatus] = useState<StageKey | "">("");
  const [assignee, setAssignee] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("overdue");
  const [openId, setOpenId] = useState<string | null>(null);

  const all = useMemo(() => db.resolutions.filter((r) => r.series_id === seriesId), [db.resolutions, seriesId]);

  const buckets = {
    all: all.length,
    in_progress: all.filter((r) => r.status !== "done" && overdueDays(r) === 0).length,
    done: all.filter((r) => r.status === "done").length,
    overdue: all.filter((r) => overdueDays(r) > 0 && r.status !== "done").length,
  };

  const rows = all
    .filter((r) => {
      const activeStage = status || (bucket !== "all" ? bucket : "");
      if (activeStage === "in_progress" && (r.status === "done" || overdueDays(r) > 0)) return false;
      if (activeStage === "done" && r.status !== "done") return false;
      if (activeStage === "overdue" && (overdueDays(r) === 0 || r.status === "done")) return false;
      if (assignee && !r.assignee_ids.includes(assignee)) return false;
      if (query.trim()) {
        const q = query.trim().toLowerCase();
        const hay = `${r.text} ${r.ref_no} ${assigneeNames(db, r).map((p) => p.full_name).join(" ")}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sort) {
        case "overdue":
          return overdueDays(b) - overdueDays(a) || (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999");
        case "due":
          return (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999");
        case "recent":
          return b.updated_at.localeCompare(a.updated_at);
        default:
          return a.ref_no.localeCompare(b.ref_no);
      }
    });

  const people = db.people.filter((p) => all.some((r) => r.assignee_ids.includes(p.id)));
  const filtersActive = Boolean(status || assignee || query.trim());

  return (
    <>
      <PageHeader
        title={t("navResolutions")}
        desc={t.pick(
          "มติทุกข้อในชุดการประชุมนี้ — คลิกเพื่อดูไทม์ไลน์และหลักฐานคำต่อคำ",
          "Every resolution in this series, regardless of which meeting created it.",
        )}
        tabs={
          <Segmented
            value={bucket}
            onChange={(val) => {
              setBucket(val as StageKey);
              if (status) setStatus("");
            }}
            options={[
              { value: "all", label: t("all"), count: buckets.all },
              { value: "in_progress", label: t.pick("กำลังดำเนินการ", "In Progress"), count: buckets.in_progress },
              { value: "done", label: t.pick("เสร็จ", "Done"), count: buckets.done },
              { value: "overdue", label: t.pick("เกินกำหนด", "Overdue"), count: buckets.overdue },
            ]}
          />
        }
      />

      <PageBody className="space-y-4">
        <Card className="flex flex-wrap items-center gap-2.5 p-3">
          <div className="relative min-w-[220px] flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-4" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.pick("ค้นข้อความมติ เลขที่มติ หรือผู้รับผิดชอบ", "Search resolutions")}
              className="pl-9"
            />
          </div>

          <div className="w-[180px]">
            <Select value={status} onChange={(e) => setStatus(e.target.value as StageKey | "")}>
              <option value="">{t("status")}: {t("all")}</option>
              <option value="in_progress">{t.pick("กำลังดำเนินการ", "In Progress")}</option>
              <option value="done">{t.pick("เสร็จ", "Done")}</option>
              <option value="overdue">{t.pick("เกินกำหนด", "Overdue")}</option>
            </Select>
          </div>

          <div className="w-[190px]">
            <Select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">{t("assignee")}: {t("all")}</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                </option>
              ))}
            </Select>
          </div>

          <div className="w-[196px]">
            <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              <option value="overdue">{t.pick("เรียง: เกินกำหนดมากสุด", "Sort: most overdue")}</option>
              <option value="due">{t.pick("เรียง: ใกล้ครบกำหนด", "Sort: due soonest")}</option>
              <option value="recent">{t.pick("เรียง: แก้ไขล่าสุด", "Sort: recently updated")}</option>
              <option value="ref">{t.pick("เรียง: เลขที่มติ", "Sort: reference no.")}</option>
            </Select>
          </div>

          {filtersActive && (
            <Button
              size="sm"
              variant="ghost"
              icon={<SlidersHorizontal size={14} />}
              onClick={() => {
                setStatus("");
                setAssignee("");
                setQuery("");
              }}
            >
              {t.pick("ล้างตัวกรอง", "Clear")}
            </Button>
          )}
        </Card>

        <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-ink-3">
          <span>
            {t.pick("แสดง", "Showing")} <span className="tnum font-medium text-ink">{rows.length}</span>{" "}
            {t.pick(`จาก ${all.length} ข้อ`, `of ${all.length}`)}
          </span>
          {buckets.overdue > 0 && (
            <Badge tone="danger">
              <AlertTriangle size={11} /> {buckets.overdue} {t("statOverdue")}
            </Badge>
          )}
        </div>

        <Card className={cn("overflow-hidden", rows.length === 0 && "border-dashed")}>
          {rows.length === 0 ? (
            <EmptyState
              icon={<ListChecks size={20} />}
              title={t("noResolutions")}
              desc={t.pick("ลองล้างตัวกรอง หรือเปลี่ยนคำค้น", "Try clearing the filters.")}
            />
          ) : (
            rows.map((r) => <ResolutionRow key={r.id} resolution={r} onOpen={() => setOpenId(r.id)} />)
          )}
        </Card>
      </PageBody>

      <ResolutionDrawer resolutionId={openId} onClose={() => setOpenId(null)} />
    </>
  );
}
