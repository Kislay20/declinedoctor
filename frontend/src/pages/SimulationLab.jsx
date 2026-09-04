import { useState, useEffect } from "react";
import {
  Sliders,
  Play,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Sparkles,
  RefreshCw,
  TrendingUp,
  Zap,
  Users,
  BarChart2,
  ShieldAlert,
  Award,
  Clock,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  formatInteger,
} from "../utils/format";

export default function SimulationLab() {
  const [tab, setTab] = useState("sandbox"); // 'sandbox' | 'streaming' | 'experiments' | 'customers'

  // Sandbox State
  const [issuer, setIssuer] = useState("Bank X");
  const [paymentMethod, setPaymentMethod] = useState("card");
  const [txCount, setTxCount] = useState(500);
  const [failureRate, setFailureRate] = useState(0.40);
  const [avgAmount, setAvgAmount] = useState(1850);
  const [hypothesis, setHypothesis] = useState("ROUTING_CONNECTIVITY_ISSUE");
  const [action, setAction] = useState("REROUTE");
  const [confidence, setConfidence] = useState(0.85);
  const [humanApproved, setHumanApproved] = useState(false);

  const [loadingSim, setLoadingSim] = useState(false);
  const [simResult, setSimResult] = useState(null);

  // Streaming State
  const [streamAmount, setStreamAmount] = useState(1500);
  const [streamSuccess, setStreamSuccess] = useState(false);
  const [streamDeclineCode, setStreamDeclineCode] = useState("processor_declined");
  const [autoRecover, setAutoRecover] = useState(false);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamTrace, setStreamTrace] = useState(null);

  // Experiments State (Phase 6)
  const [experimentData, setExperimentData] = useState(null);
  const [loadingExp, setLoadingExp] = useState(false);

  // Customers State (Phase 8)
  const [customers, setCustomers] = useState([]);

  useEffect(() => {
    let isMounted = true;
    if (tab === "experiments" && !experimentData) {
      api.get("/experiments/summary")
        .then((res) => {
          if (isMounted) setExperimentData(res.data);
        })
        .catch((err) => console.error("Experiment fetch error", err));
    } else if (tab === "customers" && customers.length === 0) {
      api.get("/simulate/customers")
        .then((res) => {
          if (isMounted) setCustomers(res.data);
        })
        .catch((err) => console.error("Customer fetch error", err));
    }
    return () => {
      isMounted = false;
    };
  }, [tab, experimentData, customers.length]);

  const handleRunExperiment = async () => {
    setLoadingExp(true);
    try {
      const res = await api.post("/experiments/run", {
        strategy_a: "REROUTE",
        strategy_b: "ADJUST_RETRY_TIMING",
        candidate_action_a: "REROUTE",
        candidate_action_b: "ADJUST_RETRY_TIMING",
        sample_size: 100,
        segment: `${issuer} ${paymentMethod}`,
        segment_issuer: issuer,
        segment_payment_method: paymentMethod,
      });
      setExperimentData(res.data);
    } catch (err) {
      console.error("Experiment run error", err);
    } finally {
      setLoadingExp(false);
    }
  };

  const handleRunSimulation = async () => {
    setLoadingSim(true);
    try {
      const res = await api.post("/simulate/recovery", {
        segment_issuer: issuer,
        segment_payment_method: paymentMethod,
        transaction_count: txCount,
        failure_rate: failureRate,
        average_amount: avgAmount,
        diagnosis_hypothesis: hypothesis,
        action: action,
        confidence: confidence,
        human_approved: humanApproved,
        user_role: localStorage.getItem("declinedoctor_user_role") || "OPERATOR",
      });
      setSimResult(res.data);
    } catch (err) {
      console.error("Simulation error", err);
    } finally {
      setLoadingSim(false);
    }
  };

  const handleEmitStreamEvent = async () => {
    setStreamLoading(true);
    try {
      const res = await api.post("/simulate/stream", {
        issuer: issuer,
        payment_method: paymentMethod,
        amount: streamAmount,
        success: streamSuccess,
        decline_code: streamSuccess ? null : streamDeclineCode,
        decline_reason: streamSuccess ? null : "Simulated decline event",
        auto_recover: autoRecover,
        user_role: localStorage.getItem("declinedoctor_user_role") || "OPERATOR",
      });
      setStreamTrace(res.data);
    } catch (err) {
      console.error("Stream error", err);
    } finally {
      setStreamLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Sliders className="text-indigo-400 w-7 h-7" /> Recovery Simulation Lab
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Evaluate counterfactual recoveries, test edge-case decline rates, and simulate transaction event streams using production mathematics.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex flex-wrap bg-slate-900 border border-slate-800 p-1 rounded-lg self-start gap-1">
          <button
            onClick={() => setTab("sandbox")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition ${
              tab === "sandbox"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Policy &amp; Recovery Sandbox
          </button>
          <button
            onClick={() => setTab("streaming")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 transition ${
              tab === "streaming"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Radio className="w-3.5 h-3.5" /> Event Stream Mode
          </button>
          <button
            onClick={() => setTab("experiments")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 transition ${
              tab === "experiments"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <BarChart2 className="w-3.5 h-3.5" /> Recovery Experiments
          </button>
          <button
            onClick={() => setTab("customers")}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1 transition ${
              tab === "customers"
                ? "bg-indigo-600 text-white"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Users className="w-3.5 h-3.5" /> Customer Retry Safety
          </button>
        </div>
      </div>

      {tab === "sandbox" ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Simulation Controls (Left 5 cols) */}
          <div className="lg:col-span-5 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" /> Scenario Parameters
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 font-medium">Issuer</label>
                <select
                  value={issuer}
                  onChange={(e) => setIssuer(e.target.value)}
                  className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="Bank X">Bank X</option>
                  <option value="SBI">SBI</option>
                  <option value="ICICI">ICICI</option>
                  <option value="HDFC">HDFC</option>
                  <option value="Axis Bank">Axis Bank</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 font-medium">Payment Method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="card">card</option>
                  <option value="upi">upi</option>
                  <option value="netbanking">netbanking</option>
                </select>
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-400">Transaction Batch Size</span>
                <span className="text-indigo-300 font-mono font-bold">{txCount} txns</span>
              </div>
              <input
                type="range"
                min="50"
                max="5000"
                step="50"
                value={txCount}
                onChange={(e) => setTxCount(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-400">Simulated Failure Rate</span>
                <span className="text-rose-400 font-mono font-bold">{(failureRate * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.95"
                step="0.05"
                value={failureRate}
                onChange={(e) => setFailureRate(Number(e.target.value))}
                className="w-full accent-rose-500"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 font-medium">Average Ticket Size (₹)</label>
              <input
                type="number"
                value={avgAmount}
                onChange={(e) => setAvgAmount(Number(e.target.value))}
                className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="border-t border-slate-800 pt-3 space-y-3">
              <div>
                <label className="text-xs text-slate-400 font-medium">Diagnosis Hypothesis</label>
                <select
                  value={hypothesis}
                  onChange={(e) => setHypothesis(e.target.value)}
                  className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="ROUTING_CONNECTIVITY_ISSUE">ROUTING_CONNECTIVITY_ISSUE</option>
                  <option value="BIN_LEVEL_TEMPORARY_ISSUE">BIN_LEVEL_TEMPORARY_ISSUE</option>
                  <option value="ISSUER_SIDE_DECLINE">ISSUER_SIDE_DECLINE</option>
                  <option value="INSUFFICIENT_SIGNAL">INSUFFICIENT_SIGNAL</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 font-medium">Candidate Action</label>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                >
                  <option value="REROUTE">REROUTE (42% effect size)</option>
                  <option value="ADJUST_RETRY_TIMING">ADJUST_RETRY_TIMING (21% effect size)</option>
                  <option value="SUPPRESS_RETRIES">SUPPRESS_RETRIES (0% effect size)</option>
                </select>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Diagnostic Confidence</span>
                  <span className="text-emerald-400 font-mono font-bold">{(confidence * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-slate-300">Human Approval Granted</span>
                <input
                  type="checkbox"
                  checked={humanApproved}
                  onChange={(e) => setHumanApproved(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 focus:ring-0 bg-slate-900 border-slate-700"
                />
              </div>
            </div>

            <button
              onClick={handleRunSimulation}
              disabled={loadingSim}
              className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 font-semibold text-sm text-white flex items-center justify-center gap-2 transition disabled:opacity-50"
            >
              {loadingSim ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Run Genuine Recovery Simulation
            </button>
          </div>

          {/* Simulation Output (Right 7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            {simResult ? (
              <>
                {/* Status & Outcome Banner */}
                <div
                  className={`p-4 rounded-xl border flex items-center justify-between ${
                    simResult.projected_outcome === "RESOLVED"
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      : simResult.projected_outcome === "BLOCKED"
                      ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                      : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {simResult.projected_outcome === "RESOLVED" ? (
                      <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="w-6 h-6 text-amber-400" />
                    )}
                    <div>
                      <div className="font-bold text-sm">
                        Projected Result: {simResult.projected_outcome}
                      </div>
                      <div className="text-xs opacity-90">
                        {simResult.safety_evaluation.reason}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs font-mono px-2.5 py-1 rounded bg-black/40 border border-white/10">
                    {simResult.safety_evaluation.status}
                  </div>
                </div>

                {/* Metrics Comparison Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-[#151822] border border-slate-800 p-3.5 rounded-xl">
                    <div className="text-xs text-slate-400">At-Risk Revenue</div>
                    <div className="text-base font-bold font-mono text-rose-400 mt-1">
                      {formatCurrency(simResult.pre_metrics.at_risk_revenue)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {formatInteger(simResult.pre_metrics.total_failures)} failures
                    </div>
                  </div>

                  <div className="bg-[#151822] border border-slate-800 p-3.5 rounded-xl">
                    <div className="text-xs text-slate-400">Recovered Revenue</div>
                    <div className="text-base font-bold font-mono text-emerald-400 mt-1">
                      {formatCurrency(simResult.post_metrics.recovered_revenue)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {formatInteger(simResult.post_metrics.transactions_flipped)} flipped
                    </div>
                  </div>

                  <div className="bg-[#151822] border border-slate-800 p-3.5 rounded-xl">
                    <div className="text-xs text-slate-400">Pre Success Rate</div>
                    <div className="text-base font-bold font-mono text-slate-300 mt-1">
                      {formatPercent(simResult.pre_metrics.pre_success_rate)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">initial window</div>
                  </div>

                  <div className="bg-[#151822] border border-slate-800 p-3.5 rounded-xl">
                    <div className="text-xs text-slate-400">Post Success Rate</div>
                    <div className="text-base font-bold font-mono text-indigo-300 mt-1 flex items-center gap-1">
                      {formatPercent(simResult.post_metrics.post_success_rate)}
                      <span className="text-emerald-400 text-xs">
                        +{formatNumber(simResult.post_metrics.improvement_pp, 2)} pp
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">simulated post-recovery</div>
                  </div>
                </div>

                {/* Safety Gates Breakdown */}
                <div className="bg-[#151822] border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Backend Policy Gate Evaluations
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Confidence Gate (&ge; 0.70):</span>
                      <span
                        className={`font-semibold ${
                          simResult.safety_evaluation.confidence_check.passed
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }`}
                      >
                        {simResult.safety_evaluation.confidence_check.value} (
                        {simResult.safety_evaluation.confidence_check.passed ? "PASSED" : "BLOCKED"})
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Revenue Floor (&ge; ₹50k):</span>
                      <span
                        className={`font-semibold ${
                          simResult.safety_evaluation.revenue_floor_check.passed
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }`}
                      >
                        ₹{simResult.safety_evaluation.revenue_floor_check.value.toLocaleString()} (
                        {simResult.safety_evaluation.revenue_floor_check.passed ? "PASSED" : "BLOCKED"})
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Revenue Ceiling (&le; ₹500k):</span>
                      <span
                        className={`font-semibold ${
                          simResult.safety_evaluation.revenue_ceiling_check.requires_approval
                            ? "text-amber-400"
                            : "text-emerald-400"
                        }`}
                      >
                        {simResult.safety_evaluation.revenue_ceiling_check.requires_approval
                          ? "HUMAN APPROVAL REQUIRED"
                          : "AUTO-APPROVED"}
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                      <span className="text-slate-400">Action Compatibility:</span>
                      <span
                        className={`font-semibold ${
                          simResult.is_compatible ? "text-emerald-400" : "text-rose-400"
                        }`}
                      >
                        {simResult.is_compatible ? "COMPATIBLE" : `INCOMPATIBLE (Expected ${simResult.expected_action})`}
                      </span>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-[#151822] border border-dashed border-slate-800 rounded-xl p-12 text-center text-slate-500">
                <Sliders className="w-10 h-10 mx-auto text-slate-600 mb-3" />
                <div className="text-sm font-medium text-slate-300">No Simulation Executed Yet</div>
                <div className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Adjust the scenario parameters on the left and click "Run Genuine Recovery Simulation" to project outcomes.
                </div>
              </div>
            )}
          </div>
        </div>
      ) : tab === "streaming" ? (
        /* Event Stream Mode */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" /> Ingest Live Event
            </h2>
            <p className="text-xs text-slate-400">
              Inject a transaction event into the continuous monitoring loop: Transaction Event &rarr; Detection &rarr; Diagnosis &rarr; Policy &rarr; Recovery.
            </p>

            <div>
              <label className="text-xs text-slate-400 font-medium">Transaction Amount (₹)</label>
              <input
                type="number"
                value={streamAmount}
                onChange={(e) => setStreamAmount(Number(e.target.value))}
                className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200"
              />
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800">
              <span className="text-xs text-slate-300">Transaction Status</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setStreamSuccess(true)}
                  className={`px-3 py-1 rounded text-xs font-semibold ${
                    streamSuccess ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
                  }`}
                >
                  SUCCESS
                </button>
                <button
                  onClick={() => setStreamSuccess(false)}
                  className={`px-3 py-1 rounded text-xs font-semibold ${
                    !streamSuccess ? "bg-rose-600 text-white" : "bg-slate-800 text-slate-400"
                  }`}
                >
                  FAILED
                </button>
              </div>
            </div>

            {!streamSuccess && (
              <div>
                <label className="text-xs text-slate-400 font-medium">Decline Code</label>
                <select
                  value={streamDeclineCode}
                  onChange={(e) => setStreamDeclineCode(e.target.value)}
                  className="w-full mt-1 bg-slate-900 border border-slate-700 rounded-lg p-2 text-sm text-slate-200"
                >
                  <option value="processor_declined">processor_declined</option>
                  <option value="gateway_timeout">gateway_timeout</option>
                  <option value="try_again_later">try_again_later</option>
                  <option value="insufficient_funds">insufficient_funds</option>
                  <option value="velocity_limit">velocity_limit</option>
                </select>
              </div>
            )}

            <div className="flex items-center justify-between p-2 rounded-lg bg-slate-900 border border-slate-800">
              <span className="text-xs text-slate-300">Auto-execute Recovery if Safe</span>
              <input
                type="checkbox"
                checked={autoRecover}
                onChange={(e) => setAutoRecover(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600"
              />
            </div>

            <button
              onClick={handleEmitStreamEvent}
              disabled={streamLoading}
              className="w-full py-2.5 px-4 rounded-lg bg-amber-600 hover:bg-amber-500 font-semibold text-sm text-white flex items-center justify-center gap-2 transition disabled:opacity-50"
            >
              {streamLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Radio className="w-4 h-4" />
              )}
              Emit Stream Event
            </button>
          </div>

          <div className="lg:col-span-7 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" /> Pipeline Processing Trace
            </h2>

            {streamTrace ? (
              <div className="space-y-3">
                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Transaction ID:</span>
                  <span className="text-xs font-mono text-indigo-300">{streamTrace.transaction_id}</span>
                </div>

                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Lifecycle Stage:</span>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {streamTrace.lifecycle_stage}
                  </span>
                </div>

                {streamTrace.incident_id && (
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-400">Matched Incident:</span>
                    <span className="text-xs font-mono text-amber-300">{streamTrace.incident_id}</span>
                  </div>
                )}

                {streamTrace.hypothesis && (
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-400">Diagnostic Hypothesis:</span>
                    <span className="text-xs font-medium text-slate-200">
                      {streamTrace.hypothesis} (conf: {streamTrace.confidence})
                    </span>
                  </div>
                )}

                {streamTrace.safety_check && (
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                    <div className="text-xs font-semibold text-slate-400 mb-1">Policy Gate Status:</div>
                    <div className="text-xs text-slate-300">
                      Status: <span className="font-bold text-amber-400">{streamTrace.safety_check.status}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {streamTrace.safety_check.reason}
                    </div>
                  </div>
                )}

                {/* 9-Stage Event Lifecycle Trace (Phase 2) */}
                {streamTrace.pipeline_trace && streamTrace.pipeline_trace.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-slate-800">
                    <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-indigo-400" /> 9-Stage Event Pipeline Trace:
                    </div>
                    <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                      {streamTrace.pipeline_trace.map((step, idx) => (
                        <div
                          key={idx}
                          className="p-2.5 rounded bg-black/40 border border-slate-800/80 flex items-start justify-between text-xs font-mono"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="text-slate-500 text-[10px]">{step.timestamp}</span>
                              <span className="font-bold text-indigo-300">{step.stage}</span>
                            </div>
                            <div className="text-[11px] text-slate-300 font-sans">{step.details}</div>
                          </div>
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold">
                            {step.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-12 text-center text-slate-500 border border-dashed border-slate-800 rounded-xl">
                Emit an event to see the step-by-step pipeline execution trace.
              </div>
            )}
          </div>
        </div>
      ) : tab === "experiments" ? (
        /* Recovery Strategy Experiment Lab (Phase 6) */
        <div className="space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#151822] border border-slate-800 p-5 rounded-xl">
            <div>
              <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
                <BarChart2 className="w-5 h-5 text-indigo-400" /> Recovery Strategy Experiment (Cohort A vs B)
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Deterministic simulation comparing recovery actions on identical failure distributions. Live customer traffic is never partitioned.
              </p>
            </div>
            <button
              onClick={handleRunExperiment}
              disabled={loadingExp}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingExp ? "animate-spin" : ""}`} />
              Run New Experiment (N=100)
            </button>
          </div>

          {experimentData && (
            <div className="space-y-4">
              {/* Winner Banner */}
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Award className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                  <div>
                    <div className="text-xs font-bold text-emerald-300 uppercase tracking-wider">
                      Statistical Winner: {experimentData.winner}
                    </div>
                    <div className="text-xs text-slate-300 mt-0.5">
                      {experimentData.recommendation_rationale}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="px-2 py-1 rounded bg-black/40 text-emerald-400 border border-emerald-500/20">
                    p-value: {experimentData.p_value}
                  </span>
                  <span className="px-2 py-1 rounded bg-black/40 text-slate-200 border border-slate-800">
                    Confidence: {experimentData.confidence_level_pct}%
                  </span>
                </div>
              </div>

              {/* Side-by-Side Comparison Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Cohort A */}
                <div className="bg-[#151822] border border-indigo-500/40 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span className="text-xs font-bold font-mono text-indigo-300">
                      COHORT A: {experimentData.cohort_a?.strategy || experimentData.cohort_a?.action || "REROUTE"}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      N = {experimentData.cohort_size || experimentData.cohort_a?.sample_count} txns
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Recovery Rate</div>
                      <div className="text-base font-bold text-emerald-400 mt-0.5">
                        {experimentData.cohort_a?.recovery_rate_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Average Lift</div>
                      <div className="text-base font-bold text-indigo-300 mt-0.5">
                        +{experimentData.cohort_a?.average_lift_pp ?? experimentData.cohort_a?.avg_lift_pp} pp
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Recovered Revenue</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {formatCurrency(experimentData.cohort_a?.net_recovered_revenue ?? experimentData.cohort_a?.recovered_revenue ?? experimentData.cohort_a?.gross_recovered_revenue)}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Friction Score</div>
                      <div className="text-base font-bold text-slate-300 mt-0.5">
                        {experimentData.cohort_a?.friction_score ?? experimentData.cohort_a?.customer_friction_score} / 100
                      </div>
                    </div>
                  </div>
                </div>

                {/* Cohort B */}
                <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <span className="text-xs font-bold font-mono text-amber-300">
                      COHORT B: {experimentData.cohort_b?.strategy || experimentData.cohort_b?.action || "ADJUST_RETRY_TIMING"}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      N = {experimentData.cohort_size || experimentData.cohort_b?.sample_count} txns
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Recovery Rate</div>
                      <div className="text-base font-bold text-emerald-400 mt-0.5">
                        {experimentData.cohort_b?.recovery_rate_pct}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Average Lift</div>
                      <div className="text-base font-bold text-amber-300 mt-0.5">
                        +{experimentData.cohort_b?.average_lift_pp ?? experimentData.cohort_b?.avg_lift_pp} pp
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Recovered Revenue</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {formatCurrency(experimentData.cohort_b?.net_recovered_revenue ?? experimentData.cohort_b?.recovered_revenue ?? experimentData.cohort_b?.gross_recovered_revenue)}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-sans">Friction Score</div>
                      <div className="text-base font-bold text-slate-300 mt-0.5">
                        {experimentData.cohort_b?.friction_score ?? experimentData.cohort_b?.customer_friction_score} / 100
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-black/30 border border-slate-800 text-[11px] text-slate-500">
                {experimentData.simulation_disclaimer}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Customer Retry Safety & Cooldowns (Phase 8) */
        <div className="space-y-4">
          <div className="bg-[#151822] border border-slate-800 p-5 rounded-xl">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-rose-400" /> Customer-Level Recovery Safety Guardrails
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Zero PII exposure. Anonymized customer identifiers enforce retry caps and cooldowns to prevent customer fatigue and card network penalties.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(customers.length > 0 ? customers : [
              {
                customer_id: "CUST_1042",
                issuer: "Bank X",
                payment_method: "card",
                failed_attempts: 3,
                retries_used: 2,
                friction_score: 85.0,
                cooldown_active: true,
                safety_status: "LOCKED_MAX_RETRIES",
                enforced_action: "SUPPRESS_RETRIES",
              },
              {
                customer_id: "CUST_2081",
                issuer: "HDFC",
                payment_method: "netbanking",
                failed_attempts: 1,
                retries_used: 1,
                friction_score: 35.0,
                cooldown_active: false,
                safety_status: "RETRY_ALLOWED",
                enforced_action: "INTELLIGENT_RETRY",
              },
              {
                customer_id: "CUST_3190",
                issuer: "SBI",
                payment_method: "upi",
                failed_attempts: 4,
                retries_used: 2,
                friction_score: 92.0,
                cooldown_active: true,
                safety_status: "LOCKED_COOLDOWN_ACTIVE",
                enforced_action: "SUPPRESS_RETRIES",
              },
            ]).map((cust) => (
              <div
                key={cust.customer_id}
                className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold font-mono text-slate-200">
                    {cust.customer_id}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    cust.safety_status.includes("LOCKED")
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                      : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  }`}>
                    {cust.safety_status}
                  </span>
                </div>

                <div className="text-xs text-slate-400">
                  {cust.issuer} · {cust.payment_method.toUpperCase()}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Failures</div>
                    <div className="font-bold text-rose-400 mt-0.5">{cust.failed_attempts}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Retries Used</div>
                    <div className="font-bold text-amber-400 mt-0.5">{cust.retries_used} / 2 limit</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Friction Score</div>
                    <div className="font-bold text-slate-200 mt-0.5">{cust.friction_score}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Enforced Action</div>
                    <div className="font-bold text-indigo-300 mt-0.5">{cust.enforced_action}</div>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-800/80 leading-relaxed">
                  {cust.retries_used >= 2
                    ? "Retry cap reached / repeated failure pattern. Automated retries strictly suppressed to protect customer trust."
                    : "Within safe recovery limits. Single bounded retry eligible."}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
