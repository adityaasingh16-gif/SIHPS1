import { riskColor, riskBg } from "../../lib/risk";
import { useRiskLabel } from "../../hooks/useRiskLabel";

export { RiskBadge };


function RiskBadge({ risk }) {
  const label = useRiskLabel()(risk);

  return (
  <span
  className={`rounded-full border px-3 py-1 text-xs font-semibold ${riskBg(
  risk,
  )} ${riskColor(risk)}`}
  >
  {label}
  </span>
  );
}
