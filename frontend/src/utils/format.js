/**
 * Utility functions for user-facing formatting across DeclineDoctor UI.
 * Standardizes:
 * - percentages: 2 decimal places with %
 * - percentage-point changes: 2 decimal places with positive magnitude and 'pp'
 * - currency: 2 decimal places with ₹ formatting and thousands separators
 * - counts: integers with thousands separators
 * - confidence: 2 decimal places
 * - p-values: scientific/decimal (< 0.0001 or 4 decimal places)
 * - z-scores: 2 decimal places
 */

export const formatCurrency = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "₹0.00";
  return `₹${Number(val).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

export const formatPercent = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  return `${Number(val).toFixed(2)}%`;
};

export const formatPp = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  return `${Math.abs(Number(val)).toFixed(2)} pp`;
};

export const formatLiftPp = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  const num = Number(val);
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(2)} pp`;
};

export const formatConfidence = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  return Number(val).toFixed(2);
};

export const formatNumber = (val, decimals = 2) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  return Number(val).toFixed(decimals);
};

export const formatInteger = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "0";
  return Math.round(Number(val)).toLocaleString();
};

export const formatPValue = (val) => {
  if (val === null || val === undefined || isNaN(Number(val))) return "N/A";
  const num = Number(val);
  if (num < 0.0001) return "< 0.0001";
  return num.toFixed(4);
};

export const getSeverityBadge = (severity) => {
  switch ((severity || "").toUpperCase()) {
    case "CRITICAL":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "HIGH":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "MEDIUM":
      return "bg-blue-500/15 text-blue-300 border-blue-500/30";
    default:
      return "bg-slate-500/15 text-slate-300 border-slate-500/30";
  }
};

export const getStateBadge = (state) => {
  switch ((state || "").toUpperCase()) {
    case "RESOLVED":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
    case "AWAITING_HUMAN_APPROVAL":
      return "bg-purple-500/15 text-purple-300 border-purple-500/30";
    case "APPROVAL_REJECTED":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "ROLLED_BACK":
      return "bg-rose-500/15 text-rose-300 border-rose-500/30";
    case "ESCALATED_LOW_CONFIDENCE":
    case "ESCALATED_LOW_REVENUE":
    case "ESCALATED_INSUFFICIENT_RECOVERY":
      return "bg-amber-500/15 text-amber-300 border-amber-500/30";
    case "DIAGNOSED":
      return "bg-cyan-500/15 text-cyan-300 border-cyan-500/30";
    default:
      return "bg-slate-500/15 text-slate-300 border-slate-500/30";
  }
};
