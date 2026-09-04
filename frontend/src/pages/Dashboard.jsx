import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  TrendingDown,
  AlertCircle,
  IndianRupee,
  RefreshCw,
  Clock,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import api from "../api";

const ACTIVE_STATES = [
  "ANOMALY_DETECTED",
  "DIAGNOSED",
  "AWAITING_HUMAN_APPROVAL",
  "ACTION_SELECTED",
  "ACTION_APPLIED",
];

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [activeTab, setActiveTab] = useState("active");

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, incidentsRes] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/incidents"),
      ]);
      setSummary(summaryRes.data);
      setIncidents(incidentsRes.data);
    } catch (err) {
      console.error("Error fetching dashboard data", err);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    Promise.all([api.get("/dashboard/summary"), api.get("/incidents")])
      .then(([summaryRes, incidentsRes]) => {
        if (isMounted) {
          setSummary(summaryRes.data);
          setIncidents(incidentsRes.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Error fetching dashboard data", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleResetDemo = async () => {
    setResetting(true);
    try {
      await api.post("/simulate/inject");
      await loadData();
    } catch (err) {
      console.error("Error resetting demo data", err);
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-10 text-slate-400">Loading metrics...</div>
    );
  }

  const activeIncidents = incidents.filter((inc) =>
    ACTIVE_STATES.includes(inc.state)
  );
  const historicalIncidents = incidents.filter(
    (inc) => !ACTIVE_STATES.includes(inc.state)
  );

  const displayedIncidents =
    activeTab === "active" ? activeIncidents : historicalIncidents;

  const getStatusBadge = (state) => {
    if (state === "RESOLVED") {
      return (
        <span className="bg-emerald-500/10 text-emerald-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-emerald-500/20 flex items-center gap-1">
          <CheckCircle2 className="w-3 h-3" /> RESOLVED
        </span>
      );
    }
    if (state === "AWAITING_HUMAN_APPROVAL") {
      return (
        <span className="bg-amber-500/10 text-amber-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-amber-500/20 flex items-center gap-1">
          <ShieldCheck className="w-3 h-3" /> AWAITING HUMAN APPROVAL
        </span>
      );
    }
    if (state.startsWith("ESCALATED")) {
      return (
        <span className="bg-rose-500/10 text-rose-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-rose-500/20">
          {state.replace(/_/g, " ")}
        </span>
      );
    }
    return (
      <span className="bg-blue-500/10 text-blue-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-blue-500/20">
        {state}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">
            Payment Health Overview
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time anomaly detection and autonomous revenue recovery
          </p>
        </div>
        <button
          onClick={handleResetDemo}
          disabled={resetting}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-sm font-medium transition disabled:opacity-50"
        >
          <RefreshCw
            className={`w-4 h-4 ${resetting ? "animate-spin text-purple-400" : ""}`}
          />
          {resetting ? "Resetting Demo..." : "Reset / Seed Demo Data"}
        </button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#1e2330] p-5 rounded-xl border border-slate-800 shadow-sm">
          <div className="text-slate-400 text-sm mb-1">
            Global Success Rate (24h)
          </div>
          <div className="text-3xl font-bold text-white">
            {summary?.global_success_rate}%
          </div>
        </div>
        <div className="bg-[#1e2330] p-5 rounded-xl border border-slate-800 shadow-sm">
          <div className="text-slate-400 text-sm mb-1">Active Incidents</div>
          <div className="text-3xl font-bold text-rose-500 flex items-center gap-2">
            <AlertCircle className="w-6 h-6" /> {summary?.active_incident_count}
          </div>
        </div>
        <div className="bg-[#1e2330] p-5 rounded-xl border border-slate-800 shadow-sm">
          <div className="text-slate-400 text-sm mb-1">Active Revenue at Risk</div>
          <div className="text-3xl font-bold text-orange-400 flex items-center">
            <IndianRupee className="w-6 h-6" />{" "}
            {summary?.revenue_at_risk?.toLocaleString()}
          </div>
        </div>
        <div className="bg-[#1e2330] p-5 rounded-xl border border-slate-800 shadow-sm">
          <div className="text-slate-400 text-sm mb-1">Total Recovered Revenue</div>
          <div className="text-3xl font-bold text-emerald-400 flex items-center">
            <IndianRupee className="w-6 h-6" />{" "}
            {summary?.total_recovered_revenue?.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Incidents Table with Tabs */}
      <div className="bg-[#1e2330] rounded-xl border border-slate-800 overflow-hidden mt-8">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab("active")}
              className={`text-sm font-semibold pb-1 border-b-2 transition ${
                activeTab === "active"
                  ? "border-blue-500 text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Active Incidents ({activeIncidents.length})
            </button>
            <button
              onClick={() => setActiveTab("history")}
              className={`text-sm font-semibold pb-1 border-b-2 transition ${
                activeTab === "history"
                  ? "border-blue-500 text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Historical & Resolved ({historicalIncidents.length})
            </button>
          </div>
        </div>
        <div className="divide-y divide-slate-800/50">
          {displayedIncidents.length === 0 ? (
            <div className="p-8 text-center text-slate-500">
              {activeTab === "active"
                ? "No active incidents detected. Payment flows are healthy."
                : "No historical or resolved incidents recorded yet."}
            </div>
          ) : (
            displayedIncidents.map((inc) => (
              <div
                key={inc.id}
                className="p-6 flex items-center justify-between hover:bg-[#252b3b] transition"
              >
                <div>
                  <div className="flex items-center gap-3 mb-1.5">
                    <span className="bg-slate-800 text-slate-200 px-2.5 py-0.5 rounded text-xs font-semibold border border-slate-700">
                      {inc.segment_issuer} • {inc.segment_payment_method}
                    </span>
                    {getStatusBadge(inc.state)}
                  </div>
                  <div className="text-slate-400 text-sm flex items-center gap-4">
                    <span className="flex items-center gap-1 text-rose-400">
                      <TrendingDown className="w-4 h-4" />
                      Dropped {inc.drop_pp.toFixed(1)}% (from{" "}
                      {inc.baseline_success_rate.toFixed(1)}% to{" "}
                      {inc.incident_success_rate.toFixed(1)}%)
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className="text-slate-300">
                      ₹{Math.round(inc.at_risk_revenue ?? inc.estimated_loss ?? 0).toLocaleString()} at risk
                    </span>
                    <span className="text-slate-500">•</span>
                    <span className="text-slate-400 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {inc.sample_size} sample txns
                    </span>
                  </div>
                </div>
                <Link
                  to={`/incident/${inc.id}`}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
                >
                  View Evidence
                </Link>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
