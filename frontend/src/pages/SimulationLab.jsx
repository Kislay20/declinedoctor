import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Sliders,
  Radio,
  Users,
  ShieldAlert,
  Award,
  Server,
  Send,
  Activity,
  RotateCcw,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
} from "../utils/format";

const DEFAULT_ROUTING_BINS = [
  { bin: "452114", issuer: "Bank X", card_network: "Visa", card_tier: "Signature Platinum Debit", label: "452114 (Bank X Visa Signature Platinum Debit)" },
  { bin: "524188", issuer: "HDFC", card_network: "Mastercard", card_tier: "World Elite Credit", label: "524188 (HDFC Mastercard World Elite Credit)" },
  { bin: "401200", issuer: "SBI", card_network: "Visa", card_tier: "Classic Global Debit", label: "401200 (SBI Visa Classic Global Debit)" },
  { bin: "411111", issuer: "ICICI", card_network: "Visa", card_tier: "Commercial Purchasing Card", label: "411111 (ICICI Visa Commercial Purchasing Card)" },
  { bin: "476543", issuer: "ICICI", card_network: "Visa", card_tier: "Coral Platinum Card", label: "476543 (ICICI Visa Coral Platinum Card)" },
];

const ISSUER_CANONICAL_BINS = {
  "Bank X": "452114",
  "ICICI": "476543",
  "SBI": "401200",
  "HDFC": "524188",
};

export default function SimulationLab() {
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get("tab") || "policy";
  const [tab, setTab] = useState(initialTab);

  // Policy Sandbox State
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

  // Streaming State & Webhook Probe
  const [streamAmount, setStreamAmount] = useState(1500);
  const [streamSuccess, setStreamSuccess] = useState(false);
  const [streamDeclineCode, setStreamDeclineCode] = useState("processor_declined");
  const [autoRecover, setAutoRecover] = useState(false);
  const [streamLoading, setStreamLoading] = useState(false);
  const [streamTrace, setStreamTrace] = useState(null);
  const [streamError, setStreamError] = useState(null);
  const [webhookResult, setWebhookResult] = useState(null);

  // Experiments State
  const [experimentData, setExperimentData] = useState(null);
  const [loadingExp, setLoadingExp] = useState(false);

  // Customers State
  const [customers, setCustomers] = useState([]);

  // Provider Optimizer State
  const [providerOptResult, setProviderOptResult] = useState(null);
  const [optIssuer, setOptIssuer] = useState("Bank X");
  const [optMethod, setOptMethod] = useState("card");
  const [optBin, setOptBin] = useState("452114");
  const [optDecline, setOptDecline] = useState("processor_declined");
  const [simulatedDegradedProvider, setSimulatedDegradedProvider] = useState("none");
  const [loadingOpt, setLoadingOpt] = useState(false);
  const [availableBins, setAvailableBins] = useState(DEFAULT_ROUTING_BINS);

  const fetchRoutingRecommendation = useCallback((
    currentIssuer = optIssuer,
    currentMethod = optMethod,
    currentBin = optBin,
    currentDecline = optDecline,
    degraded = simulatedDegradedProvider
  ) => {
    const degradedQuery = degraded && degraded !== "none" ? `&current_degraded_provider=${encodeURIComponent(degraded)}` : "";
    api.get(`/providers/routing/recommendation?issuer=${encodeURIComponent(currentIssuer)}&payment_method=${encodeURIComponent(currentMethod)}&bin=${encodeURIComponent(currentBin)}&decline_reason=${encodeURIComponent(currentDecline)}${degradedQuery}`)
      .then((res) => {
        if (res.data) setProviderOptResult(res.data);
      })
      .catch((err) => console.error("Routing update error", err));
  }, [optIssuer, optMethod, optBin, optDecline, simulatedDegradedProvider]);

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
    } else if (tab === "providers") {
      api.get("/providers/routing/bins")
        .then((res) => {
          if (isMounted && Array.isArray(res.data) && res.data.length > 0) {
            setAvailableBins(res.data);
          }
        })
        .catch((err) => console.error("Provider bins fetch error", err));

      if (!providerOptResult) {
        fetchRoutingRecommendation(optIssuer, optMethod, optBin, optDecline, simulatedDegradedProvider);
      }
    }
    return () => {
      isMounted = false;
    };
  }, [tab, experimentData, customers.length, providerOptResult, optIssuer, optMethod, optBin, optDecline, simulatedDegradedProvider, fetchRoutingRecommendation]);

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

  const handleInjectStreamEvent = async () => {
    setStreamLoading(true);
    setStreamError(null);
    try {
      const res = await api.post("/simulate/stream_event", {
        amount: streamAmount,
        issuer: issuer,
        payment_method: paymentMethod,
        success: streamSuccess,
        decline_code: streamSuccess ? null : streamDeclineCode,
        auto_recover: autoRecover,
        user_role: localStorage.getItem("declinedoctor_user_role") || "OPERATOR",
      });
      setStreamTrace(res.data);
    } catch (err) {
      console.error("Stream event error", err);
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
        : (typeof detail === "string" ? detail : (err.message || "Failed to inject stream event"));
      setStreamError(msg);
    } finally {
      setStreamLoading(false);
    }
  };

  const handleSendWebhook = async () => {
    setStreamLoading(true);
    setStreamError(null);
    try {
      const res = await api.post("/webhooks/payment", {
        payment_id: `pay_probe_${Date.now()}`,
        amount: streamAmount,
        currency: "INR",
        status: streamSuccess ? "captured" : "failed",
        issuer: issuer,
        payment_method: paymentMethod,
        card_bin: ISSUER_CANONICAL_BINS[issuer] || "452114",
        decline_code: streamSuccess ? null : streamDeclineCode,
        decline_reason: streamSuccess ? null : "Routing partner timeout probe",
      });
      setWebhookResult(res.data);
      if (res.data?.pipeline_result) {
        setStreamTrace(res.data.pipeline_result);
      }
    } catch (err) {
      console.error("Webhook probe error", err);
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
        : (typeof detail === "string" ? detail : (err.message || "Webhook probe failed"));
      setStreamError(msg);
    } finally {
      setStreamLoading(false);
    }
  };

  const handleBinChange = (selectedBin) => {
    setOptBin(selectedBin);
    const matched = availableBins.find((b) => b.bin === selectedBin);
    const newIssuer = matched?.issuer || optIssuer;
    if (matched?.issuer) {
      setOptIssuer(matched.issuer);
    }
    fetchRoutingRecommendation(newIssuer, optMethod, selectedBin, optDecline, simulatedDegradedProvider);
  };

  const handleIssuerChange = (selectedIssuer) => {
    setOptIssuer(selectedIssuer);
    const currentBinMatch = availableBins.find((b) => b.bin === optBin);
    let targetBin = optBin;
    if (!currentBinMatch || currentBinMatch.issuer !== selectedIssuer) {
      const canonicalBin = ISSUER_CANONICAL_BINS[selectedIssuer] || availableBins.find((b) => b.issuer === selectedIssuer)?.bin;
      if (canonicalBin) {
        targetBin = canonicalBin;
        setOptBin(canonicalBin);
      }
    }
    fetchRoutingRecommendation(selectedIssuer, optMethod, targetBin, optDecline, simulatedDegradedProvider);
  };

  const handleDegradedProviderChange = (providerVal) => {
    setSimulatedDegradedProvider(providerVal);
    fetchRoutingRecommendation(optIssuer, optMethod, optBin, optDecline, providerVal);
  };

  const handleScoreProviderRouting = async () => {
    setLoadingOpt(true);
    try {
      const res = await api.post("/providers/routing/score", {
        issuer: optIssuer,
        payment_method: optMethod,
        bin: optBin,
        decline_reason: optDecline,
        current_degraded_provider: simulatedDegradedProvider === "none" ? null : simulatedDegradedProvider,
      });
      setProviderOptResult(res.data);
    } catch (err) {
      console.error("Routing score error", err);
    } finally {
      setLoadingOpt(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2.5 text-white">
            <Sliders className="w-6 h-6 text-cyan-400" /> Simulation Lab &amp; Analytics
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Offline cohort experiments, parameter stress-testing, real-time event pipeline tracing, and multi-provider routing.
          </p>
        </div>
      </div>

      {/* 5 Clear Tabs Navigation (Part K Spec) */}
      <div className="flex items-center gap-2 border-b border-slate-800 overflow-x-auto">
        <button
          onClick={() => setTab("policy")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            tab === "policy"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Sliders className="w-3.5 h-3.5" /> 1. Policy Simulator
        </button>

        <button
          onClick={() => setTab("streaming")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            tab === "streaming"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Radio className="w-3.5 h-3.5 text-rose-400" /> 2. Event Stream &amp; Webhook Probe
        </button>

        <button
          onClick={() => setTab("experiments")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            tab === "experiments"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Award className="w-3.5 h-3.5 text-amber-400" /> 3. Recovery Experiments (A/B)
        </button>

        <button
          onClick={() => setTab("customers")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            tab === "customers"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Users className="w-3.5 h-3.5 text-indigo-400" /> 4. Customer Safety &amp; Retry Caps
        </button>

        <button
          onClick={() => setTab("providers")}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition flex items-center gap-2 ${
            tab === "providers"
              ? "border-cyan-500 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Server className="w-3.5 h-3.5 text-emerald-400" /> 5. Provider Routing Optimizer
        </button>
      </div>

      {/* TAB 1: Policy Simulator */}
      {tab === "policy" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Simulation Parameters
            </h2>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Issuer</label>
                <select
                  value={issuer}
                  onChange={(e) => setIssuer(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200"
                >
                  <option value="Bank X">Bank X</option>
                  <option value="ICICI">ICICI</option>
                  <option value="SBI">SBI</option>
                  <option value="HDFC">HDFC</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Payment Method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200"
                >
                  <option value="card">card</option>
                  <option value="upi">upi</option>
                  <option value="netbanking">netbanking</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Hypothesis</label>
                <select
                  value={hypothesis}
                  onChange={(e) => setHypothesis(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                >
                  <option value="ROUTING_CONNECTIVITY_ISSUE">ROUTING_CONNECTIVITY_ISSUE</option>
                  <option value="BIN_LEVEL_TEMPORARY_ISSUE">BIN_LEVEL_TEMPORARY_ISSUE</option>
                  <option value="ISSUER_SIDE_DECLINE">ISSUER_SIDE_DECLINE</option>
                  <option value="INSUFFICIENT_SIGNAL">INSUFFICIENT_SIGNAL</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Proposed Action</label>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                >
                  <option value="REROUTE">REROUTE</option>
                  <option value="ADJUST_RETRY_TIMING">ADJUST_RETRY_TIMING</option>
                  <option value="SUPPRESS_RETRIES">SUPPRESS_RETRIES</option>
                </select>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-slate-400 block mb-1">Tx Count</label>
                  <input
                    type="number"
                    value={txCount}
                    onChange={(e) => setTxCount(parseInt(e.target.value) || 0)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-slate-200 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Fail Rate (%)</label>
                  <input
                    type="number"
                    step="0.05"
                    value={Math.round(failureRate * 100)}
                    onChange={(e) => setFailureRate((parseFloat(e.target.value) || 0) / 100)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-slate-200 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="text-slate-400 block mb-1">Avg Amount</label>
                  <input
                    type="number"
                    value={avgAmount}
                    onChange={(e) => setAvgAmount(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-1.5 text-slate-200 font-mono text-xs"
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Confidence: {(confidence * 100).toFixed(0)}%</span>
                  <span className={confidence >= 0.70 ? "text-emerald-400" : "text-rose-400"}>
                    {confidence >= 0.70 ? "Above Gate" : "Below Gate"}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.4"
                  max="1.0"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="approvalCheck"
                  checked={humanApproved}
                  onChange={(e) => setHumanApproved(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-800"
                />
                <label htmlFor="approvalCheck" className="text-slate-300">
                  Dual-Control Human Approval Granted
                </label>
              </div>

              <button
                onClick={handleRunSimulation}
                disabled={loadingSim}
                className="w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50 mt-2"
              >
                {loadingSim ? "Evaluating Policy..." : "Run Policy Evaluation"}
              </button>
            </div>
          </div>

          <div className="lg:col-span-7 bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Evaluation &amp; Recovery Outcome
            </h2>

            {simResult ? (
              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">Policy Status:</span>
                  <span className={`font-bold ${
                    simResult.status === "SAFE_TO_EXECUTE"
                      ? "text-emerald-400"
                      : simResult.status === "AWAITING_HUMAN_APPROVAL"
                      ? "text-amber-400"
                      : "text-rose-400"
                  }`}>
                    {simResult.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Revenue at Risk</div>
                    <div className="text-sm font-bold text-rose-400 mt-0.5">{formatCurrency(simResult.revenue_at_risk)}</div>
                  </div>
                  <div className="p-3 rounded bg-slate-900 border border-slate-800">
                    <div className="text-[10px] text-slate-500 font-sans">Estimated Recovered</div>
                    <div className="text-sm font-bold text-emerald-400 mt-0.5">{formatCurrency(simResult.recovered_revenue)}</div>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-black/40 border border-slate-800 text-[11px] text-slate-300">
                  {simResult.reason || "Intervention evaluated against backend financial safety rules."}
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg text-xs">
                Configure parameters on the left and run policy evaluation.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Event Stream & Webhook Ingestion Probe */}
      {tab === "streaming" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-5 bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Send className="w-4 h-4 text-cyan-400" /> Ingestion Probes
              </h2>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="text-slate-400 block mb-1">Transaction Amount (₹)</label>
                  <input
                    type="number"
                    value={streamAmount}
                    onChange={(e) => setStreamAmount(parseFloat(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                  />
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">Status</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setStreamSuccess(false)}
                      className={`flex-1 py-1.5 rounded text-xs font-bold font-mono border ${
                        !streamSuccess ? "bg-rose-500/20 text-rose-300 border-rose-500/40" : "bg-slate-900 text-slate-400 border-slate-800"
                      }`}
                    >
                      Failed
                    </button>
                    <button
                      onClick={() => setStreamSuccess(true)}
                      className={`flex-1 py-1.5 rounded text-xs font-bold font-mono border ${
                        streamSuccess ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" : "bg-slate-900 text-slate-400 border-slate-800"
                      }`}
                    >
                      Captured
                    </button>
                  </div>
                </div>

                {!streamSuccess && (
                  <div>
                    <label className="text-slate-400 block mb-1">Decline Code</label>
                    <select
                      value={streamDeclineCode}
                      onChange={(e) => setStreamDeclineCode(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 text-slate-200 font-mono"
                    >
                      <option value="processor_declined">processor_declined</option>
                      <option value="gateway_timeout">gateway_timeout</option>
                      <option value="velocity_limit">velocity_limit</option>
                      <option value="insufficient_funds">insufficient_funds</option>
                    </select>
                  </div>
                )}

                <div className="flex items-center gap-2 pt-1 pb-1">
                  <input
                    type="checkbox"
                    id="autoRecoverCheck"
                    checked={autoRecover}
                    onChange={(e) => setAutoRecover(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-800"
                  />
                  <label htmlFor="autoRecoverCheck" className="text-slate-400 text-[11px]">
                    Allow automated mitigation if policy passes (simulated stream only)
                  </label>
                </div>

                <div className="flex gap-2 pt-2">
                  <button
                    onClick={handleInjectStreamEvent}
                    disabled={streamLoading}
                    className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                  >
                    {streamLoading ? "Streaming..." : "Inject Stream Event"}
                  </button>
                  <button
                    onClick={handleSendWebhook}
                    disabled={streamLoading}
                    className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 rounded-lg font-semibold text-xs transition disabled:opacity-50"
                  >
                    POST /api/webhooks
                  </button>
                </div>
              </div>
            </div>

            <div className="lg:col-span-7 bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  9-Stage Event Pipeline Trace
                </h2>
                {streamTrace && (
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2 py-0.5 rounded">
                    {streamTrace.timeline?.length || 9} STAGES PROCESSED
                  </span>
                )}
              </div>

              {streamError && (
                <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold">Pipeline Ingestion Error: </span>
                      <span className="font-mono text-[11px]">{streamError}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => setStreamError(null)}
                    className="text-rose-400 hover:text-rose-200 text-xs font-bold px-1"
                  >
                    ✕
                  </button>
                </div>
              )}

              {webhookResult && (
                <div className="p-3 rounded-lg bg-cyan-950/30 border border-cyan-500/30 text-xs font-mono space-y-1">
                  <div className="flex items-center justify-between text-cyan-300 font-bold">
                    <span>Webhook Response: {webhookResult.status}</span>
                    <span className="text-[10px] text-slate-400">HTTP 200 OK</span>
                  </div>
                  <div className="text-[11px] text-slate-300">
                    Idempotency Key: <span className="text-white">{webhookResult.idempotency_key}</span> · Payment ID: <span className="text-white">{webhookResult.payment_id}</span>
                  </div>
                  <div className="text-[10px] text-slate-400">
                    Action Bounded: Webhook ingestion routed to controlled pipeline with auto_recover=False
                  </div>
                </div>
              )}

              {streamTrace ? (
                <div className="space-y-2 font-mono text-xs">
                  {streamTrace.timeline?.map((step, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-cyan-400 font-bold text-[11px] min-w-[125px]">{step.stage}</span>
                        {step.status && (
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider ${
                            step.status === "COMPLETED" || step.status === "RESOLVED" || step.status === "APPLIED" || step.status === "SAFE_TO_EXECUTE"
                              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                              : step.status === "ANOMALY_CONFIRMED" || step.status === "BLOCKED" || step.status === "HALTED" || step.status === "FAILED"
                              ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                              : step.status === "RECOMMENDED" || step.status === "PENDING_MANUAL_TRIGGER"
                              ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                              : "bg-slate-800 text-slate-400 border border-slate-700"
                          }`}>
                            {step.status}
                          </span>
                        )}
                        <span className="text-slate-300 font-sans text-xs">{step.details}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 shrink-0 ml-2">{step.timestamp}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg text-xs">
                  Inject a stream event or trigger webhook to inspect live pipeline execution.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: Recovery Experiments (A/B Simulation) */}
      {tab === "experiments" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Award className="w-4 h-4 text-amber-400" /> Offline Strategy Cohort Experiments
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic SHA-256 seeding ensures identical inputs produce identical results across process restarts.
              </p>
            </div>
            <button
              onClick={handleRunExperiment}
              disabled={loadingExp}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-semibold text-xs transition disabled:opacity-50"
            >
              {loadingExp ? "Running Cohort Test..." : "Run Cohort Experiment"}
            </button>
          </div>

          {experimentData && (
            <div className="space-y-4">
              {/* Winner Banner */}
              <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-950/60 to-slate-900 border border-emerald-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div>
                  <div className="text-[10px] font-mono text-emerald-400 font-bold uppercase">
                    Statistical Winner Confirmed (p-value: {experimentData.p_value})
                  </div>
                  <div className="text-base font-bold text-white mt-0.5 font-mono">
                    {experimentData.winner}
                  </div>
                  <div className="text-xs text-slate-300 mt-1">{experimentData.recommendation_rationale}</div>
                </div>
                <div className="text-right font-mono">
                  <div className="text-[10px] text-slate-400">Confidence</div>
                  <div className="text-lg font-bold text-emerald-400">{experimentData.confidence_level_pct}%</div>
                </div>
              </div>

              {/* Cohort Comparison Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {["cohort_a", "cohort_b"].map((cKey) => {
                  const c = experimentData[cKey];
                  return (
                    <div key={cKey} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">{c.strategy}</span>
                        <span className="text-xs font-mono font-bold text-cyan-300">{formatPercent(c.recovery_rate_pct)} Rate</span>
                      </div>

                      <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                        <div className="p-2 rounded bg-black/40">
                          <div className="text-[10px] text-slate-500 font-sans">Avg Lift</div>
                          <div className="font-bold text-emerald-400">+{c.average_lift_pp} pp</div>
                        </div>
                        <div className="p-2 rounded bg-black/40">
                          <div className="text-[10px] text-slate-500 font-sans">Net Revenue</div>
                          <div className="font-bold text-indigo-300">{formatCurrency(c.net_recovered_revenue)}</div>
                        </div>
                        <div className="p-2 rounded bg-black/40">
                          <div className="text-[10px] text-slate-500 font-sans">Friction</div>
                          <div className="font-bold text-slate-200">{c.friction_score} / 100</div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Customer Safety */}
      {tab === "customers" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" /> Customer-Level Anonymized Retry Safety
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Zero PII exposure. Anonymized token hashes enforce max 2 retry caps to prevent cardholder friction.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {(customers.length > 0 ? customers : [
              { customer_id: "CUST_1042", issuer: "Bank X", payment_method: "card", retries_used: 2, safety_status: "LOCKED_MAX_RETRIES", friction_score: 85.0 },
              { customer_id: "CUST_2081", issuer: "HDFC", payment_method: "netbanking", retries_used: 1, safety_status: "RETRY_ALLOWED", friction_score: 35.0 },
              { customer_id: "CUST_3190", issuer: "SBI", payment_method: "upi", retries_used: 2, safety_status: "LOCKED_COOLDOWN_ACTIVE", friction_score: 92.0 },
            ]).map((cust) => (
              <div key={cust.customer_id} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-xs font-mono">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{cust.customer_id}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    cust.safety_status.includes("LOCKED") ? "bg-rose-500/10 text-rose-300" : "bg-emerald-500/10 text-emerald-300"
                  }`}>
                    {cust.safety_status}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 font-sans">{cust.issuer} · {cust.payment_method}</div>
                <div className="flex justify-between pt-2 border-t border-slate-800 text-[11px]">
                  <span>Retries: {cust.retries_used} / 2 limit</span>
                  <span>Friction: {cust.friction_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: Provider Routing Optimizer (Part B) */}
      {tab === "providers" && (
        <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Server className="w-4 h-4 text-emerald-400" /> Multi-Gateway Routing Optimizer Simulation
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Simulates real-time multi-gateway scoring factoring latency, success probability, cost, and BIN specialization.
              </p>
            </div>
            <button
              onClick={handleScoreProviderRouting}
              disabled={loadingOpt}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition disabled:opacity-50"
            >
              {loadingOpt ? "Scoring Routes..." : "Optimize Routing Decision"}
            </button>
          </div>

          {/* Provider Health Simulation Control (Part B Degradation Scenario) */}
          <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2.5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  Provider Health Simulation (Failure Injection Mode)
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                SANDBOX SIMULATION ONLY · ZERO PRODUCTION IMPACT
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-3 text-xs">
              <div className="flex-1">
                <label className="text-slate-400 block mb-1 font-sans text-[11px]">
                  Simulated Gateway Fault / Outage Status
                </label>
                <select
                  value={simulatedDegradedProvider}
                  onChange={(e) => handleDegradedProviderChange(e.target.value)}
                  className="w-full bg-black/40 border border-slate-700 rounded p-2 text-slate-200 font-mono text-xs focus:border-amber-500 focus:outline-none"
                >
                  <option value="none">Normal Health (All Gateways Optimal / Nominal Operational State)</option>
                  <option value="Provider A">Simulate Provider A Degradation (Direct Bank Switch Latency Spike / Outage)</option>
                  <option value="Provider B">Simulate Provider B Degradation (Card Network Direct Failure)</option>
                  <option value="Razorpay Smart Router">Simulate Razorpay Smart Router Degradation (Aggregator Terminal Latency)</option>
                </select>
              </div>

              {simulatedDegradedProvider !== "none" && (
                <button
                  onClick={() => handleDegradedProviderChange("none")}
                  className="sm:self-end px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 transition flex items-center gap-1.5"
                  title="Reset to Optimal Health"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
                  <span>Restore Normal Health</span>
                </button>
              )}
            </div>

            {simulatedDegradedProvider !== "none" ? (
              <div className="text-[11px] font-mono text-amber-300/90 bg-amber-500/10 p-2.5 rounded border border-amber-500/20 flex items-start gap-2">
                <span className="text-amber-400 font-bold">&bull;</span>
                <span>
                  <strong>Active Simulation:</strong> {simulatedDegradedProvider} is assigned a <strong>-25.0 composite score penalty</strong> and marked <strong>DEGRADED</strong>.
                  Optimizer dynamically reroutes traffic to next optimal partner ({providerOptResult?.recommended_provider || "alternate route"}).
                </span>
              </div>
            ) : (
              <div className="text-[10px] font-mono text-slate-500">
                Live simulated gateways operating with nominal parameters. Select a provider above to test dynamic failover routing.
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <label className="text-slate-400 block mb-1 font-sans">Issuer</label>
              <select
                value={optIssuer}
                onChange={(e) => handleIssuerChange(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-200 font-mono"
              >
                <option value="Bank X">Bank X</option>
                <option value="ICICI">ICICI</option>
                <option value="SBI">SBI</option>
                <option value="HDFC">HDFC</option>
              </select>
            </div>

            <div>
              <label className="text-slate-400 block mb-1 font-sans">Card BIN</label>
              <select
                value={optBin}
                onChange={(e) => handleBinChange(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-200 font-mono"
              >
                {availableBins.map((b) => (
                  <option key={b.bin} value={b.bin}>
                    {b.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-slate-400 block mb-1 font-sans">Payment Method</label>
              <select
                value={optMethod}
                onChange={(e) => setOptMethod(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-200 font-mono"
              >
                <option value="card">card</option>
                <option value="upi">upi</option>
                <option value="netbanking">netbanking</option>
              </select>
            </div>

            <div>
              <label className="text-slate-400 block mb-1 font-sans">Decline Trigger</label>
              <select
                value={optDecline}
                onChange={(e) => setOptDecline(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-200 font-mono"
              >
                <option value="processor_declined">processor_declined</option>
                <option value="gateway_timeout">gateway_timeout</option>
                <option value="velocity_limit">velocity_limit</option>
              </select>
            </div>
          </div>

          {providerOptResult && (
            <div className="space-y-3 pt-2">
              <div className="p-3.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="font-bold text-emerald-400">Target Decision: </span>
                  <span className="font-mono text-slate-200 font-bold">{providerOptResult.target_gateway_routing}</span>
                </div>
                <div className="text-[11px] text-slate-400 font-mono">
                  Expected Success: <strong className="text-emerald-300">{providerOptResult.expected_success_rate}%</strong> · Latency: <strong className="text-slate-200">{providerOptResult.expected_latency_ms}ms</strong>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 text-[11px]">
                      <th className="p-2.5">PROVIDER</th>
                      <th className="p-2.5">SCORE</th>
                      <th className="p-2.5">EXPECTED SUCCESS</th>
                      <th className="p-2.5">LATENCY</th>
                      <th className="p-2.5">FEE</th>
                      <th className="p-2.5">HEALTH</th>
                      <th className="p-2.5 text-right">RECOMMENDATION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {providerOptResult.ranked_providers?.map((p, idx) => (
                      <tr key={p.provider} className={idx === 0 ? "bg-emerald-500/5 font-semibold" : ""}>
                        <td className="p-2.5 text-slate-200 font-sans font-bold">
                          <div className="flex items-center gap-1.5">
                            <span>{p.provider}</span>
                            {p.is_currently_degraded && (
                              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                DEGRADED
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-2.5 text-cyan-300 font-bold">{p.composite_score}</td>
                        <td className="p-2.5 text-emerald-400">{p.expected_success_rate}%</td>
                        <td className="p-2.5 text-slate-200">{p.latency_ms}ms</td>
                        <td className="p-2.5 text-slate-400">{p.cost_pct}%</td>
                        <td className="p-2.5">
                          <span
                            className={
                              p.health === "OPTIMAL"
                                ? "text-emerald-400 font-bold"
                                : p.health === "HEALTHY"
                                ? "text-blue-400"
                                : p.health === "DEGRADED"
                                ? "text-rose-400 font-bold animate-pulse"
                                : "text-amber-400"
                            }
                          >
                            {p.health}
                          </span>
                        </td>
                        <td className="p-2.5 text-right">
                          {idx === 0 ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                              OPTIMAL CHOICE
                            </span>
                          ) : p.is_currently_degraded ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950/40 text-rose-400 border border-rose-800/50">
                              PENALIZED
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[10px]">STANDBY</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
