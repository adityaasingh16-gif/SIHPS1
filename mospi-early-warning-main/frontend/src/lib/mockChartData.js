export { riskData, riskTrendOverall, progressData, riskDistribution };


const riskData = [
 { month:"Jan", low: 42, medium: 31, high: 18, critical: 7 },
 { month:"Feb", low: 44, medium: 29, high: 19, critical: 8 },
 { month:"Mar", low: 47, medium: 28, high: 17, critical: 8 },
 { month:"Apr", low: 51, medium: 26, high: 16, critical: 7 },
];


const riskTrendOverall = riskData.map((d) => ({
 month: d.month,
 overall: Math.round((d.low + d.medium + d.high + d.critical) / 4),
}));


const progressData = [
 { name:"Roads", progress: 72 },
 { name:"Railways", progress: 64 },
 { name:"Energy", progress: 76 },
 { name:"Water", progress: 81 },
 { name:"Urban", progress: 61 },
];


const riskDistribution = [
 { name:"Low", value: 42 },
 { name:"Medium", value: 31 },
 { name:"High", value: 19 },
 { name:"Critical", value: 8 },
];
