import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Layers, Filter, ArrowRight, RefreshCw, CreditCard, ShieldAlert, Cpu } from "lucide-react";
import api from "../api";
import { formatCurrency, formatPercent, formatInteger } from "../utils/format";

export default function SegmentExplorer() {
  const [activeTab, setActiveTab] = useState("issuers"); // 'issuers' | 'bins'
  const [segments, setSegments] = useState([]);
  const [filters, setFilters] = useState({ issuers: [], payment_methods: [], decline_codes: [] });
  const [selectedIssuer, setSelectedIssuer] = useState("");
  const [selectedMethod, setSelectedMethod] = useState("");
  const [selectedCode, setSelectedCode] = useState("");
  const [binData, setBinData] = useState(null);
  const [binIssuer, setBinIssuer] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedIssuer) params.issuer = selectedIssuer;
      if (selectedMethod) params.payment_method = selectedMethod;
      if (selectedCode) params.decline_code = selectedCode;

      const [segRes, binRes] = await Promise.all([
        api.get("/segments/analytics", { params }),
        api.get("/segments/bin-intelligence", { params: { issuer: binIssuer || undefined } }).catch(() => ({ data: null })),
      ]);

      setSegments(segRes.data.segments || []);
      setFilters(segRes.data.filters || { issuers: [], payment_methods: [], decline_codes: [] });
      if (binRes?.data) setBinData(binRes.data);
    } catch (err) {
      console.error("Failed to load segment analytics", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const params = {};
    if (selectedIssuer) params.issuer = selectedIssuer;
    if (selectedMethod) params.payment_method = selectedMethod;
    if (selectedCode) params.decline_code = selectedCode;

    Promise.all([
      api.get("/segments/analytics", { params }),
      api.get("/segments/bin-intelligence", { params: { issuer: binIssuer || undefined } }).catch(() => ({ data: null })),
    ])
      .then(([segRes, binRes]) => {
        if (isMounted) {
          setSegments(segRes.data.segments || []);
          setFilters(segRes.data.filters || { issuers: [], payment_methods: [], decline_codes: [] });
          if (binRes?.data) setBinData(binRes.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to load segment analytics", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedIssuer, selectedMethod, selectedCode, binIssuer]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Layers className="text-blue-400 w-7 h-7" /> Segment Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Granular success rate analysis, decline code distributions, and active incident mapping by issuer, rail, and deep BIN range.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-lg text-xs font-semibold">
            <button
              onClick={() => setActiveTab("issuers")}
              className={`px-3 py-1.5 rounded-md transition ${activeTab === "issuers" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
            >
              Issuer &amp; Rail Segments
            </button>
            <button
              onClick={() => setActiveTab("bins")}
              className={`px-3 py-1.5 rounded-md transition flex items-center gap-1.5 ${activeTab === "bins" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"}`}
            >
              <CreditCard className="w-3.5 h-3.5 text-cyan-400" /> Deep BIN Intelligence
            </button>
          </div>

          <button
            onClick={fetchAnalytics}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      {activeTab === "issuers" ? (
        <>
          {/* Filter Bar */}
          <div className="bg-[#151822] border border-slate-800 rounded-xl p-4 flex flex-wrap gap-4 items-center">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <Filter className="w-4 h-4 text-indigo-400" /> Filter By:
            </div>

            <div>
              <select
                value={selectedIssuer}
                onChange={(e) => setSelectedIssuer(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Issuers</option>
                {filters.issuers.map((iss) => (
                  <option key={iss} value={iss}>{iss}</option>
                ))}
              </select>
            </div>

            <div>
              <select
                value={selectedMethod}
                onChange={(e) => setSelectedMethod(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Payment Methods</option>
                {filters.payment_methods.map((pm) => (
                  <option key={pm} value={pm}>{pm}</option>
                ))}
              </select>
            </div>

            <div>
              <select
                value={selectedCode}
                onChange={(e) => setSelectedCode(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Decline Codes</option>
                {filters.decline_codes.map((dc) => (
                  <option key={dc} value={dc}>{dc}</option>
                ))}
              </select>
            </div>

            {(selectedIssuer || selectedMethod || selectedCode) && (
              <button
                onClick={() => {
                  setSelectedIssuer("");
                  setSelectedMethod("");
                  setSelectedCode("");
                }}
                className="text-xs text-indigo-400 hover:text-indigo-300 underline ml-auto"
              >
                Clear Filters
              </button>
            )}
          </div>

          {/* Segments Table */}
          <div className="bg-[#151822] border border-slate-800 rounded-xl overflow-hidden">
            {loading ? (
              <div className="p-10 text-center text-slate-400">Loading segment analytics...</div>
            ) : segments.length === 0 ? (
              <div className="p-10 text-center text-slate-500">No segments match the selected criteria.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold uppercase">
                    <tr>
                      <th className="p-4">Segment (Issuer &amp; Rail)</th>
                      <th className="p-4">Volume (INR)</th>
                      <th className="p-4">Declined Volume</th>
                      <th className="p-4">Success Rate</th>
                      <th className="p-4">Decline Codes Breakdown</th>
                      <th className="p-4">Active Incidents</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {segments.map((seg, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition">
                        <td className="p-4 font-semibold text-slate-200">
                          <div>{seg.issuer}</div>
                          <div className="text-[11px] font-mono text-indigo-400 uppercase">{seg.payment_method}</div>
                        </td>

                        <td className="p-4 font-mono text-slate-300">
                          {formatCurrency(seg.total_volume)}
                          <div className="text-[10px] text-slate-500 font-sans">{formatInteger(seg.total_transactions)} txns</div>
                        </td>

                        <td className="p-4 font-mono text-rose-400">
                          {formatCurrency(seg.declined_volume)}
                          <div className="text-[10px] text-slate-500 font-sans">{formatInteger(seg.failed_transactions)} declines</div>
                        </td>

                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <span className={`font-mono font-bold ${
                              seg.success_rate >= 80 ? "text-emerald-400" : seg.success_rate >= 60 ? "text-amber-400" : "text-rose-400"
                            }`}>
                              {formatPercent(seg.success_rate)}
                            </span>
                          </div>
                          <div className="w-24 bg-slate-800 h-1.5 rounded-full mt-1 overflow-hidden">
                            <div
                              className={`h-full ${
                                seg.success_rate >= 80 ? "bg-emerald-500" : seg.success_rate >= 60 ? "bg-amber-500" : "bg-rose-500"
                              }`}
                              style={{ width: `${Math.min(100, Math.max(5, seg.success_rate))}%` }}
                            />
                          </div>
                        </td>

                        <td className="p-4">
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {Object.entries(seg.decline_codes).map(([code, cnt]) => (
                              <span
                                key={code}
                                className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/60 text-[10px] font-mono text-slate-300"
                              >
                                {code}: {cnt}
                              </span>
                            ))}
                          </div>
                        </td>

                        <td className="p-4">
                          {seg.incidents && seg.incidents.length > 0 ? (
                            <div className="flex flex-col gap-1">
                              {seg.incidents.map((inc) => (
                                <Link
                                  key={inc.id}
                                  to={`/incident/${inc.id}`}
                                  className="inline-flex items-center gap-1 text-[11px] font-mono text-indigo-400 hover:text-indigo-300"
                                >
                                  <span>{inc.id.slice(0, 10)}...</span>
                                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                                    {inc.state}
                                  </span>
                                  <ArrowRight className="w-3 h-3" />
                                </Link>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500 text-[11px]">None active</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Deep BIN Intelligence Tab */
        <div className="space-y-6">
          {/* Isolation Verdict Banner */}
          {binData?.isolation_verdict && (
            <div className={`p-4 rounded-xl border flex items-center justify-between gap-4 ${
              binData.isolated_incident_detected
                ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                : "bg-slate-900 border-slate-800 text-slate-300"
            }`}>
              <div className="flex items-center gap-3">
                <ShieldAlert className={`w-5 h-5 ${binData.isolated_incident_detected ? "text-amber-400" : "text-indigo-400"}`} />
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Causal Diagnosis &amp; Isolation Verdict
                  </div>
                  <div className="text-sm font-medium mt-0.5">{binData.isolation_verdict}</div>
                </div>
              </div>

              <div className="text-right font-mono text-xs hidden sm:block">
                <div className="text-slate-400">Total BINs Telemetry</div>
                <div className="text-slate-200 font-bold">{binData.total_bins_analyzed} ranges analyzed</div>
              </div>
            </div>
          )}

          {/* Issuer Filter for BINs */}
          <div className="bg-[#151822] border border-slate-800 rounded-xl p-4 flex items-center gap-4">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-400" /> Filter Issuer for BIN Profiling:
            </div>
            <select
              value={binIssuer}
              onChange={(e) => setBinIssuer(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Issuers (Global Telemetry)</option>
              {filters.issuers.map((iss) => (
                <option key={iss} value={iss}>{iss}</option>
              ))}
            </select>
          </div>

          {/* BINs Table */}
          <div className="bg-[#151822] border border-slate-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-cyan-400" /> Monitored Bank Identification Numbers (BINs)
              </h2>
              <span className="text-[11px] text-slate-500 font-mono">Simulated Multi-Bank Card Ranges</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-sans font-semibold uppercase">
                  <tr>
                    <th className="p-3">BIN Range</th>
                    <th className="p-3">Issuer / Scheme</th>
                    <th className="p-3">Txn Volume</th>
                    <th className="p-3">Declines</th>
                    <th className="p-3">Success Rate</th>
                    <th className="p-3">3DS Failure Signal</th>
                    <th className="p-3">Decline Distribution</th>
                    <th className="p-3">Gateway Dispersion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {binData?.bins && binData.bins.filter((b) => b.bin && String(b.bin).trim() !== "None" && String(b.bin).trim() !== "").length > 0 ? (
                    binData.bins
                      .filter((b) => b.bin && String(b.bin).trim() !== "None" && String(b.bin).trim() !== "")
                      .map((b) => (
                      <tr key={b.bin} className="hover:bg-slate-800/30 transition">
                        <td className="p-3">
                          <span className="px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-800/40 text-cyan-300 font-bold">
                            {b.bin}
                          </span>
                        </td>

                        <td className="p-3 font-sans">
                          <div className="text-slate-200 font-semibold">{b.issuer}</div>
                          <div className="text-[10px] text-slate-400 uppercase font-mono">{b.card_type || `${b.network || "Visa"} ${b.tier || ""}`}</div>
                        </td>

                        <td className="p-3 font-mono text-slate-300">
                          {formatCurrency(b.total_volume)}
                          <div className="text-[10px] text-slate-500 font-sans">{b.total_txns} txns</div>
                        </td>

                        <td className="p-3 font-mono text-rose-400">
                          {formatCurrency(b.declined_volume)}
                          <div className="text-[10px] text-slate-500 font-sans">{b.failed_txns ?? b.failures} failed</div>
                        </td>

                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            <span className={`font-bold ${
                              (b.success_rate ?? b.success_rate_pct) >= 80 ? "text-emerald-400" :
                              (b.success_rate ?? b.success_rate_pct) >= 60 ? "text-amber-400" : "text-rose-400"
                            }`}>
                              {(b.success_rate != null || b.success_rate_pct != null)
                                ? formatPercent(b.success_rate ?? b.success_rate_pct)
                                : <span className="text-slate-500">No signal</span>}
                            </span>
                          </div>
                          {(b.success_rate != null || b.success_rate_pct != null) && (
                            <div className="w-20 bg-slate-800 h-1.5 rounded-full mt-1 overflow-hidden">
                              <div
                                className={`h-full ${
                                  (b.success_rate ?? b.success_rate_pct) >= 80 ? "bg-emerald-500" :
                                  (b.success_rate ?? b.success_rate_pct) >= 60 ? "bg-amber-500" : "bg-rose-500"
                                }`}
                                style={{ width: `${Math.min(100, Math.max(5, b.success_rate ?? b.success_rate_pct))}%` }}
                              />
                            </div>
                          )}
                        </td>

                        <td className="p-3">
                          {/* 3DS signal: read both nested and flat field names */}
                          {(() => {
                            const rate = b.synthetic_3ds_signal?.auth_failure_rate_pct ?? b.synthetic_3ds_failure_rate_pct;
                            if (rate == null) return <span className="text-slate-500 text-[10px]">No signal</span>;
                            return (
                              <span className={`px-2 py-0.5 rounded text-[10px] ${
                                rate > 30
                                  ? "bg-rose-500/10 text-rose-300 border border-rose-500/30"
                                  : rate > 10
                                  ? "bg-amber-500/10 text-amber-300 border border-amber-500/30"
                                  : "bg-slate-900 text-slate-400 border border-slate-800"
                              }`}>
                                {formatPercent(rate)} <span className="text-[9px] text-slate-500">(Synthetic)</span>
                              </span>
                            );
                          })()}
                        </td>

                        <td className="p-3">
                          <div className="flex flex-wrap gap-1 max-w-xs font-mono">
                            {b.decline_codes && Object.entries(b.decline_codes).map(([code, cnt]) => (
                              <span
                                key={code}
                                className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/60 text-[10px] text-slate-300"
                              >
                                {code}: {cnt}
                              </span>
                            ))}
                            {(!b.decline_codes || Object.keys(b.decline_codes).length === 0) && (
                              <span className="text-slate-500 text-[10px]">No declines</span>
                            )}
                          </div>
                        </td>

                        <td className="p-3 text-[11px] text-slate-300 font-sans">
                          {/* Gateway dispersion: read both providers and provider_breakdown */}
                          {(() => {
                            const prov = b.providers || b.provider_breakdown;
                            if (!prov || Object.keys(prov).length === 0) {
                              return <span className="text-slate-500">No data</span>;
                            }
                            return (
                              <div className="space-y-0.5">
                                {Object.entries(prov).map(([gw, info]) => (
                                  <div key={gw} className="flex items-center gap-1.5">
                                    <span className="font-semibold text-slate-200 truncate max-w-[90px]">{gw}</span>
                                    {info.success_rate != null && (
                                      <span className={`text-[10px] font-mono ${
                                        info.success_rate >= 90 ? "text-emerald-400" :
                                        info.success_rate >= 70 ? "text-amber-400" : "text-rose-400"
                                      }`}>{formatPercent(info.success_rate)}</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            );
                          })()}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="p-8 text-center text-slate-500 font-sans">
                        No BIN records available for current filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

