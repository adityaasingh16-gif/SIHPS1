export { isRealComparison };


function isRealComparison(modelComparison) {
 return (
 modelComparison?.enhanced_data_metrics?.[0]?.model?.includes("PDF-trained") ||
 modelComparison?.comparison_summary?.includes("Real-MoSPI")
 );
}
