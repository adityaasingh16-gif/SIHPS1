export { MetricCell };


function MetricCell({ item }) {
 const isCls = item.roc_auc != null || item.f1 != null;
 const metrics = isCls
 ? [
 ["ROC-AUC", item.roc_auc],
 ["F1", item.f1],
 ["Recall", item.recall],
 ]
 : [
 ["R²", item.r2],
 ["MAE", item.mae],
 ["RMSE", item.rmse],
 ];
 const present = metrics.filter(([, v]) => v != null);
 return (
 <td className="px-3 py-3">
 <div className="flex flex-wrap justify-end gap-1">
 {present.length === 0 && <span className="text-xs text-fg-4">—</span>}
 {present.map(([k, v]) => (
 <span
 key={k}
 className="rounded-md bg-page px-1.5 py-0.5 text-[10px] font-semibold text-fg-2 ring-1 ring-inset ring-brand"
 >
 {k}: <span className="text-fg">{Number(v).toFixed(3)}</span>
 </span>
 ))}
 </div>
 </td>
 );
}
