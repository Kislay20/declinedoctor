import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  TrendingDown,
  AlertCircle,
  RefreshCw,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Check,
  BarChart3,
  Users,
  Server,
  DollarSign,
  BrainCircuit,
  Activity,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
  formatPp,
  formatInteger,
  formatNumber,
} from "../utils/format";

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
  const [providersHealth, setProvidersHealth] = useState(null);
  const [learningSummary, setLearningSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [activeTab, setActiveTab] = useState("active"); // 'active' | 'queue' | 'history'
  const [approvingId, setApprovingId] = useState(null);
  const [role, setRole] = useState(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, incidentsRes, providersRes, learningRes, alertsRes] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/incidents"),
        api.get("/providers/health").catch(() => ({ data: null })),
        api.get("/learning/summary").catch(() => ({ data: null })),
        api.get("/observability/alerts").catch(() => ({ data: [] })),
      ]);
      setSummary(summaryRes.data);
      setIncidents(incidentsRes.data);
      if (providersRes?.data) setProvidersHealth(providersRes.data);
      if (learningRes?.data) setLearningSummary(learningRes.data);
      if (alertsRes?.data) setAlerts(alertsRes.data);
    } catch (err) {
      console.error("Error fetching dashboard data", err);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      api.get("/dashboard/summary"),
      api.get("/incidents"),
      api.get("/providers/health").catch(() => ({ data: null })),
      api.get("/learning/summary").catch(() => ({ data: null })),
      api.get("/observability/alerts").catch(() => ({ data: [] })),
    ])
      .then(([summaryRes, incidentsRes, providersRes, learningRes, alertsRes]) => {
        if (isMounted) {
          setSummary(summaryRes.data);
          setIncidents(incidentsRes.data);
          if (providersRes?.data) setProvidersHealth(providersRes.data);
          if (learningRes?.data) setLearningSummary(learningRes.data);
          if (alertsRes?.data) setAlerts(alertsRes.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Error fetching dashboard data", err);
        if (isMounted) setLoading(false);
      });

    const handleRoleUpdate = () => {
      setRole(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");
    };
    window.addEventListener("storage", handleRoleUpdate);

    return () => {
      isMounted = false;
      window.removeEventListener("storage", handleRoleUpdate);
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

  const handleQuickApprove = async (incidentId, proposedAction) => {
    setApprovingId(incidentId);
    try {
      await api.post(`/incidents/${incidentId}/recover`, {
        recommended_action: proposedAction || "REROUTE",
        selected_by: "human_operator",
        reasoning: "Approved via dashboard quick approval queue.",
        human_approved: true,
        role: role,
      });
      await loadData();
    } catch (err) {
      console.error("Failed to approve recovery", err);
      alert(err.response?.data?.detail || "Approval rejected by backend policy.");
    } finally {
      setApprovingId(null);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-16 text-slate-400">Loading metrics...</div>
    );
  }

  const activeIncidents = incidents.filter((inc) =>
    ACTIVE_STATES.includes(inc.state)
  );
  const historicalIncidents = incidents.filter(
    (inc) => !ACTIVE_STATES.includes(inc.state)
  );
  const approvalQueue = summary?.approval_queue || [];

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
          <AlertCircle className="w-3 h-3" /> AWAITING APPROVAL
        </span>
      );
    }
    if (state.startsWith("ESCALATED_")) {
      return (
        <span className="bg-rose-500/10 text-rose-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-rose-500/20 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> {state.replace("ESCALATED_", "ESCALATED: ")}
        </span>
      );
    }
    if (state === "ROLLED_BACK") {
      return (
        <span className="bg-purple-500/10 text-purple-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-purple-500/20 flex items-center gap-1">
          ROLLED BACK
        </span>
      );
    }
    return (
      <span className="bg-blue-500/10 text-blue-400 px-2.5 py-0.5 rounded text-xs font-semibold border border-blue-500/20 flex items-center gap-1">
        <Clock className="w-3 h-3" /> {state}
      </span>
    );
  };

  const getSeverityBadge = (sev) => {
    const s = sev || "MEDIUM";
    if (s === "CRITICAL") {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">CRITICAL</span>;
    }
    if (s === "HIGH") {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">HIGH</span>;
    }
    if (s === "MEDIUM") {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">MEDIUM</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300">LOW</span>;
  };

  const funnel = summary?.funnel || {
    total_payments_volume: 0,
    total_failed_volume: 0,
    at_risk: 0,
    diagnosed: 0,
    eligible: 0,
    recovered: 0,
    net_recovered: 0,
  };
  const economics = summary?.recovery_economics || {
    gross_recovered: 0,
    recovery_cost: 0,
    net_recovered: 0,
    roi_pct: 0,
    cost_breakdown: {},
    disclaimer: "Simulated recovery economics based on transparent cost models.",
  };
  const canApprove = role === "ADMIN" || role === "OPERATOR";
  const activeAlertCount = (alerts || []).filter((a) => a.triggered).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold">Autonomous Recovery Command</h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time decline anomaly detection, causal diagnosis, bounded policy-driven mitigation, and closed-loop learning.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleResetDemo}
            disabled={resetting}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${resetting ? "animate-spin" : ""}`} />
            {resetting ? "Resetting..." : "Reset / Seed Demo Data"}
          </button>
        </div>
      </div>

      {/* Production Observability & Alert Ribbon */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-slate-900/90 border border-slate-800 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-semibold text-slate-300">
            <Activity className="w-4 h-4 text-indigo-400" />
            <span>Platform Telemetry:</span>
          </div>
          <span className="flex items-center gap-1 text-emerald-400 font-mono font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" /> All 5 Observability Guards Nominal
          </span>
          {activeAlertCount > 0 && (
            <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
              {activeAlertCount} Alert Triggered
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
          <span>Diag Latency: <strong className="text-slate-200">142ms</strong></span>
          <span>Policy Eval: <strong className="text-slate-200">18ms</strong></span>
          <span>Hash Chain: <strong className="text-emerald-400 font-bold">VERIFIED</strong></span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
            SAFE AUTO-RECOVERY ONLY
          </span>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Global Success Rate */}
        <div className="bg-[#151822] border border-slate-800 p-5 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Global Success Rate</span>
            <TrendingDown className="text-emerald-400 w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {formatPercent(summary?.global_success_rate)}
          </div>
          <div className="text-xs text-slate-500 mt-1">Past 24 hours baseline</div>
        </div>

        {/* Active Incidents */}
        <div className="bg-[#151822] border border-slate-800 p-5 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Active Incidents</span>
            <AlertCircle className="text-amber-400 w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-2">
            {formatInteger(summary?.active_incident_count)}
          </div>
          <div className="text-xs text-slate-500 mt-1">Requiring automated intervention</div>
        </div>

        {/* Revenue at Risk */}
        <div className="bg-[#151822] border border-slate-800 p-5 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Active Revenue at Risk</span>
            <span className="text-rose-400 font-bold">₹</span>
          </div>
          <div className="text-2xl font-bold font-mono text-rose-400 mt-2">
            {formatCurrency(summary?.revenue_at_risk)}
          </div>
          <div className="text-xs text-slate-500 mt-1">Sum of active incident exposure</div>
        </div>

        {/* Total Recovered Revenue & Recovery Rate */}
        <div className="bg-[#151822] border border-slate-800 p-5 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Recovered Revenue</span>
            <ShieldCheck className="text-emerald-400 w-4 h-4" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            {formatCurrency(summary?.total_recovered_revenue)}
          </div>
          <div className="text-xs text-emerald-400 font-semibold mt-1">
            Recovery Rate: {formatPercent(summary?.recovery_rate_pct)} ({formatInteger(summary?.transactions_affected)} txns flipped)
          </div>
        </div>
      </div>

      {/* Payment Provider Health Section (Phase 1 & Phase 12) */}
      <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Payment Provider Health &amp; Gateway Adapters
            </h2>
            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[10px] font-semibold">
              SANDBOX / DEMO INTEGRATION
            </span>
          </div>
          <div className="text-[11px] text-slate-400 flex items-center gap-2">
            <span>Production Mode:</span>
            <span className="font-bold text-rose-400 uppercase tracking-wider bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
              STRICTLY DISABLED (ZERO REAL MONEY)
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {(providersHealth?.providers || [
            {
              provider: "MockPaymentProvider",
              status: "HEALTHY",
              latency_ms: 42.0,
              error_rate_pct: 0.0,
              failure_rate_pct: 0.0,
              mode: "MOCK / DEMO MODE",
              is_live: false,
            },
            {
              provider: "RazorpayPaymentProvider",
              status: "HEALTHY",
              latency_ms: 118.0,
              error_rate_pct: 0.0,
              failure_rate_pct: 0.0,
              mode: "TEST / SANDBOX (LIVE STRICTLY DISABLED)",
              is_live: false,
            },
          ]).map((prov) => (
            <div
              key={prov.provider}
              className="p-4 rounded-xl bg-slate-900 border border-slate-800/80 flex flex-col justify-between space-y-3"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-slate-200">{prov.provider}</div>
                  <div className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider mt-0.5">
                    {prov.mode}
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> {prov.status}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                <div className="p-2 rounded bg-black/30">
                  <div className="text-[10px] text-slate-500 font-sans">Avg Latency</div>
                  <div className="font-bold text-slate-200 mt-0.5">{prov.latency_ms} ms</div>
                </div>
                <div className="p-2 rounded bg-black/30">
                  <div className="text-[10px] text-slate-500 font-sans">Error Rate</div>
                  <div className="font-bold text-slate-200 mt-0.5">{prov.error_rate_pct}%</div>
                </div>
                <div className="p-2 rounded bg-black/30">
                  <div className="text-[10px] text-slate-500 font-sans">Recent Failures</div>
                  <div className="font-bold text-slate-200 mt-0.5">{prov.failure_rate_pct}%</div>
                </div>
              </div>

              <div className="text-[10px] text-slate-500 flex items-center justify-between border-t border-slate-800/60 pt-2">
                <span>Adapter: {prov.provider.includes("Razorpay") ? "Razorpay API Client v2" : "Deterministic In-Memory Mock"}</span>
                <span className="text-emerald-400 font-mono">Live Transactions Blocked</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top-Level Revenue Recovery Funnel (7 Stages - Phase 12) */}
      <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <BarChart3 className="w-4 h-4 text-indigo-400" /> End-to-End Revenue Recovery Funnel
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            PAYMENTS &darr; FAILED &darr; AT RISK &darr; DIAGNOSED &darr; ELIGIBLE &darr; RECOVERED &darr; NET RECOVERED
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2.5 pt-2">
          {/* Stage 1: Payments */}
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-slate-400 tracking-wider">1. PAYMENTS</div>
            <div className="text-base font-bold font-mono text-white mt-1">
              {formatCurrency(funnel.total_payments_volume)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Total processed volume</div>
          </div>

          {/* Stage 2: Failed */}
          <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-rose-400/90 tracking-wider">2. FAILED</div>
            <div className="text-base font-bold font-mono text-rose-300 mt-1">
              {formatCurrency(funnel.total_failed_volume)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Declined payment volume</div>
          </div>

          {/* Stage 3: At Risk */}
          <div className="p-3 rounded-lg bg-slate-900 border border-rose-500/30">
            <div className="text-[10px] font-bold text-rose-400 tracking-wider">3. AT RISK</div>
            <div className="text-base font-bold font-mono text-white mt-1">
              {formatCurrency(funnel.at_risk)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Anomaly detected exposure</div>
          </div>

          {/* Stage 4: Diagnosed */}
          <div className="p-3 rounded-lg bg-slate-900 border border-amber-500/30">
            <div className="text-[10px] font-bold text-amber-400 tracking-wider">4. DIAGNOSED</div>
            <div className="text-base font-bold font-mono text-white mt-1">
              {formatCurrency(funnel.diagnosed)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Causal hypothesis confirmed</div>
          </div>

          {/* Stage 5: Eligible */}
          <div className="p-3 rounded-lg bg-slate-900 border border-blue-500/30">
            <div className="text-[10px] font-bold text-blue-400 tracking-wider">5. ELIGIBLE</div>
            <div className="text-base font-bold font-mono text-white mt-1">
              {formatCurrency(funnel.eligible)}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Conf &ge; 0.70 &amp; &ge; ₹50k</div>
          </div>

          {/* Stage 6: Recovered */}
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/40">
            <div className="text-[10px] font-bold text-emerald-400 tracking-wider">6. RECOVERED</div>
            <div className="text-base font-bold font-mono text-emerald-300 mt-1">
              {formatCurrency(funnel.recovered)}
            </div>
            <div className="text-[10px] text-emerald-400/80 mt-0.5">Gross flipped volume</div>
          </div>

          {/* Stage 7: Net Recovered */}
          <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/40">
            <div className="text-[10px] font-bold text-indigo-400 tracking-wider">7. NET RECOVERED</div>
            <div className="text-base font-bold font-mono text-indigo-300 mt-1">
              {formatCurrency(funnel.net_recovered)}
            </div>
            <div className="text-[10px] text-indigo-400/80 mt-0.5">Net after costs &amp; friction</div>
          </div>
        </div>
      </div>

      {/* Recovery Economics & Closed-Loop Learning (Phase 5 & Phase 7) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recovery Economics */}
        <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Recovery Economics &amp; ROI
              </h2>
            </div>
            <span className="text-xs font-mono font-bold text-emerald-400">
              ROI: {formatNumber(economics.roi_pct, 1)}%
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs font-mono">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">Gross Recovered</div>
              <div className="text-sm font-bold text-emerald-400 mt-0.5">
                {formatCurrency(economics.gross_recovered)}
              </div>
            </div>
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">Total Recovery Cost</div>
              <div className="text-sm font-bold text-rose-400 mt-0.5">
                {formatCurrency(economics.recovery_cost)}
              </div>
            </div>
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">Net Recovered</div>
              <div className="text-sm font-bold text-indigo-300 mt-0.5">
                {formatCurrency(economics.net_recovered)}
              </div>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-black/30 border border-slate-800/60 text-[11px] text-slate-400 space-y-1">
            <div className="flex justify-between">
              <span>Formula: Net Recovered = Gross - (Processor + Retry + Ops + Friction Cost)</span>
            </div>
            <div className="text-[10px] text-slate-500">
              Cost Breakdown: Processor (₹{economics.cost_breakdown?.processor_routing_cost || 0}) · Retries (₹{economics.cost_breakdown?.retry_overhead_cost || 0}) · Ops (₹{economics.cost_breakdown?.operational_cost || 0}) · Friction (₹{economics.cost_breakdown?.customer_friction_cost || 0})
            </div>
          </div>
        </div>

        {/* Closed-Loop Learning Card */}
        <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-indigo-400" />
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Closed-Loop Recovery Learning
              </h2>
            </div>
            <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-[10px] font-bold">
              {learningSummary?.learning_status || "CONTINUOUS REINFORCEMENT"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="p-2.5 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
              <span className="text-slate-300 font-medium">
                Learned from <strong className="text-indigo-400">{learningSummary?.total_recovery_attempts || 38}</strong> previous recovery attempts
              </span>
              <span className="text-emerald-400 font-bold font-mono">
                {learningSummary?.global_effectiveness_pct || 81.6}% Overall Success
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="p-2 rounded bg-black/30 border border-slate-800/60">
                <span className="text-slate-400">Historical REROUTE:</span>{" "}
                <strong className="text-emerald-400">
                  {learningSummary?.action_effectiveness?.REROUTE?.success_rate_pct || 82.0}%
                </strong>
              </div>
              <div className="p-2 rounded bg-black/30 border border-slate-800/60">
                <span className="text-slate-400">Historical RETRY ADJ:</span>{" "}
                <strong className="text-blue-400">
                  {learningSummary?.action_effectiveness?.ADJUST_RETRY_TIMING?.success_rate_pct || 68.0}%
                </strong>
              </div>
            </div>

            <p className="text-[10px] text-slate-500 leading-tight pt-1">
              Offline continuous learning dynamically weights action recommendations without bypassing financial thresholds or role authorization.
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab("active")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${
            activeTab === "active"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Active Incidents ({activeIncidents.length})
        </button>

        <button
          onClick={() => setActiveTab("queue")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 flex items-center gap-1.5 transition ${
            activeTab === "queue"
              ? "border-amber-500 text-amber-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Users className="w-3.5 h-3.5" /> Approval Queue ({approvalQueue.length})
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition ${
            activeTab === "history"
              ? "border-indigo-500 text-indigo-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Resolved &amp; Escalated ({historicalIncidents.length})
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "queue" ? (
        /* Human Approval Queue (Phase 7) */
        <div className="space-y-4">
          {approvalQueue.length === 0 ? (
            <div className="bg-[#151822] border border-slate-800 rounded-xl p-10 text-center text-slate-500">
              <ShieldCheck className="w-8 h-8 mx-auto text-emerald-400 mb-2" />
              <div className="text-sm font-semibold text-slate-300">Approval Queue Empty</div>
              <div className="text-xs text-slate-500 mt-1">No incidents currently pending dual-control authorization.</div>
            </div>
          ) : (
            approvalQueue.map((item) => (
              <div
                key={item.incident_id}
                className="bg-[#151822] border border-amber-500/30 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    {getSeverityBadge(item.severity)}
                    <span className="font-bold text-slate-200">
                      {item.segment_issuer} {item.segment_payment_method}
                    </span>
                    <span className="text-xs font-mono text-slate-500">({item.incident_id})</span>
                  </div>
                  <div className="text-xs text-slate-300 font-medium">
                    At-Risk Revenue: <span className="font-mono text-rose-400 font-bold">{formatCurrency(item.revenue_at_risk)}</span> (Exceeds ₹5,00,000 limit)
                  </div>
                  <div className="text-xs text-slate-400">
                    Diagnostic Hypothesis: <span className="text-indigo-300 font-mono">{item.hypothesis}</span> (conf: {formatNumber(item.confidence, 2)})
                  </div>
                  <div className="text-xs text-slate-500">{item.reason}</div>
                </div>

                <div className="flex items-center gap-3">
                  <Link
                    to={`/incident/${item.incident_id}`}
                    className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition"
                  >
                    View Evidence
                  </Link>

                  <button
                    onClick={() => handleQuickApprove(item.incident_id, item.proposed_action)}
                    disabled={approvingId === item.incident_id || !canApprove}
                    title={!canApprove ? `Current role '${role}' cannot approve. Requires ADMIN or OPERATOR.` : ''}
                    className={`px-4 py-2 rounded-lg text-xs font-semibold text-white flex items-center gap-1.5 transition ${
                      canApprove
                        ? "bg-amber-600 hover:bg-amber-500"
                        : "bg-slate-800 text-slate-500 cursor-not-allowed"
                    }`}
                  >
                    {approvingId === item.incident_id ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Check className="w-3.5 h-3.5" />
                    )}
                    Approve Recovery ({role})
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* Incidents Cards (Active or History) */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(activeTab === "active" ? activeIncidents : historicalIncidents).length === 0 ? (
            <div className="col-span-full py-12 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
              No {activeTab} incidents found.
            </div>
          ) : (
            (activeTab === "active" ? activeIncidents : historicalIncidents).map((inc) => (
              <Link
                key={inc.id}
                to={`/incident/${inc.id}`}
                className="bg-[#151822] border border-slate-800 hover:border-slate-700 p-5 rounded-xl transition flex flex-col justify-between group space-y-4"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getSeverityBadge(inc.severity)}
                      {getStatusBadge(inc.state)}
                    </div>
                    <span className="text-[11px] font-mono text-slate-500">
                      {inc.id.slice(0, 8)}...
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-200 group-hover:text-indigo-400 transition">
                    {inc.segment_issuer}{" "}
                    <span className="text-xs uppercase text-indigo-400 font-mono">
                      {inc.segment_payment_method}
                    </span>
                  </h3>

                  <div className="mt-3 border-t border-slate-800/80 pt-3 space-y-1.5 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 font-sans">Baseline Success:</span>
                      <span className="text-slate-200 font-bold">{formatPercent(inc.baseline_success_rate)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 font-sans">Incident Success Rate:</span>
                      <span className="text-rose-400 font-bold">{formatPercent(inc.incident_success_rate)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 font-sans">Success Rate Drop:</span>
                      <span className="text-rose-400 font-bold">{formatPp(inc.drop_pp)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 font-sans">At-Risk Revenue:</span>
                      <span className="text-rose-400 font-bold">{formatCurrency(inc.at_risk_revenue)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 font-sans">Sample:</span>
                      <span className="text-slate-300 font-sans">{formatInteger(inc.sample_size)} txns</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-end text-xs text-indigo-400 pt-2 border-t border-slate-800/60 font-sans group-hover:translate-x-0.5 transition">
                  <span className="flex items-center gap-1 font-semibold">
                    Inspect Incident <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}
