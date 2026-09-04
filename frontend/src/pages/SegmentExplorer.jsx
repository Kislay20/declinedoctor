import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Layers, Filter, ArrowRight, RefreshCw } from "lucide-react";
import api from "../api";
import { formatCurrency, formatPercent, formatInteger } from "../utils/format";

export default function SegmentExplorer() {
  const [segments, setSegments] = useState([]);
  const [filters, setFilters] = useState({ issuers: [], payment_methods: [], decline_codes: [] });
  const [selectedIssuer, setSelectedIssuer] = useState("");
  const [selectedMethod, setSelectedMethod] = useState("");
  const [selectedCode, setSelectedCode] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedIssuer) params.issuer = selectedIssuer;
      if (selectedMethod) params.payment_method = selectedMethod;
      if (selectedCode) params.decline_code = selectedCode;

      const res = await api.get("/segments/analytics", { params });
      setSegments(res.data.segments || []);
      setFilters(res.data.filters || { issuers: [], payment_methods: [], decline_codes: [] });
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

    api.get("/segments/analytics", { params })
      .then((res) => {
        if (isMounted) {
          setSegments(res.data.segments || []);
          setFilters(res.data.filters || { issuers: [], payment_methods: [], decline_codes: [] });
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
  }, [selectedIssuer, selectedMethod, selectedCode]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Layers className="text-blue-400 w-7 h-7" /> Segment Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Granular success rate analysis, decline code distributions, and active incident mapping by issuer and payment rail.
          </p>
        </div>

        <button
          onClick={fetchAnalytics}
          className="self-start px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-2 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh Data
        </button>
      </div>

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
                  <th className="p-4">Segment (Issuer & Rail)</th>
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
    </div>
  );
}
