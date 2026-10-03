import { Download } from "lucide-react";
import { exportCSV } from "../../lib/exportCsv";
import { useT } from "../../hooks/useT";

export { ExportButton };


function ExportButton({ label, filename, rows, disabled }) {
 const t = useT();
 const isEmpty = !rows || rows.length === 0 || disabled;
 return (
 <button
 onClick={() => exportCSV(filename, rows)}
 disabled={isEmpty}
 title={
  isEmpty
   ? t("export.nothingYet")
   : t("export.downloadRows", { n: rows.length })
 }
 className="flex items-center gap-1.5 rounded-xl border border-line bg-raised px-3 py-2 text-xs font-semibold text-fg-2 shadow-sm transition hover:border-brand-border hover:text-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
 >
 <Download size={14} />
 {label ?? t("common.exportCsv")}
 </button>
 );
}
