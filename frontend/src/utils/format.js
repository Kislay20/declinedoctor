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
