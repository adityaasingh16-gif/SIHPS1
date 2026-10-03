export { formatCr, formatLakhCrore };


function formatCr(value) {
 return `₹${Number(value).toLocaleString("en-IN", {
 maximumFractionDigits: 2,
 })}`;
}


/** MoSPI costs arrive in ₹ crore; portfolio totals read better in lakh crore. */
function formatLakhCrore(crore) {
  const n = Number(crore);
  if (!Number.isFinite(n)) return "—";
  return `₹${(n / 100000).toFixed(2)}L Cr`;
}
