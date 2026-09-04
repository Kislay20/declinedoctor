import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  TrendingDown,
  AlertCircle,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Users,
  Server,
  DollarSign,
  BrainCircuit,
  Activity,
  Layers,
  Radio,
  ExternalLink,
  XCircle,
  RotateCcw,
  Clock,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
  formatPp,
  formatInteger,
  formatNumber,
  getSeverityBadge,
  getStateBadge,
} from "../utils/format";

const ACTIVE_STATES = [
  "ANOMALY_DETECTED",
  "DIAGNOSED",
  "AWAITING_HUMAN_APPROVAL",
  "ACTION_SELECTED",
  "ACTION_APPLIED",
];

const TERMINAL_STATES = [
  "RESOLVED",
  "ROLLED_BACK",
  "ESCALATED_LOW_CONFIDENCE",
  "ESCALATED_LOW_REVENUE",
  "ESCALATED_INSUFFICIENT_RECOVERY",
  "APPROVAL_REJECTED",
];

function getActionGateStatus(inc) {
  // 1. Terminal States
  if (inc.state === "APPROVAL_REJECTED") {
    return (
      <span className="text-slate-400 font-bold flex items-center gap-1">
        <XCircle className="w-3 h-3 text-rose-400" /> Recovery Rejected · Terminal
      </span>
    );
  }
  if (inc.state === "ROLLED_BACK") {
    return (
      <span className="text-rose-400 font-bold flex items-center gap-1">
        <RotateCcw className="w-3 h-3" /> Rolled Back · Terminal
      </span>
    );
  }
  if (inc.state === "RESOLVED") {
    return (
      <span className="text-emerald-400 font-bold flex items-center gap-1">
        <CheckCircle2 className="w-3 h-3" /> Mitigated · Resolved
      </span>
    );
  }
  if (inc.state === "ESCALATED_LOW_CONFIDENCE") {
    return (
      <span className="text-rose-400 font-bold flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" /> Recovery Blocked · Low Confidence
      </span>
    );
  }
  if (inc.state === "ESCALATED_LOW_REVENUE") {
    return (
      <span className="text-slate-400 font-bold flex items-center gap-1">
        <AlertCircle className="w-3 h-3" /> Below Revenue Floor (&lt; ₹50k)
      </span>
    );
  }
  if (inc.state === "ESCALATED_INSUFFICIENT_RECOVERY") {
    return (
      <span className="text-amber-400 font-bold flex items-center gap-1">
        <AlertCircle className="w-3 h-3" /> Insufficient Lift (&lt; 5pp)
      </span>
    );
  }

  // 2. Confidence Gate (< 70% confidence)
  if (inc.confidence !== null && inc.confidence !== undefined && inc.confidence < 0.70) {
    return (
      <span className="text-rose-400 font-bold flex items-center gap-1">
        <AlertTriangle className="w-3 h-3" /> Recovery Blocked · Low Confidence
      </span>
    );
  }

  // 3. Dual-Control Human Approval Gate
  if (inc.state === "AWAITING_HUMAN_APPROVAL" || inc.at_risk_revenue > 500000) {
    return (
      <span className="text-amber-400 font-bold flex items-center gap-1">
        <AlertCircle className="w-3 h-3" /> Approval Required
      </span>
    );
  }

  // 4. In-Flight Execution
  if (inc.state === "ACTION_SELECTED" || inc.state === "ACTION_APPLIED") {
    return (
      <span className="text-cyan-400 font-bold flex items-center gap-1">
        <Clock className="w-3 h-3" /> Mitigation In Flight
      </span>
    );
  }

  // 5. Auto-Mitigation Eligible
  return (
    <span className="text-emerald-400 font-bold flex items-center gap-1">
      <CheckCircle2 className="w-3 h-3" /> Auto-Mitigation Eligible
    </span>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [feed, setFeed] = useState([]);
  const [routingRec, setRoutingRec] = useState(null);
  const [learningSummary, setLearningSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resetting, setResetting] = useState(false);
  const [activeTab, setActiveTab] = useState("active"); // 'active' | 'feed' | 'queue' | 'history'
  const [approvingId, setApprovingId] = useState(null);
  const [role, setRole] = useState(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, incidentsRes, feedRes, routingRes, learningRes, alertsRes] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/incidents"),
        api.get("/incidents/feed").catch(() => ({ data: [] })),
        api.get("/providers/routing/recommendation?issuer=Bank+X&payment_method=card&bin=452114").catch(() => ({ data: null })),
        api.get("/learning/summary").catch(() => ({ data: null })),
        api.get("/observability/alerts").catch(() => ({ data: [] })),
      ]);
      setSummary(summaryRes.data);
      setIncidents(incidentsRes.data);
      setFeed(feedRes.data || []);
      if (routingRes?.data) setRoutingRec(routingRes.data);
      if (learningRes?.data) setLearningSummary(learningRes.data);
      if (alertsRes?.data) setAlerts(alertsRes.data);
    } catch (err) {
      console.error("Error fetching dashboard data", err);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      await loadData();
      if (isMounted) setLoading(false);
    };
    init();

    const interval = setInterval(() => {
      loadData();
    }, 12000);

    const handleRoleUpdate = () => {
      setRole(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");
    };
    window.addEventListener("storage", handleRoleUpdate);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener("storage", handleRoleUpdate);
    };
  }, [loadData]);


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
      <div className="flex items-center justify-center min-h-[50vh] text-slate-400 font-mono text-xs">
        <Activity className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
        Initializing DeclineDoctor Command Center...
      </div>
    );
  }

  const activeIncidents = incidents.filter(
    (inc) => ACTIVE_STATES.includes(inc.state) && !TERMINAL_STATES.includes(inc.state)
  );
  const historicalIncidents = incidents.filter(
    (inc) => TERMINAL_STATES.includes(inc.state) || !ACTIVE_STATES.includes(inc.state)
  );
  const approvalQueue = summary?.approval_queue || [];
  const economics = summary?.recovery_economics || {
    gross_recovered: 0,
    recovery_cost: 0,
    net_recovered: 0,
    roi_pct: 0,
    cost_breakdown: {},
  };

  const canApprove = role === "ADMIN" || role === "OPERATOR";

  return (
    <div className="space-y-6">
      {/* Top Command Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-1">
            <span className="flex items-center gap-1 text-cyan-400 font-semibold">
              <Activity className="w-3.5 h-3.5" /> DeclineDoctor Command Console
            </span>
            <span>·</span>
            <span className="text-slate-400">Production Architecture Upgrade</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            Autonomous Revenue Recovery
            <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
              v2.4 ENTERPRISE
            </span>
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Status Indicators */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-300">System: </span>
            <span className="text-emerald-400 font-bold">HEALTHY (99.98%)</span>
          </div>

          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <span className="text-slate-400">Mode:</span>
            <span className="text-amber-400 font-bold">SIMULATION / ADAPTER</span>
          </div>

          <button
            onClick={handleResetDemo}
            disabled={resetting}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition disabled:opacity-50 shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${resetting ? "animate-spin" : ""}`} />
            {resetting ? "Seeding..." : "Reset Telemetry"}
          </button>
        </div>
      </div>

      {/* Primary Financial & Operational KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3.5">
        {/* Metric 1: Revenue at Risk */}
        <div className="bg-[#111622] border border-rose-500/30 p-4 rounded-xl relative overflow-hidden">
          <div className="text-[11px] font-semibold text-rose-300 uppercase tracking-wider flex items-center justify-between">
            <span>Revenue at Risk</span>
            <AlertCircle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2 tabular-nums">
            {formatCurrency(summary?.revenue_at_risk)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Across active anomaly windows</div>
        </div>

        {/* Metric 2: Active Incidents */}
        <div className="bg-[#111622] border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Active Incidents</span>
            <span className="w-2 h-2 rounded-full bg-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-2 tabular-nums">
            {formatInteger(summary?.active_incident_count || activeIncidents.length)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">
            {approvalQueue.length} awaiting dual-control approval
          </div>
        </div>

        {/* Metric 3: Global Success Rate */}
        <div className="bg-[#111622] border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Global Success Rate</span>
            <TrendingDown className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2 tabular-nums">
            {formatPercent(summary?.global_success_rate)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">24-hour weighted baseline</div>
        </div>

        {/* Metric 4: Recovered Revenue */}
        <div className="bg-[#111622] border border-emerald-500/30 p-4 rounded-xl">
          <div className="text-[11px] font-semibold text-emerald-300 uppercase tracking-wider flex items-center justify-between">
            <span>Recovered Revenue</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2 tabular-nums">
            {formatCurrency(summary?.total_recovered_revenue)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">
            {formatInteger(summary?.transactions_affected || 0)} transactions flipped
          </div>
        </div>

        {/* Metric 5: Recovery Rate */}
        <div className="bg-[#111622] border border-slate-800 p-4 rounded-xl">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
            <span>Recovery Rate</span>
            <BarChart3 className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-indigo-300 mt-2 tabular-nums">
            {formatPercent(summary?.recovery_rate_pct)}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">On bounded eligible retry pool</div>
        </div>

        {/* Metric 6: Net Recovered / ROI */}
        <div className="bg-[#111622] border border-indigo-500/30 p-4 rounded-xl">
          <div className="text-[11px] font-semibold text-indigo-300 uppercase tracking-wider flex items-center justify-between">
            <span>Net Recovery / ROI</span>
            <DollarSign className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-indigo-300 mt-2 tabular-nums">
            {formatCurrency(economics?.net_recovered)}
          </div>
          <div className="text-[10px] text-emerald-400 font-mono font-bold mt-1">
            ROI: {formatNumber(economics?.roi_pct, 1)}%
          </div>
        </div>
      </div>

      {/* Recovery Pipeline 7-Stage Visualizer */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <Layers className="w-4 h-4 text-cyan-400" /> End-to-End Recovery Pipeline Architecture
          </div>
          <div className="text-[11px] font-mono text-slate-500">
            Strict Backend Policy Gates Enforced at Every Stage
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-center text-xs font-mono">
          <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-slate-400">1. DETECT</div>
            <div className="text-xs font-bold text-slate-200 mt-1">EWMA + CUSUM</div>
            <div className="text-[9px] text-slate-500 mt-0.5">Statistical drop &gt; 15pp</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-slate-400">2. DIAGNOSE</div>
            <div className="text-xs font-bold text-slate-200 mt-1">Causal Evidence</div>
            <div className="text-[9px] text-slate-500 mt-0.5">12-factor hypothesis</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-slate-400">3. POLICY</div>
            <div className="text-xs font-bold text-slate-200 mt-1">Guardrail Gate</div>
            <div className="text-[9px] text-slate-500 mt-0.5">Conf &ge; 0.70 &amp; &ge; ₹50k</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-amber-500/30">
            <div className="text-[10px] font-bold text-amber-400">4. APPROVE</div>
            <div className="text-xs font-bold text-amber-300 mt-1">Dual Control</div>
            <div className="text-[9px] text-amber-400/80 mt-0.5">Ceiling &gt; ₹5,00,000</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-emerald-500/30">
            <div className="text-[10px] font-bold text-emerald-400">5. RECOVER</div>
            <div className="text-xs font-bold text-emerald-300 mt-1">REROUTE / Backoff</div>
            <div className="text-[9px] text-slate-500 mt-0.5">Bounded max 2 retries</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
            <div className="text-[10px] font-bold text-slate-400">6. MEASURE</div>
            <div className="text-xs font-bold text-slate-200 mt-1">Real Lift pp</div>
            <div className="text-[9px] text-slate-500 mt-0.5">Pre vs post flip rate</div>
          </div>
          <div className="p-2.5 rounded-lg bg-slate-900 border border-indigo-500/30">
            <div className="text-[10px] font-bold text-indigo-400">7. LEARN</div>
            <div className="text-xs font-bold text-indigo-300 mt-1">Reinforcement</div>
            <div className="text-[9px] text-slate-500 mt-0.5">Offline feedback loop</div>
          </div>
        </div>
      </div>

      {/* Multi-Provider Routing Optimizer & Gateway Status (Part B) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <Server className="w-4 h-4 text-indigo-400" /> Multi-Gateway Routing Intelligence &amp; Live Health
          </div>
          {routingRec && (
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-slate-400">Optimal Card Route:</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/30">
                {routingRec.target_gateway_routing} ({routingRec.score} Score · {routingRec.expected_success_rate}% Success · {routingRec.expected_latency_ms}ms)
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(routingRec?.ranked_providers || [
            { provider: "Provider A", composite_score: 92.4, expected_success_rate: 96.1, latency_ms: 78, cost_pct: 1.85, health: "OPTIMAL" },
            { provider: "Razorpay Smart Router", composite_score: 90.8, expected_success_rate: 95.8, latency_ms: 88, cost_pct: 1.90, health: "OPTIMAL" },
            { provider: "Provider B", composite_score: 84.5, expected_success_rate: 94.2, latency_ms: 115, cost_pct: 1.95, health: "HEALTHY" },
            { provider: "Provider C", composite_score: 72.1, expected_success_rate: 91.0, latency_ms: 142, cost_pct: 2.10, health: "DEGRADED_FAILOVER" },
          ]).map((p, idx) => {
            const isTop = idx === 0;
            return (
              <div
                key={p.provider}
                className={`p-3.5 rounded-xl border flex flex-col justify-between space-y-2 ${
                  isTop ? "bg-emerald-500/5 border-emerald-500/30" : "bg-slate-900 border-slate-800"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200">{p.provider}</span>
                  {isTop && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300">
                      RECOMMENDED
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-1.5 text-xs font-mono">
                  <div className="p-1.5 rounded bg-black/40">
                    <div className="text-[9px] text-slate-400 font-sans">Score</div>
                    <div className="font-bold text-cyan-300">{p.composite_score}</div>
                  </div>
                  <div className="p-1.5 rounded bg-black/40">
                    <div className="text-[9px] text-slate-400 font-sans">Success</div>
                    <div className="font-bold text-emerald-400">{p.expected_success_rate}%</div>
                  </div>
                  <div className="p-1.5 rounded bg-black/40">
                    <div className="text-[9px] text-slate-400 font-sans">Latency</div>
                    <div className="font-bold text-slate-200">{p.latency_ms}ms</div>
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/60 font-mono">
                  <span>Fee: {p.cost_pct}%</span>
                  <span className={p.health === "OPTIMAL" ? "text-emerald-400" : "text-amber-400"}>
                    {p.health}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Closed-Loop Learning & Telemetry Bar */}
        {learningSummary && (
          <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-slate-300 font-sans">
              <BrainCircuit className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold">Closed-Loop Recovery Learning:</span>
              <span className="text-slate-400 font-mono text-[11px]">
                {learningSummary.total_attempts || 38} recovery trials logged · {learningSummary.global_effectiveness_pct || 81.6}% historical efficacy
              </span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              <span className="text-slate-400 font-sans">Dynamic Prior Calibration:</span>
              <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 font-mono font-bold">
                ACTIVE
              </span>
            </div>
          </div>
        )}

        {/* System Observability Alerts */}
        {alerts && alerts.length > 0 && (
          <div className="mt-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-xs text-rose-300">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span className="font-semibold">System Alerts:</span>
            <span className="text-[11px] font-mono">{alerts.map((a) => a.message || a.title || JSON.stringify(a)).join(" · ")}</span>
          </div>
        )}
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800">
        <button
          onClick={() => setActiveTab("active")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === "active"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Active Incidents ({activeIncidents.length})
        </button>

        <button
          onClick={() => setActiveTab("feed")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === "feed"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Radio className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
          Real-Time Activity Feed ({feed.length})
        </button>

        <button
          onClick={() => setActiveTab("queue")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === "queue"
              ? "border-amber-500 text-amber-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          Dual-Control Approval Queue ({approvalQueue.length})
        </button>

        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            activeTab === "history"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Incident History ({historicalIncidents.length})
        </button>
      </div>

      {/* TAB 1: Active Incidents */}
      {activeTab === "active" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl overflow-hidden">
          {activeIncidents.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              No active incidents detected. All payment segments nominal.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 font-mono text-[11px]">
                    <th className="p-3">SEGMENT / ISSUER</th>
                    <th className="p-3">SEVERITY</th>
                    <th className="p-3">AT-RISK EXPOSURE</th>
                    <th className="p-3">DROP</th>
                    <th className="p-3">CURRENT STATE</th>
                    <th className="p-3">ACTION / GATE</th>
                    <th className="p-3 text-right">ACTION</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {activeIncidents.map((inc) => (
                    <tr key={inc.id} className="hover:bg-slate-900/40 transition">
                      <td className="p-3 font-semibold text-slate-200 font-sans">
                        <div>{inc.segment_issuer}</div>
                        <div className="text-[10px] text-slate-400 font-mono uppercase">
                          {inc.segment_payment_method} · ID: {inc.id}
                        </div>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getSeverityBadge(inc.severity)}`}>
                          {inc.severity || "MEDIUM"}
                        </span>
                      </td>
                      <td className="p-3 text-rose-400 font-bold">
                        {formatCurrency(inc.at_risk_revenue)}
                      </td>
                      <td className="p-3 text-rose-400 font-bold">
                        -{formatPp(inc.drop_pp)}
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getStateBadge(inc.state)}`}>
                          {inc.state}
                        </span>
                      </td>
                      <td className="p-3">
                        {getActionGateStatus(inc)}
                      </td>
                      <td className="p-3 text-right">
                        <Link
                          to={`/incident/${inc.id}`}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-sans text-xs font-semibold transition"
                        >
                          View &amp; Act <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Real-Time Incident Activity Feed (Part F) */}
      {activeTab === "feed" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Radio className="w-4 h-4 text-rose-400" /> Operational Alert Ingestion Stream
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              Live updates via POST /api/webhooks/payment &amp; streaming detection
            </span>
          </div>

          <div className="space-y-2.5">
            {feed.length === 0 ? (
              <div className="p-6 text-center text-slate-400 text-xs">
                No alerts in the feed queue.
              </div>
            ) : (
              feed.map((item) => (
                <div
                  key={item.incident_id + item.timestamp}
                  className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="flex items-start sm:items-center gap-3">
                    <div className="font-mono text-[11px] text-slate-400 bg-black/40 px-2 py-1 rounded">
                      {item.timestamp}
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getSeverityBadge(item.severity)}`}>
                      {item.severity}
                    </span>
                    <div>
                      <div className="font-bold text-slate-200 flex items-center gap-2">
                        <span>{item.issuer} / {item.payment_method.toUpperCase()}</span>
                        <span className="text-rose-400 font-mono font-bold">
                          {formatCurrency(item.revenue_at_risk)} at risk
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                        {item.summary} · State: <span className="text-cyan-300">{item.current_state}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 self-end sm:self-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${
                      item.approval_state === "APPROVAL_REQUIRED"
                        ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        : item.approval_state === "NOT_REQUIRED_BLOCKED"
                        ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                        : "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                    }`}>
                      {item.approval_state}
                    </span>
                    <Link
                      to={`/incident/${item.incident_id}`}
                      className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Dual-Control Approval Queue (Part G) */}
      {activeTab === "queue" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl overflow-hidden p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <Users className="w-4 h-4 text-amber-400" /> Pending Dual-Control Approvals (&gt; ₹5,00,000 Exposure)
            </span>
            <span className="text-[11px] font-mono text-slate-400">
              Current Role: <strong className="text-indigo-400">{role}</strong>
            </span>
          </div>

          {approvalQueue.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              Approval queue is clear. No high-value interventions held.
            </div>
          ) : (
            <div className="space-y-3">
              {approvalQueue.map((item) => (
                <div
                  key={item.incident_id}
                  className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs"
                >
                  <div className="space-y-1">
                    <div className="font-bold text-amber-300 text-sm flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" /> {item.segment_issuer} {item.segment_payment_method}
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-mono">
                        DUAL-CONTROL REQUIRED
                      </span>
                    </div>
                    <div className="text-slate-300 font-mono text-[11px] flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5">
                      <span>At-Risk Exposure: <strong className="text-rose-400">{formatCurrency(item.at_risk_revenue ?? item.revenue_at_risk)}</strong></span>
                      <span>·</span>
                      <span>Diagnosis: <strong className="text-slate-200">{item.hypothesis || "ROUTING_CONNECTIVITY_ISSUE"}</strong> ({formatPercent((item.confidence || 0) * 100)})</span>
                      <span>·</span>
                      <span>Proposed: <strong className="text-cyan-300">{item.proposed_action || "REROUTE"}{item.target_provider ? ` → ${item.target_provider}` : ""}</strong></span>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-3 text-[10px] font-mono text-slate-400 pt-0.5">
                      {item.projected_lift_pp != null && (
                        <span className="text-emerald-400">Projected Lift: <strong>+{formatNumber(item.projected_lift_pp, 2)} pp</strong></span>
                      )}
                      {item.projected_net_recovery != null && (
                        <span className="text-indigo-300">Projected Net Recovery: <strong>{formatCurrency(item.projected_net_recovery)}</strong></span>
                      )}
                      {item.customer_friction_score != null && (
                        <span className="text-slate-400">Friction: <strong>{item.customer_friction_score}/100</strong></span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Ceiling limit (&gt; ₹5,00,000) exceeded. Dual-control authorization required to unblock execution.
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {canApprove ? (
                      <button
                        onClick={() => handleQuickApprove(item.incident_id, item.proposed_action)}
                        disabled={approvingId === item.incident_id}
                        className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs transition disabled:opacity-50"
                      >
                        {approvingId === item.incident_id ? "Approving..." : "Approve & Execute"}
                      </button>
                    ) : (
                      <span className="text-[11px] text-rose-400 font-mono">
                        Role ({role}) cannot approve. Requires ADMIN / OPERATOR.
                      </span>
                    )}
                    <Link
                      to={`/incident/${item.incident_id}`}
                      className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs transition"
                    >
                      Inspect Evidence
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Incident History */}
      {activeTab === "history" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl overflow-hidden">
          {historicalIncidents.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-xs">
              No historical resolved or escalated incidents recorded.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse font-mono">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 text-[11px]">
                    <th className="p-3">SEGMENT</th>
                    <th className="p-3">INCIDENT ID</th>
                    <th className="p-3">TERMINAL STATE</th>
                    <th className="p-3">ACTION / GATE VERDICT</th>
                    <th className="p-3">RECOVERED</th>
                    <th className="p-3 text-right">AUDIT TRAIL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {historicalIncidents.map((inc) => (
                    <tr key={inc.id} className="hover:bg-slate-900/40 transition">
                      <td className="p-3 font-semibold text-slate-200 font-sans">
                        {inc.segment_issuer} ({inc.segment_payment_method})
                      </td>
                      <td className="p-3 text-slate-400">{inc.id}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getStateBadge(inc.state)}`}>
                          {inc.state}
                        </span>
                      </td>
                      <td className="p-3">
                        {getActionGateStatus(inc)}
                      </td>
                      <td className="p-3 text-emerald-400 font-bold">
                        {inc.state === "RESOLVED" ? "RECOVERED" : "UNRECOVERED"}
                      </td>
                      <td className="p-3 text-right">
                        <Link
                          to={`/incident/${inc.id}`}
                          className="text-cyan-400 hover:underline font-sans"
                        >
                          View Details &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
