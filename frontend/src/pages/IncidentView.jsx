import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { ShieldAlert, Cpu, Play, CheckCircle, ShieldCheck, AlertCircle, AlertTriangle } from "lucide-react";
import api from "../api";

export default function IncidentView() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const getRecommendedAction = (hypothesis) => {
    if (hypothesis === "ROUTING_CONNECTIVITY_ISSUE") return "REROUTE";
    if (hypothesis === "BIN_LEVEL_TEMPORARY_ISSUE") return "ADJUST_RETRY_TIMING";
    return "SUPPRESS_RETRIES";
  };

  // 1. Wrap the fetch function in useCallback so it's a stable dependency
  const fetchIncidentData = useCallback(async () => {
    const res = await api.get(`/incidents/${id}`);
    return res.data;
  }, [id]);

  // 2. Safely call it inside useEffect and add it to the dependency array
  useEffect(() => {
    let isMounted = true;

    fetchIncidentData()
      .then((fetchedData) => {
        if (isMounted) setData(fetchedData);
      })
      .catch((err) => {
        console.error("Error fetching incident:", err);
        if (isMounted) setErrorMessage("Failed to load incident data.");
      });

    return () => {
      isMounted = false;
    };
  }, [fetchIncidentData]);

  const handleDiagnose = async () => {
    setDiagnosing(true);
    setErrorMessage(null);
    try {
      await api.post(`/incidents/${id}/diagnose`);
      const newData = await fetchIncidentData();
      setData(newData);
    } catch (err) {
      console.error(err);
      setErrorMessage(err.response?.data?.detail || err.message || "Diagnosis failed");
    } finally {
      setDiagnosing(false);
    }
  };

  const handleRecover = async () => {
    setRecovering(true);
    setErrorMessage(null);
    try {
      const actionType = getRecommendedAction(data.diagnosis?.hypothesis);
      const actionData = {
        recommended_action: actionType,
        selected_by: "llm",
        human_approved: data.incident?.state === "AWAITING_HUMAN_APPROVAL",
      };
      const res = await api.post(`/incidents/${id}/recover`, actionData);
      setRecoveryResult(res.data);

      const newData = await fetchIncidentData();
      setData(newData);
    } catch (err) {
      console.error(err);
      setErrorMessage(err.response?.data?.detail || err.message || "Recovery execution failed");
    } finally {
      setRecovering(false);
    }
  };

  if (!data)
    return (
      <div className="text-center py-10 text-slate-400">
        Loading evidence...
      </div>
    );

  const { incident, diagnosis, recovery_action, outcome } = data;
  const activeOutcome = recoveryResult?.outcome || outcome;
  const activeAction = recoveryResult?.action || recovery_action;
  const recommendedAction = diagnosis ? getRecommendedAction(diagnosis.hypothesis) : "REROUTE";
  const displayAction = activeAction?.action_type || recommendedAction;

  const getStatusBadge = (state) => {
    if (state === "RESOLVED") {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">RESOLVED</span>;
    }
    if (state === "AWAITING_HUMAN_APPROVAL") {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">AWAITING HUMAN APPROVAL</span>;
    }
    if (state?.startsWith("ESCALATED")) {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">{state.replace(/_/g, " ")}</span>;
    }
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">{state}</span>;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between bg-[#1e2330] p-6 rounded-xl border border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ShieldAlert className="text-rose-500" /> Segment:{" "}
            {incident.segment_issuer} {incident.segment_payment_method}
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-slate-400 text-sm">Status:</span>
            {getStatusBadge(incident.state)}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to={`/incident/${id}/audit`}
            className="px-4 py-2 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-lg text-sm font-medium transition"
          >
            View Audit Trail
          </Link>
          {!diagnosis ? (
            <button
              onClick={handleDiagnose}
              disabled={diagnosing || incident.state.startsWith("ESCALATED") || incident.state === "RESOLVED"}
              className="bg-purple-600 hover:bg-purple-500 px-5 py-2.5 rounded-lg text-white font-medium flex items-center gap-2 disabled:opacity-50 transition"
            >
              <Cpu className="w-4 h-4" />{" "}
              {diagnosing ? "Diagnosing..." : "Run AI Diagnosis"}
            </button>
          ) : (
            <div className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg flex items-center gap-2 font-medium">
              <CheckCircle className="w-5 h-5" /> Diagnosed
            </div>
          )}
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="bg-rose-500/10 border border-rose-500/30 p-4 rounded-xl flex items-center gap-3 text-rose-400 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Evidence Panel */}
        <div className="bg-[#1e2330] rounded-xl border border-slate-800 p-6">
          <h2 className="text-lg font-medium text-white mb-4 border-b border-slate-800 pb-2">
            Statistical Evidence
          </h2>
          <div className="space-y-4">
            <div className="flex justify-between">
              <span className="text-slate-400">Success Rate Drop</span>
              <span className="text-rose-400 font-medium">
                {incident.drop_pp.toFixed(1)}% (from{" "}
                {incident.baseline_success_rate.toFixed(1)}%)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Concentration Ratio</span>
              <span className="text-white font-medium">
                {(incident.concentration_ratio * 100).toFixed(1)}% of failures
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Sample Size</span>
              <span className="text-white font-medium">
                {incident.sample_size} txns
              </span>
            </div>
            {diagnosis && (
              <div className="flex justify-between mt-4 pt-4 border-t border-slate-800">
                <span className="text-slate-400">Dominant Error</span>
                <span className="text-orange-400 font-medium">
                  {diagnosis.dominant_decline_code} (
                  {(diagnosis.dominant_decline_code_share * 100).toFixed(1)}%)
                </span>
              </div>
            )}
            <div className="flex justify-between mt-4 pt-4 border-t border-slate-800">
              <span className="text-slate-400">Estimated At-Risk Revenue</span>
              <span className="text-rose-400 font-semibold">
                ₹{Math.round(incident.at_risk_revenue ?? incident.estimated_loss ?? 0).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Diagnosis & Action Panel */}
        {diagnosis && (
          <div className="bg-gradient-to-br from-[#1e2330] to-[#151822] rounded-xl border border-slate-700 p-6 shadow-lg shadow-purple-900/10">
            <h2 className="text-lg font-medium text-purple-400 mb-4 flex items-center gap-2">
              <Cpu className="w-5 h-5" /> AI Root Cause Analysis
            </h2>
            <div className="mb-4">
              <div className="text-sm text-slate-400 mb-1">
                Confidence Score
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full ${diagnosis.confidence >= 0.7 ? "bg-emerald-500" : "bg-rose-500"}`}
                  style={{ width: `${diagnosis.confidence * 100}%` }}
                ></div>
              </div>
              <div className="text-right text-xs text-slate-300 mt-1">
                {(diagnosis.confidence * 100).toFixed(0)}% (Deterministic)
              </div>
            </div>

            <div className="bg-[#0f111a] p-4 rounded-lg border border-slate-800 mb-6 text-sm text-slate-300 leading-relaxed italic">
              "
              {diagnosis.narrative_text ||
                "Waiting for narrative generation..."}
              "
            </div>

            {/* Escalated Status Notice */}
            {incident.state.startsWith("ESCALATED") && (
              <div className="mt-4 p-4 rounded-lg bg-rose-500/10 border border-rose-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-5 h-5 text-rose-400" />
                  <div className="font-semibold text-rose-400">
                    {incident.state === "ESCALATED_LOW_CONFIDENCE"
                      ? "Escalated: Low Confidence"
                      : incident.state === "ESCALATED_LOW_REVENUE"
                      ? "Escalated: Low Revenue"
                      : "Escalated: Insufficient Recovery"}
                  </div>
                </div>
                <p className="text-sm text-slate-400 leading-relaxed">
                  {incident.state === "ESCALATED_LOW_CONFIDENCE"
                    ? `Confidence score (${(diagnosis.confidence * 100).toFixed(0)}%) is below the 70% threshold required for automated recovery action. Automated recovery is suppressed and escalated to human operations.`
                    : incident.state === "ESCALATED_LOW_REVENUE"
                    ? "At-risk revenue is below the ₹50,000 threshold. Escalated to prevent unnecessary intervention."
                    : "Recovery simulation produced insufficient improvement (< 5 pp). Escalated to prevent harmful retries."}
                </p>
              </div>
            )}

            {/* Human Approval Required Notice & Action */}
            {incident.state === "AWAITING_HUMAN_APPROVAL" && (
              <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="w-5 h-5 text-amber-400" />
                  <div className="font-semibold text-amber-400">
                    Human Approval Required
                  </div>
                </div>

                <p className="text-sm text-slate-400 leading-relaxed">
                  At-risk revenue exceeds ₹500,000 (₹{Math.round(incident.at_risk_revenue ?? incident.estimated_loss ?? 0).toLocaleString()}). In accordance with safety guardrails, an authorized operator must approve the recovery action before execution.
                </p>

                <div className="my-3 p-3 bg-slate-900/80 rounded border border-amber-500/20 text-xs text-slate-300">
                  <span className="text-slate-400">Proposed Action:</span> <span className="font-semibold text-amber-300">{recommendedAction}</span>
                </div>

                <button
                  onClick={handleRecover}
                  disabled={recovering}
                  className="w-full mt-2 bg-amber-600 hover:bg-amber-500 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50"
                >
                  <ShieldCheck className="w-5 h-5" />
                  {recovering
                    ? "Executing Approved Recovery..."
                    : "Approve & Execute Recovery"}
                </button>
              </div>
            )}

            {/* Diagnosed & Ready for Simulation */}
            {incident.state === "DIAGNOSED" && diagnosis.confidence >= 0.7 && (
              <>
                <div className="mb-4 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">
                    Recommended Recovery Action
                  </div>

                  <div className="text-lg font-semibold text-blue-400">
                    {recommendedAction}
                  </div>

                  <div className="text-xs text-slate-400 mt-1">
                    Confidence threshold passed ({(diagnosis.confidence * 100).toFixed(0)}% &ge; 70%) — recovery simulation is permitted.
                  </div>
                </div>

                <button
                  onClick={handleRecover}
                  disabled={recovering}
                  className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50"
                >
                  <Play className="w-5 h-5" />
                  {recovering
                    ? "Simulating Recovery..."
                    : "Execute Recovery Simulation"}
                </button>
              </>
            )}

            {/* Recovery Outcome (survives page refresh via activeOutcome) */}
            {activeOutcome && (
              <div className="mt-4 p-5 rounded-lg border bg-emerald-500/10 border-emerald-500/30">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-semibold text-emerald-400">
                    Recovery Outcome: {activeOutcome.result}
                  </h3>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-slate-400">Action</div>
                    <div className="text-white font-semibold">{displayAction}</div>
                  </div>

                  <div>
                    <div className="text-slate-400">Success Rate</div>
                    <div className="text-white font-semibold">
                      {activeOutcome.pre_success_rate?.toFixed(1)}%
                      {" → "}
                      {activeOutcome.post_success_rate?.toFixed(1)}%
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400">Improvement</div>
                    <div className="text-emerald-400 font-semibold">
                      +
                      {(
                        activeOutcome.post_success_rate -
                        activeOutcome.pre_success_rate
                      ).toFixed(2)}{" "}
                      pp
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400">Recovered Revenue</div>
                    <div className="text-emerald-400 font-semibold">
                      ₹
                      {activeOutcome.recovered_revenue?.toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
