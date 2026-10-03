export { exportCSV };


function exportCSV(filename, rows) {
 if (!rows || rows.length === 0) return;
 const keys = Object.keys(rows[0]);
 const escape = (v) => `"${String(v ??"").replace(/"/g, '""')}"`;
 const csv = [
 keys.join(","),
 ...rows.map((r) => keys.map((k) => escape(r[k])).join(",")),
 ].join("\n");
 const blob = new Blob([csv], { type:"text/csv;charset=utf-8;" });
 const url = URL.createObjectURL(blob);
 const a = document.createElement("a");
 a.href = url;
 a.download = filename;
 document.body.appendChild(a);
 a.click();
 document.body.removeChild(a);
 URL.revokeObjectURL(url);
}
