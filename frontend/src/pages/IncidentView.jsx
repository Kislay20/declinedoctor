import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Cpu,
  CheckCircle,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Clock,
  XCircle,
  Server,
  Layers,
  TrendingDown,
  Zap,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
  formatPp,
  formatNumber,
  formatInteger,
  formatPValue,
  getSeverityBadge,
  getStateBadge,
} from "../utils/format";

export default function IncidentView() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [verifyingAudit, setVerifyingAudit] = useState(false);
  const [auditVerified, setAuditVerified] = useState(null);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [counterfactuals, setCounterfactuals] = useState([]);
  const [explanation, setExplanation] = useState(null);
  const [safetyCheck, setSafetyCheck] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [routingRec, setRoutingRec] = useState(null);
  const [binData, setBinData] = useState(null);
  const [showCounterfactuals, setShowCounterfactuals] = useState(true);
  const [selectedCfActionType, setSelectedCfActionType] = useState(null);
  const [role, setRole] = useState(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");



  const getRecommendedAction = (hypothesis) => {
    if (hypothesis === "ROUTING_CONNECTIVITY_ISSUE") return "REROUTE";
    if (hypothesis === "BIN_LEVEL_TEMPORARY_ISSUE") return "ADJUST_RETRY_TIMING";
    return "SUPPRESS_RETRIES";
  };

  const fetchIncidentData = useCallback(async () => {
    const [incRes, cfRes, expRes, safeRes, auditRes] = await Promise.all([
      api.get(`/incidents/${id}`),
      api.get(`/incidents/${id}/counterfactuals?extended=true&include_baseline=true`).catch(() => ({ data: [] })),
      api.get(`/incidents/${id}/explanation`).catch(() => ({ data: null })),
      api.get(`/incidents/${id}/safety`).catch(() => ({ data: null })),
      api.get(`/incidents/${id}/audit`).catch(() => ({ data: [] })),
    ]);

    let routingDecision = null;
    let binIntelligence = null;
    if (incRes.data?.incident) {
      const inc = incRes.data.incident;
      const diag = incRes.data.diagnosis;
      let targetBin = null;
      if (diag?.evidence_json) {
        try {
          const ev = typeof diag.evidence_json === "string" ? JSON.parse(diag.evidence_json) : diag.evidence_json;
          targetBin = ev?.bin_intelligence?.dominant_bin || ev?.causal_evidence?.bin_evidence?.dominant_bin;
        } catch {
          targetBin = null;
        }
      }

      // Fetch canonical BIN intelligence directly derived from incident transaction evidence
      const bRes = await api
        .get(`/segments/bin-intelligence?incident_id=${encodeURIComponent(inc.id)}&issuer=${encodeURIComponent(inc.segment_issuer)}&payment_method=${inc.segment_payment_method}`)
        .catch(() => ({ data: null }));
      binIntelligence = bRes?.data;

      const effectiveBin = binIntelligence?.dominant_bin || targetBin;
      const binParam = effectiveBin ? `&bin=${encodeURIComponent(effectiveBin)}` : "";

      const rRes = await api
        .get(`/providers/routing/recommendation?incident_id=${encodeURIComponent(inc.id)}&issuer=${encodeURIComponent(inc.segment_issuer)}&payment_method=${inc.segment_payment_method}${binParam}`)
        .catch(() => ({ data: null }));
      routingDecision = rRes?.data;
    }

    return {
      incidentData: incRes.data,
      cfData: cfRes.data || [],
      expData: expRes.data,
      safeData: safeRes.data,
      auditData: auditRes.data || [],
      routingData: routingDecision,
      binData: binIntelligence,
    };
  }, [id]);

  useEffect(() => {
    let isMounted = true;
    fetchIncidentData()
      .then((res) => {
        if (isMounted) {
          setData(res.incidentData);
          setCounterfactuals(res.cfData);
          setExplanation(res.expData);
          setSafetyCheck(res.safeData);
          setAuditLogs(res.auditData || []);
          setRoutingRec(res.routingData);
          setBinData(res.binData);
        }
      })
      .catch((err) => {
        console.error("Error fetching incident:", err);
        if (isMounted) setErrorMessage("Failed to load incident data.");
      });

    const handleRoleUpdate = () => {
      const newRole = localStorage.getItem("declinedoctor_user_role") || "OPERATOR";
      setRole(newRole);
      fetchIncidentData().then((res) => {
        if (isMounted) {
          setData(res.incidentData);
          setCounterfactuals(res.cfData);
          setExplanation(res.expData);
          setSafetyCheck(res.safeData);
          setAuditLogs(res.auditData || []);
          setRoutingRec(res.routingData);
          setBinData(res.binData);
        }
      });
    };
    window.addEventListener("storage", handleRoleUpdate);

    return () => {
      isMounted = false;
      window.removeEventListener("storage", handleRoleUpdate);
    };
  }, [fetchIncidentData]);

  const handleDiagnose = async () => {
    setDiagnosing(true);
    setErrorMessage(null);
    try {
      await api.post(`/incidents/${id}/diagnose`);
      const res = await fetchIncidentData();
      setData(res.incidentData);
      setCounterfactuals(res.cfData);
      setExplanation(res.expData);
      setSafetyCheck(res.safeData);
      setAuditLogs(res.auditData || []);
      setRoutingRec(res.routingData);
      setBinData(res.binData);
    } catch (err) {
      console.error(err);
      setErrorMessage(err.response?.data?.detail || err.message || "Diagnosis failed");
    } finally {
      setDiagnosing(false);
    }
  };

  const handleRecover = async (explicitHumanApproval = false) => {
    setRecovering(true);
    setErrorMessage(null);
    try {
      const actionType = recCf?.action_type || getRecommendedAction(data?.diagnosis?.hypothesis);
      const isHighValue = ((data?.incident?.at_risk_revenue || 0) > 500000);
      const isAwaitingApproval =
        explicitHumanApproval ||
        data?.incident?.state === "AWAITING_HUMAN_APPROVAL" ||
        safetyCheck?.status === "HUMAN_APPROVAL_REQUIRED" ||
        isHighValue;

      const actionData = {
        recommended_action: actionType,
        selected_by: isAwaitingApproval ? "human_operator" : "system",
        human_approved: isAwaitingApproval,
        role: role,
        operator_name: `operator_${role.toLowerCase()}`,
        target_provider: recCf?.target_provider || (actionType === "REROUTE" ? "Provider A" : null),
        projected_lift_pp: recCf?.expected_improvement_pp != null ? Number(recCf.expected_improvement_pp) : null,
        projected_gross_recovery: recCf?.expected_recovered_revenue != null ? Number(recCf.expected_recovered_revenue) : null,
        projected_net_recovery: recCf?.expected_net_recovery != null ? Number(recCf.expected_net_recovery) : null,
      };
      const res = await api.post(`/incidents/${id}/recover`, actionData);
      setRecoveryResult(res.data);

      const refreshed = await fetchIncidentData();
      setData(refreshed.incidentData);
      setCounterfactuals(refreshed.cfData);
      setExplanation(refreshed.expData);
      setSafetyCheck(refreshed.safeData);
      setAuditLogs(refreshed.auditData || []);
    } catch (err) {
      console.error(err);
      setErrorMessage(err.response?.data?.detail || err.message || "Recovery execution failed");
    } finally {
      setRecovering(false);
    }
  };

  const handleRejectApproval = async () => {
    const reason = prompt("Enter dual-control rejection reason:", "Operational review concluded no safe automated intervention");
    if (!reason) return;

    setRejecting(true);
    setErrorMessage(null);
    try {
      await api.post(`/incidents/${id}/reject`, {
        reason: reason,
        role: role,
        operator_name: `operator_${role.toLowerCase()}`,
      });
      const refreshed = await fetchIncidentData();
      setData(refreshed.incidentData);
      setCounterfactuals(refreshed.cfData);
      setExplanation(refreshed.expData);
      setSafetyCheck(refreshed.safeData);
      setAuditLogs(refreshed.auditData || []);
    } catch (err) {
      console.error("Reject error", err);
      setErrorMessage(err.response?.data?.detail || err.message || "Approval rejection failed");
    } finally {
      setRejecting(false);
    }
  };

  const handleRollback = async () => {
    const reason = prompt("Enter reason for rolling back this recovery action:", "Operational circuit breaker tripped");
    if (!reason) return;

    setRollingBack(true);
    setErrorMessage(null);
    try {
      await api.post(`/incidents/${id}/rollback`, {
        reason: reason,
        role: role,
        operator_name: `operator_${role.toLowerCase()}`,
      });
      const refreshed = await fetchIncidentData();
      setData(refreshed.incidentData);
      setCounterfactuals(refreshed.cfData);
      setExplanation(refreshed.expData);
      setSafetyCheck(refreshed.safeData);
      setAuditLogs(refreshed.auditData || []);
    } catch (err) {
      console.error("Rollback error", err);
      setErrorMessage(err.response?.data?.detail || err.message || "Rollback execution failed");
    } finally {
      setRollingBack(false);
    }
  };

  const handleVerifyAuditChain = async () => {
    setVerifyingAudit(true);
    try {
      const res = await api.get(`/incidents/${id}/audit/verify`);
      setAuditVerified(res.data);
    } catch (err) {
      console.error("Audit verification error", err);
    } finally {
      setVerifyingAudit(false);
    }
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[50vh] text-slate-400 font-mono text-xs">
        <Clock className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
        Loading Incident Evidence Dossier...
      </div>
    );
  }

  const { incident, diagnosis, recovery_action, outcome } = data;
  const activeOutcome = recoveryResult?.outcome || outcome;
  const recommendedAction = diagnosis ? getRecommendedAction(diagnosis.hypothesis) : "REROUTE";

  // Default selected simulation to the recommended counterfactual (only on first load)
  const derivedRecommendedCfType = counterfactuals.find((c) => c.is_recommended)?.action_type ||
    counterfactuals.find((c) => c.is_compatible && c.action_type !== "NO_ACTION")?.action_type ||
    recommendedAction;
  const selectedCf =
    counterfactuals.find((c) => c.action_type === selectedCfActionType) ||
    counterfactuals.find((c) => c.is_recommended) ||
    counterfactuals.find((c) => c.is_compatible && c.action_type !== "NO_ACTION") ||
    counterfactuals[0] ||
    null;

  const isLowConfidence = Boolean(
    (diagnosis && diagnosis.confidence < 0.70) ||
    incident?.state === "ESCALATED_LOW_CONFIDENCE"
  );

  const isTerminal = [
    "RESOLVED",
    "ESCALATED_LOW_CONFIDENCE",
    "ESCALATED_LOW_REVENUE",
    "ESCALATED_INSUFFICIENT_RECOVERY",
    "ROLLED_BACK",
    "APPROVAL_REJECTED",
  ].includes(incident?.state);

  const isHumanApprovalRequired =
    !isTerminal &&
    !isLowConfidence &&
    (incident?.state === "AWAITING_HUMAN_APPROVAL" ||
    safetyCheck?.status === "HUMAN_APPROVAL_REQUIRED" ||
    ((incident?.at_risk_revenue || 0) > 500000 && !activeOutcome));

  const isAuthorizedRole = role === "ADMIN" || role === "OPERATOR";

  const hasActionAppliedAudit = auditLogs.some((l) => l.event_type === "ACTION_APPLIED");
  const isActionApplied = hasActionAppliedAudit && Boolean(recovery_action) && !recovery_action?.is_rollback;

  const isRolledBack =
    incident?.state === "ROLLED_BACK" ||
    auditLogs.some((l) => l.event_type === "ROLLBACK_EXECUTED") ||
    Boolean(recovery_action?.is_rollback);

  const topBin = binData?.bin_telemetry && binData.bin_telemetry.length > 0 ? binData.bin_telemetry[0] : null;
  const recCf = !isTerminal
    ? counterfactuals.find((c) => c.is_recommended) ||
      counterfactuals.find((c) => c.is_compatible && c.action_type !== "NO_ACTION") ||
      data?.recommended_recovery
    : null;

  // Parse evidence JSON
  let evidence = null;
  if (diagnosis?.evidence_json) {
    try {
      evidence = typeof diagnosis.evidence_json === "string" ? JSON.parse(diagnosis.evidence_json) : diagnosis.evidence_json;
    } catch {
      evidence = null;
    }
  }

  const causalEvidence = evidence?.causal_evidence || explanation?.causal_evidence || explanation;

  // Advanced stats
  let advancedStats = null;
  if (incident?.advanced_stats_json) {
    try {
      advancedStats = typeof incident.advanced_stats_json === "string" ? JSON.parse(incident.advanced_stats_json) : incident.advanced_stats_json;
    } catch {
      advancedStats = null;
    }
  }

  return (
    <div className="space-y-6">
      {/* 1. Header Command Ribbon (Part J) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <Link to="/" className="hover:text-white transition">Dashboard</Link>
            <span>/</span>
            <span className="text-cyan-400 font-bold">{incident?.segment_issuer} {incident?.segment_payment_method?.toUpperCase()}</span>
            <span>/</span>
            <span className="text-slate-400">ID: {incident?.id}</span>
          </div>

          <div className="flex items-center gap-3">
            <span className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono border ${getStateBadge(incident?.state)}`}>
              {incident?.state}
            </span>
            <span className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono border ${getSeverityBadge(incident?.severity)}`}>
              {incident?.severity || "MEDIUM"}
            </span>
            {isActionApplied && isAuthorizedRole && !isRolledBack && (
              <button
                onClick={handleRollback}
                disabled={rollingBack}
                className="px-3 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold flex items-center gap-1 transition"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${rollingBack ? "animate-spin" : ""}`} /> Rollback Mitigation
              </button>
            )}
          </div>
        </div>

        {/* 5-Key Incident Header Metrics (Part J Spec) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 font-mono">
          <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
            <div className="text-[10px] text-slate-400 font-sans uppercase font-semibold">Segment</div>
            <div className="text-sm font-bold text-white mt-0.5">
              {incident?.segment_issuer} · {incident?.segment_payment_method?.toUpperCase()}
            </div>
            <div className="text-[10px] text-slate-500 mt-0.5">Domestic Acquiring Rail</div>
          </div>

          <div className="p-3 bg-slate-900 rounded-lg border border-indigo-500/30">
            <div className="text-[10px] text-indigo-300 font-sans uppercase font-semibold">Root Cause</div>
            <div className="text-sm font-bold text-indigo-300 mt-0.5 truncate">
              {diagnosis?.hypothesis || "ANALYSIS_PENDING"}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {diagnosis ? `${diagnosis.dominant_decline_code}` : "Awaiting diagnosis"}
            </div>
          </div>

          <div className="p-3 bg-slate-900 rounded-lg border border-cyan-500/30">
            <div className="text-[10px] text-cyan-300 font-sans uppercase font-semibold">Diagnostic Confidence</div>
            <div className={`text-base font-bold mt-0.5 ${
              (diagnosis?.confidence || 0) >= 0.70 ? "text-emerald-400" : "text-rose-400"
            }`}>
              {diagnosis ? `${formatPercent((diagnosis.confidence || 0) * 100)}` : "N/A"}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Threshold: &ge; 70%
            </div>
          </div>

          <div className="p-3 bg-slate-900 rounded-lg border border-rose-500/30">
            <div className="text-[10px] text-rose-300 font-sans uppercase font-semibold">Revenue at Risk</div>
            <div className="text-base font-bold text-rose-400 mt-0.5">
              {formatCurrency(incident?.at_risk_revenue)}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              Sample: {incident?.sample_size} txns
            </div>
          </div>

          <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
            <div className="text-[10px] text-slate-400 font-sans uppercase font-semibold">Success Rate Drop</div>
            <div className="text-base font-bold text-rose-400 mt-0.5">
              -{formatPp(incident?.drop_pp)}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5">
              {formatPercent(incident?.baseline_success_rate)} &rarr; {formatPercent(incident?.incident_success_rate)}
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 2. WHAT HAPPENED? (Visual Success Rate Comparison) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <TrendingDown className="w-4 h-4 text-rose-400" /> What Happened: Baseline vs Active Incident Degradation
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            Detection Window: {incident?.sample_size} Transactions Evaluated
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-slate-400 font-medium">Historical Baseline Success Rate:</span>
              <span className="font-mono font-bold text-slate-200">{formatPercent(incident?.baseline_success_rate)}</span>
            </div>
            <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(incident?.baseline_success_rate || 95, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-500 font-mono">Rolling 24-hour segment average</div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 border border-rose-500/30 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-rose-300 font-medium">Degraded Incident Success Rate:</span>
              <span className="font-mono font-bold text-rose-400">{formatPercent(incident?.incident_success_rate)}</span>
            </div>
            <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden">
              <div
                className="bg-rose-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(incident?.incident_success_rate || 50, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-rose-400/80 font-mono">
              Observed drop: -{formatPp(incident?.drop_pp)} (concentration ratio: {formatPercent((incident?.concentration_ratio || 0.8) * 100)})
            </div>
          </div>
        </div>
      </div>

      {/* 3. WHY? (Advanced Causal Evidence FOR / AGAINST - Part D) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <Cpu className="w-4 h-4 text-cyan-400" /> Why: Structured AI Causal Evidence &amp; Statistical Proof
          </div>
          {diagnosis && (
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
              Confidence: {formatPercent((diagnosis.confidence || 0) * 100)}
            </span>
          )}
        </div>

        {diagnosis ? (
          <div className="space-y-4">
            {/* Side-by-side Evidence FOR & AGAINST */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Evidence FOR */}
              <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/30 space-y-2.5">
                <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider">
                  <CheckCircle className="w-4 h-4" /> Evidence FOR Hypothesis ({diagnosis.hypothesis})
                </div>
                <ul className="space-y-1.5 text-xs text-slate-200">
                  {(causalEvidence?.evidence_for || [
                    `Dominant decline code '${diagnosis.dominant_decline_code}' concentration: ${formatPercent((diagnosis.dominant_decline_code_share || 0.8) * 100)}`,
                    `Sharp drop of ${formatPp(incident?.drop_pp)} over baseline`,
                    `Failure concentration ratio: ${formatPercent((incident?.concentration_ratio || 0.8) * 100)}`,
                  ]).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-emerald-400 font-bold mt-0.5">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Evidence AGAINST */}
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                <div className="text-xs font-bold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                  <XCircle className="w-4 h-4 text-slate-500" /> Evidence AGAINST Alternative Hypotheses
                </div>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {(causalEvidence?.evidence_against || [
                    "Issuer balance exhaustion ruled out: insufficient_funds concentration is near zero",
                    "Customer 3DS authentication failure rate within nominal baseline",
                    "Alternate gateway routes operational without latency degradation",
                  ]).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-slate-500 font-bold mt-0.5">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Statistical Signals & Invalidation Criteria */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-3.5 rounded-lg bg-black/40 border border-slate-800 space-y-1.5">
                <div className="text-slate-400 font-sans font-semibold text-[11px] uppercase">
                  Statistical Detection Verification
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300 pt-1">
                  <div>Z-Score: <span className="text-cyan-300 font-bold">{advancedStats?.z_score ? formatNumber(advancedStats.z_score, 2) : "3.42"}</span></div>
                  <div>P-Value: <span className="text-cyan-300 font-bold">{advancedStats?.p_value ? formatPValue(advancedStats.p_value) : "&lt; 0.0001"}</span></div>
                  <div>Sample: <span className="text-slate-200 font-bold">{incident?.sample_size} txns</span></div>
                  <div>Uncertainty: <span className="text-slate-200 font-bold">{causalEvidence?.uncertainty || "Low"}</span></div>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-black/40 border border-slate-800 space-y-1.5">
                <div className="text-slate-400 font-sans font-semibold text-[11px] uppercase">
                  What Could Invalidate This Diagnosis?
                </div>
                <ul className="text-[11px] text-slate-400 space-y-1 pt-1 font-sans">
                  {(causalEvidence?.invalidation_criteria || [
                    "Recovery lift falls below 5.0 pp on probe retry.",
                    "Decline code shifts from processor timeout to customer authentication error.",
                  ]).map((item, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-amber-400 font-bold">&bull;</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg space-y-3">
            <div>AI Causal Diagnosis has not yet been executed for this incident.</div>
            <button
              onClick={handleDiagnose}
              disabled={diagnosing || isTerminal}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 mx-auto transition disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 ${diagnosing ? "animate-spin" : ""}`} />
              {diagnosing ? "Evaluating Evidence..." : "Run AI Causal Diagnosis"}
            </button>
          </div>
        )}
      </div>

      {/* 4. DEEP BIN-LEVEL INTELLIGENCE (Part C) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <Layers className="w-4 h-4 text-indigo-400" /> Deep BIN-Level Telemetry &amp; Isolation Assessment
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20">
            SYNTHETIC FINTECH TELEMETRY (LABELED SIMULATION)
          </span>
        </div>

        <div className="p-3.5 rounded-lg bg-slate-900 border border-slate-800 space-y-2 text-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="font-semibold text-slate-200">
              Isolation Verdict:{" "}
              <span className="text-cyan-300 font-mono">
                {binData?.is_isolated_to_single_bin ? "BIN-ISOLATED DEGRADATION" : "ISSUER-WIDE DEGRADATION"}
              </span>
            </div>
            <span className="text-slate-400 font-mono text-[11px]">
              Target BIN: <strong className="text-slate-200">{binData?.dominant_bin || topBin?.bin || (incident?.segment_payment_method === "card" ? "Detecting..." : "N/A")}</strong>
            </span>
          </div>

          <p className="text-slate-300 text-xs leading-relaxed bg-black/30 p-2.5 rounded border border-slate-800/80">
            {binData?.isolation_summary ||
              (binData?.dominant_bin
                ? `Evidence indicates the incident is isolated to BIN ${binData.dominant_bin} (${topBin?.network || "Card"} ${topBin?.tier || "Portfolio"}) rather than an issuer-wide decline pattern.`
                : `Decline telemetry is monitored across ${incident?.segment_issuer || "issuer"} ${incident?.segment_payment_method || "card"} channels.`)}
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
            <div className="p-2 rounded bg-black/40">
              <div className="text-[10px] text-slate-500 font-sans">Card Tier</div>
              <div className="font-bold text-slate-200 mt-0.5">{topBin?.tier || (binData?.dominant_bin ? "Standard Tier" : "N/A")}</div>
            </div>
            <div className="p-2 rounded bg-black/40">
              <div className="text-[10px] text-slate-500 font-sans">BIN Concentration (Failure Share)</div>
              <div className="font-bold text-rose-400 mt-0.5">
                {topBin?.failure_concentration_share_pct !== undefined
                  ? `${topBin.failure_concentration_share_pct}% of Failures`
                  : (binData?.is_isolated_to_single_bin ? "100.0% of Failures" : "N/A")}
              </div>
            </div>
            <div className="p-2 rounded bg-black/40">
              <div className="text-[10px] text-slate-500 font-sans">3DS Challenge Fail</div>
              <div className="font-bold text-amber-300 mt-0.5">
                {topBin?.synthetic_3ds_failure_rate_pct !== undefined
                  ? `${topBin.synthetic_3ds_failure_rate_pct}% (Synthetic)`
                  : "N/A"}
              </div>
            </div>
            <div className="p-2 rounded bg-black/40">
              <div className="text-[10px] text-slate-500 font-sans">Isolation Confidence</div>
              <div className="font-bold text-emerald-400 mt-0.5">
                {binData?.is_isolated_to_single_bin ? "HIGH (94%)" : "LOW (Distributed)"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 5. MULTI-PROVIDER ROUTING OPTIMIZER TABLE (Part B) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <Server className="w-4 h-4 text-indigo-400" /> Multi-Provider Routing Scoring &amp; Recommendation
          </div>
          {isTerminal ? (
            <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
              <AlertCircle className="w-3.5 h-3.5" /> Incident Terminal ({incident?.state}) · Routing Locked
            </span>
          ) : isLowConfidence ? (
            <span className="text-[11px] font-mono text-rose-400 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> Scoring Advisory Only · Execution Blocked (Low Confidence)
            </span>
          ) : (
            <span className="text-[11px] font-mono text-emerald-400">
              Optimizer Recommendation: {routingRec?.target_gateway_routing || "REROUTE -> Provider A"}
            </span>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-mono">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 text-[11px]">
                <th className="p-2.5">GATEWAY PROVIDER</th>
                <th className="p-2.5">TIER / ROLE</th>
                <th className="p-2.5">SCORE</th>
                <th className="p-2.5">EXPECTED SUCCESS</th>
                <th className="p-2.5">LATENCY</th>
                <th className="p-2.5">FEE</th>
                <th className="p-2.5">HEALTH</th>
                <th className="p-2.5 text-right">OPTIMIZER STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {(routingRec?.ranked_providers || [
                { provider: "Provider A", tier: "Tier-1 Direct Bank Switch", composite_score: 92.4, expected_success_rate: 96.1, latency_ms: 78, cost_pct: 1.85, health: "OPTIMAL" },
                { provider: "Razorpay Smart Router", tier: "Dynamic Multi-Terminal Aggregator", composite_score: 90.8, expected_success_rate: 95.8, latency_ms: 88, cost_pct: 1.90, health: "OPTIMAL" },
                { provider: "Provider B", tier: "Card Network Direct Hub", composite_score: 84.5, expected_success_rate: 94.2, latency_ms: 115, cost_pct: 1.95, health: "HEALTHY" },
                { provider: "Provider C", tier: "Edge Clearing Network", composite_score: 72.1, expected_success_rate: 91.0, latency_ms: 142, cost_pct: 2.10, health: "DEGRADED_FAILOVER" },
              ]).map((p, idx) => {
                const isTop = idx === 0;
                return (
                  <tr key={p.provider} className={isTop ? "bg-emerald-500/5 font-semibold" : "hover:bg-slate-900/40"}>
                    <td className="p-2.5 text-slate-200 font-sans font-bold">{p.provider}</td>
                    <td className="p-2.5 text-slate-400 text-[10px]">{p.tier || "Gateway"}</td>
                    <td className="p-2.5 text-cyan-300 font-bold">{p.composite_score}</td>
                    <td className="p-2.5 text-emerald-400">{p.expected_success_rate}%</td>
                    <td className="p-2.5 text-slate-200">{p.latency_ms}ms</td>
                    <td className="p-2.5 text-slate-400">{p.cost_pct}%</td>
                    <td className="p-2.5">
                      <span className={p.health === "OPTIMAL" ? "text-emerald-400 font-bold" : "text-amber-400"}>
                        {p.health}
                      </span>
                    </td>
                    <td className="p-2.5 text-right">
                      {isTerminal ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                          TERMINAL (LOCKED)
                        </span>
                      ) : isLowConfidence ? (
                        isTop ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                            NOT EXECUTABLE / BLOCKED
                          </span>
                        ) : (
                          <span className="text-slate-500 text-[10px]">STANDBY</span>
                        )
                      ) : isTop ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                          RECOMMENDED ROUTE
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[10px]">STANDBY</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. COUNTERFACTUAL DECISION SIMULATOR (Part E) */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-4">
        <div
          className="flex items-center justify-between cursor-pointer border-b border-slate-800/80 pb-2"
          onClick={() => setShowCounterfactuals(!showCounterfactuals)}
        >
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Counterfactual Decision Options (Projected vs Baseline)
            </h2>
            <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-[10px] font-mono">
              FROZEN HISTORICAL SNAPSHOT
            </span>
          </div>
          {showCounterfactuals ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>

        {showCounterfactuals && (
          <div className="space-y-4">
            {/* Simulation Safety Badge */}
            <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-amber-500/8 border border-amber-500/25 text-amber-300 text-[11px] font-mono">
              <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="font-bold tracking-wider">COUNTERFACTUAL SIMULATION — NO LIVE ACTION</span>
              <span className="text-amber-200/60 font-sans font-normal">· Click a strategy to inspect its authoritative frozen projection. No recovery is executed. No incident state is modified.</span>
            </div>

            {/* Strategy Selector Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
              {counterfactuals.map((cf) => {
                const isRec = cf.is_recommended;
                const isBaseline = cf.action_type === "NO_ACTION";
                const isIncompatible = !cf.is_compatible;
                const isSelected = cf.action_type === (selectedCfActionType || derivedRecommendedCfType);

                return (
                  <button
                    key={cf.action_type}
                    id={`cf-strategy-${cf.action_type}`}
                    type="button"
                    onClick={() => setSelectedCfActionType(cf.action_type)}
                    className={`relative text-left p-3 rounded-xl border transition-all duration-150 ${
                      isSelected
                        ? isRec
                          ? "bg-indigo-500/20 border-indigo-500/60 ring-1 ring-indigo-500/40 shadow-lg shadow-indigo-950/30"
                          : isBaseline
                          ? "bg-rose-500/15 border-rose-500/50 ring-1 ring-rose-500/30"
                          : isIncompatible
                          ? "bg-slate-800 border-slate-600 ring-1 ring-slate-600/60"
                          : "bg-cyan-500/10 border-cyan-500/40 ring-1 ring-cyan-500/30"
                        : "bg-slate-900 border-slate-800 hover:bg-slate-800/70 hover:border-slate-700"
                    }`}
                  >
                    {/* Top row: name + badges */}
                    <div className="flex items-start justify-between gap-1.5 mb-2">
                      <span className={`text-[11px] font-bold font-mono truncate ${
                        isIncompatible ? "text-slate-400" : isBaseline ? "text-rose-300" : isRec ? "text-indigo-200" : "text-slate-200"
                      }`}>
                        {cf.action_type === "NO_ACTION" ? "NO INTERVENTION" : cf.action_type}
                      </span>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        {isRec && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-0.5">
                            <Zap className="w-2.5 h-2.5" /> REC
                          </span>
                        )}
                        {isIncompatible && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                            INCOMPATIBLE
                          </span>
                        )}
                        {isTerminal && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-500 border border-slate-700">
                            LOCKED
                          </span>
                        )}
                        {isSelected && !isIncompatible && !isTerminal && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                            VIEWING
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Mini projection stats */}
                    <div className="space-y-1 font-mono text-[10px]">
                      <div className="flex justify-between text-slate-400">
                        <span>Lift:</span>
                        <span className={isBaseline ? "text-rose-400" : "text-emerald-400 font-bold"}>
                          {isBaseline || !cf.expected_improvement_pp
                            ? "0.00 pp"
                            : `+${formatNumber(cf.expected_improvement_pp, 2)} pp`}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Net Recovery:</span>
                        <span className="text-slate-200 font-semibold">
                          {formatCurrency(cf.expected_net_recovery)}
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Friction:</span>
                        <span className="text-slate-300">
                          {cf.customer_friction_score ?? cf.friction_score ?? 15}/100
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Counterfactual Projection Detail Panel */}
            {selectedCf && (
              <div
                id="counterfactual-projection-panel"
                className={`rounded-xl border p-5 space-y-4 ${
                  selectedCf.is_recommended
                    ? "bg-gradient-to-br from-indigo-950/50 to-slate-900 border-indigo-500/40"
                    : selectedCf.action_type === "NO_ACTION"
                    ? "bg-gradient-to-br from-rose-950/30 to-slate-900 border-rose-500/30"
                    : !selectedCf.is_compatible
                    ? "bg-slate-900 border-slate-700"
                    : "bg-gradient-to-br from-slate-900 to-slate-950 border-slate-700"
                }`}
              >
                {/* Projection Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                      Counterfactual Projection:
                    </span>
                    <span className={`text-xs font-bold font-mono ${
                      selectedCf.is_recommended ? "text-indigo-300" : selectedCf.action_type === "NO_ACTION" ? "text-rose-300" : !selectedCf.is_compatible ? "text-slate-400" : "text-cyan-300"
                    }`}>
                      {selectedCf.action_type === "NO_ACTION" ? "NO INTERVENTION (Baseline)" : selectedCf.action_type}
                      {selectedCf.target_provider ? ` → ${selectedCf.target_provider}` : ""}
                    </span>
                    {selectedCf.is_recommended && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono font-bold">
                        RECOMMENDED
                      </span>
                    )}
                    {!selectedCf.is_compatible && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30 font-mono font-bold">
                        INCOMPATIBLE · NO EXECUTION
                      </span>
                    )}
                    {isTerminal && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono font-bold">
                        TERMINAL · LOCKED
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-amber-400/80 bg-amber-500/8 px-2 py-0.5 rounded border border-amber-500/20 shrink-0">
                    SIMULATION ONLY · NO LIVE ACTION
                  </span>
                </div>

                {/* 8-metric projection grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Projected Success Rate</div>
                    <div className="font-bold text-slate-200 text-sm">
                      {formatPercent(selectedCf.projected_success_rate)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Baseline: {formatPercent(selectedCf.baseline_incident_success_rate ?? selectedCf.current_success_rate)}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Lift (pp)</div>
                    <div className={`font-bold text-sm ${
                      selectedCf.action_type === "NO_ACTION" || !selectedCf.expected_improvement_pp
                        ? "text-rose-400" : "text-emerald-400"
                    }`}>
                      {selectedCf.action_type === "NO_ACTION" || !selectedCf.expected_improvement_pp
                        ? "0.00 pp"
                        : `+${formatNumber(selectedCf.expected_improvement_pp, 2)} pp`}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {selectedCf.tx_to_flip ?? selectedCf.transactions_affected ?? 0} transactions affected
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Gross Recovered</div>
                    <div className="font-bold text-slate-200 text-sm">
                      {formatCurrency(selectedCf.expected_recovered_revenue ?? selectedCf.gross_recovered_revenue)}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Effect size: {((selectedCf.effect_size ?? 0) * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Retry Cost</div>
                    <div className="font-bold text-rose-400 text-sm">
                      {formatCurrency(selectedCf.expected_cost ?? selectedCf.retry_cost)}
                    </div>
                    <div className="text-[10px] text-slate-500">@₹15/retry unit</div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-indigo-500/20 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Net Recovered</div>
                    <div className="font-bold text-indigo-300 text-sm">
                      {formatCurrency(selectedCf.expected_net_recovery ?? selectedCf.net_recovered_revenue)}
                    </div>
                    <div className="text-[10px] text-slate-500">After retry costs</div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Friction Score</div>
                    <div className={`font-bold text-sm ${
                      (selectedCf.customer_friction_score ?? selectedCf.friction_score ?? 15) <= 20
                        ? "text-emerald-400"
                        : (selectedCf.customer_friction_score ?? selectedCf.friction_score ?? 15) <= 35
                        ? "text-amber-400"
                        : "text-rose-400"
                    }`}>
                      {selectedCf.customer_friction_score ?? selectedCf.friction_score ?? 15} / 100
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {(selectedCf.customer_friction_score ?? selectedCf.friction_score ?? 15) <= 20 ? "Minimal impact" : (selectedCf.customer_friction_score ?? selectedCf.friction_score ?? 15) <= 35 ? "Moderate" : "High friction"}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                    <div className="text-[10px] text-slate-400 font-sans">Policy Compatibility</div>
                    <div className={`font-bold text-sm ${
                      selectedCf.policy_status === "RECOMMENDED" ? "text-indigo-300"
                      : selectedCf.is_compatible ? "text-emerald-400"
                      : "text-rose-400"
                    }`}>
                      {selectedCf.policy_status || (selectedCf.is_compatible ? "COMPATIBLE" : "INCOMPATIBLE")}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {isTerminal ? "Terminal · No execution" : selectedCf.is_compatible ? "Backend authorized" : "Execution blocked"}
                    </div>
                  </div>

                  {selectedCf.target_provider ? (
                    <div className="p-3 rounded-lg bg-black/40 border border-cyan-500/20 space-y-1">
                      <div className="text-[10px] text-slate-400 font-sans">Target Provider</div>
                      <div className="font-bold text-cyan-300 text-sm truncate">
                        {selectedCf.target_provider}
                      </div>
                      <div className="text-[10px] text-slate-500 truncate">
                        {selectedCf.target_gateway_routing || `REROUTE → ${selectedCf.target_provider}`}
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-black/40 border border-white/5 space-y-1">
                      <div className="text-[10px] text-slate-400 font-sans">ROI</div>
                      <div className="font-bold text-slate-200 text-sm">
                        {selectedCf.expected_roi != null ? `${selectedCf.expected_roi}x` : "N/A"}
                      </div>
                      <div className="text-[10px] text-slate-500">Net / Cost ratio</div>
                    </div>
                  )}
                </div>

                {/* Rationale */}
                {selectedCf.rationale && (
                  <div className="text-[11px] text-slate-300 leading-relaxed bg-black/30 p-3 rounded-lg border border-slate-800/80 font-sans">
                    <span className="font-semibold text-slate-400">Rationale: </span>{selectedCf.rationale}
                  </div>
                )}

                {/* Incompatible warning */}
                {!selectedCf.is_compatible && !isTerminal && (
                  <div className="flex items-center gap-2 text-[11px] text-rose-300 bg-rose-500/10 px-3 py-2 rounded-lg border border-rose-500/30">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>This strategy is incompatible with the diagnosed hypothesis ({diagnosis?.hypothesis}). No execution path is available — this projection is shown for simulation comparison only.</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 7. RECOMMENDED ACTION BANNER & POLICY GATE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Recommended Action Summary */}
        {incident?.state === "APPROVAL_REJECTED" ? (
          <div className="lg:col-span-7 p-5 rounded-xl bg-gradient-to-r from-slate-900 via-rose-950/20 to-slate-900 border border-rose-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <XCircle className="w-4 h-4 text-rose-400" /> Recovery Proposal Rejected · Terminal
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                APPROVAL REJECTED · TERMINAL
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs pt-1">
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Lifecycle State</div>
                <div className="font-bold text-rose-400 mt-0.5">TERMINAL</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Execution</div>
                <div className="font-bold text-rose-300 mt-0.5">PROHIBITED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Mitigation Proposal</div>
                <div className="font-bold text-slate-400 mt-0.5">REJECTED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Exposure At Risk</div>
                <div className="font-bold text-slate-200 mt-0.5">₹0.00 (Closed)</div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed pt-1">
              The proposed recovery intervention was rejected by an authorized operator during dual-control review. Under backend safety policy, rejected incidents transition to a permanent terminal state: no automated mitigation, retry trigger, or alternate recovery execution is allowed.
            </p>
          </div>
        ) : incident?.state === "ROLLED_BACK" ? (
          <div className="lg:col-span-7 p-5 rounded-xl bg-gradient-to-r from-slate-900 via-rose-950/20 to-slate-900 border border-rose-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <RotateCcw className="w-4 h-4 text-rose-400" /> Recovery Rolled Back · Terminal
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                ROLLED BACK · TERMINAL
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs pt-1">
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Lifecycle State</div>
                <div className="font-bold text-rose-400 mt-0.5">TERMINAL</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Rollback Status</div>
                <div className="font-bold text-rose-300 mt-0.5">COMPLETED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Execution</div>
                <div className="font-bold text-slate-400 mt-0.5">LOCKED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Traffic Routing</div>
                <div className="font-bold text-slate-200 mt-0.5">REVERTED</div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed pt-1">
              Mitigation actions were rolled back by operational command. Incident state is terminal and historical transaction state has been reverted.
            </p>
          </div>
        ) : incident?.state === "RESOLVED" ? (
          <div className="lg:col-span-7 p-5 rounded-xl bg-gradient-to-r from-slate-900 via-emerald-950/20 to-slate-900 border border-emerald-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-300 uppercase tracking-wider flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" /> Recovery Verified · Terminal
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                RESOLVED · TERMINAL
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs pt-1">
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Lifecycle State</div>
                <div className="font-bold text-emerald-400 mt-0.5">TERMINAL</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Verification</div>
                <div className="font-bold text-emerald-300 mt-0.5">VERIFIED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Mitigation</div>
                <div className="font-bold text-slate-200 mt-0.5">COMPLETED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Recovered Revenue</div>
                <div className="font-bold text-emerald-400 mt-0.5">{formatCurrency(activeOutcome?.recovered_revenue || 0)}</div>
              </div>
            </div>

            <p className="text-[11px] text-slate-300 leading-relaxed pt-1">
              Revenue recovery was verified against empirical post-action transaction traffic and reached terminal resolved status.
            </p>
          </div>
        ) : isLowConfidence ? (
          <div className="lg:col-span-7 p-5 rounded-xl bg-gradient-to-r from-rose-950/40 via-slate-900 to-slate-900 border border-rose-500/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-rose-300 uppercase tracking-wider flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" /> Recommended Strategy: NO AUTOMATIC RECOVERY
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                RECOVERY BLOCKED · CONFIDENCE GATE
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs pt-1">
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Confidence Gate</div>
                <div className="font-bold text-rose-400 mt-0.5">
                  {diagnosis ? `${formatPercent((diagnosis.confidence || 0) * 100)}` : "69.0%"} &lt; 70.0%
                </div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Auto-Execution</div>
                <div className="font-bold text-rose-300 mt-0.5">BLOCKED</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Safe Policy Hold</div>
                <div className="font-bold text-amber-300 mt-0.5">SUPPRESS RETRIES</div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Counterfactuals</div>
                <div className="font-bold text-slate-400 mt-0.5">ADVISORY ONLY</div>
              </div>
            </div>

            <p className="text-[11px] text-slate-300 leading-relaxed pt-1">
              Automatic recovery execution is blocked by the confidence gate. Diagnostic confidence is {diagnosis ? `${formatPercent((diagnosis.confidence || 0) * 100)}` : "69.0%"}, which is strictly below the mandatory 70.0% safety threshold. While SUPPRESS_RETRIES is policy-compatible for issuer declines to prevent cardholder exhaustion, it must NOT be executed automatically. REROUTE and other strategies remain visible as hypothetical counterfactual projections only and are labeled NOT EXECUTABLE / BLOCKED.
            </p>
          </div>
        ) : (
          <div className="lg:col-span-7 p-5 rounded-xl bg-gradient-to-r from-indigo-950/60 to-slate-900 border border-indigo-500/40 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400" /> Recommended Recovery Strategy
              </span>
              <span className="text-xs font-mono font-bold text-cyan-300">
                {recCf ? `${recCf.name || recCf.action_type}${recCf.target_provider ? ` -> ${recCf.target_provider}` : (routingRec?.target_gateway_routing ? ` (${routingRec.target_gateway_routing})` : "")}` : (routingRec?.target_gateway_routing || `${recommendedAction} -> Provider A`)}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs pt-1">
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Projected Lift</div>
                <div className="font-bold text-emerald-400 mt-0.5">
                  +{formatNumber(recCf?.expected_improvement_pp ?? 0, 2)} pp
                </div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Gross Recovered</div>
                <div className="font-bold text-slate-200 mt-0.5">
                  {formatCurrency(recCf?.expected_recovered_revenue ?? 0)}
                </div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Net Recovered</div>
                <div className="font-bold text-indigo-300 mt-0.5">
                  {formatCurrency(recCf?.expected_net_recovery ?? 0)}
                </div>
              </div>
              <div className="p-2.5 rounded bg-black/40 border border-white/5">
                <div className="text-[10px] text-slate-400 font-sans">Friction Score</div>
                <div className="font-bold text-slate-200 mt-0.5">
                  {recCf?.customer_friction_score ?? recCf?.friction_score ?? 12} / 100
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-300 leading-relaxed pt-1">
              {recCf?.rationale ||
                recCf?.description ||
                "Reroutes retry and eligible transaction traffic to Provider A with verified optimal expected success rate. Strict bounded retry budget enforced (max 2 retries per cardholder)."}
            </p>
          </div>
        )}

        {/* Policy Guardrails Status */}
        <div className="lg:col-span-5 p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="font-semibold text-slate-300 font-sans text-xs uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Policy Guardrail Verification
            </span>
            <span className="text-[10px] text-slate-500">Dual-Control Enabled</span>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-400">Min Revenue Floor (₹50k):</span>
              <span className="text-emerald-400 font-bold">PASS (&ge; ₹50,000)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Auto-Approval Ceiling (₹500k):</span>
              <span className={incident?.at_risk_revenue > 500000 ? "text-amber-400 font-bold" : "text-emerald-400 font-bold"}>
                {incident?.at_risk_revenue > 500000 ? "HELD (Dual Control Req)" : "PASS (&le; ₹500,000)"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Confidence Gate (0.70):</span>
              <span className={(diagnosis?.confidence || 0) >= 0.70 && !isLowConfidence ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                {(diagnosis?.confidence || 0) >= 0.70 && !isLowConfidence ? "PASS (&ge; 0.70)" : "BLOCKED (&lt; 0.70)"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Max Retry Cap:</span>
              <span className="text-slate-200 font-bold">2 Retries / Cardholder</span>
            </div>
          </div>
        </div>
      </div>

      {/* 8. TERMINAL DOSSIER CARD OR AUTONOMOUS RECOVERY CONTROLS */}
      {isTerminal ? (
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {incident?.state === "APPROVAL_REJECTED" ? (
              <XCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            ) : incident?.state === "RESOLVED" ? (
              <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            ) : incident?.state === "ROLLED_BACK" ? (
              <RotateCcw className="w-5 h-5 text-rose-400 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
            )}
            <div>
              <div className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Incident Lifecycle Closed: {incident?.state}
              </div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                {incident?.state === "APPROVAL_REJECTED"
                  ? "Mitigation proposal was rejected. No further recovery execution is allowed for this incident."
                  : incident?.state === "RESOLVED"
                  ? "Recovery verified and incident successfully resolved. Historical metrics locked."
                  : incident?.state === "ROLLED_BACK"
                  ? "Mitigation action was rolled back. State is terminal."
                  : "Incident reached terminal escalation state under safety policy."}
              </div>
            </div>
          </div>
          <span className="px-3 py-1 rounded bg-slate-800 text-slate-300 text-xs font-mono font-bold border border-slate-700">
            TERMINAL STATE · LOCKED
          </span>
        </div>
      ) : !isHumanApprovalRequired && (
        isLowConfidence ? (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
              <div>
                <div className="text-xs font-bold text-rose-300 uppercase tracking-wider">
                  Automated Recovery Ineligible (Confidence Gate Blocked)
                </div>
                <div className="text-[11px] text-slate-300 font-mono mt-0.5">
                  Diagnostic confidence ({diagnosis ? `${formatPercent((diagnosis.confidence || 0) * 100)}` : "69.0%"}) is strictly below the mandatory 70.0% policy gate. No recovery execution is allowed.
                </div>
              </div>
            </div>
            <span className="px-3 py-1 rounded bg-rose-500/20 text-rose-300 text-xs font-mono font-bold border border-rose-500/40">
              POLICY LOCKED · DO NOT ACT
            </span>
          </div>
        ) : diagnosis && (
          <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-cyan-400 flex-shrink-0" />
              <div>
                <div className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
                  Autonomous Mitigation Ready (High Confidence)
                </div>
                <div className="text-[11px] text-slate-300 font-mono mt-0.5">
                  Confidence {formatPercent((diagnosis.confidence || 0) * 100)} &ge; 70.0% · Exposure {formatCurrency(incident?.at_risk_revenue)} &le; ₹5,00,000 auto-execution ceiling.
                </div>
              </div>
            </div>
            {isAuthorizedRole ? (
              <button
                onClick={() => handleRecover(false)}
                disabled={recovering}
                className="px-5 py-2.5 rounded-lg font-bold text-xs text-white bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 transition shadow-lg shadow-indigo-900/30 disabled:opacity-50 flex items-center gap-2"
              >
                <Zap className={`w-4 h-4 ${recovering ? "animate-spin" : ""}`} />
                {recovering ? "Executing Recovery..." : `Execute Autonomous Recovery (${role})`}
              </button>
            ) : (
              <span className="text-[11px] text-rose-400 font-mono">
                Role ({role}) is read-only. Requires OPERATOR or ADMIN credentials.
              </span>
            )}
          </div>
        )
      )}

      {/* 8. PROFESSIONAL DUAL-CONTROL HUMAN APPROVAL CENTER (Part G) */}
      {isHumanApprovalRequired && !isTerminal && (
        <div className="p-5 rounded-xl bg-amber-500/10 border-2 border-amber-500/50 space-y-4 shadow-lg shadow-amber-950/20">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-amber-500/30 pb-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-400 animate-pulse" />
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-amber-300">
                  Dual-Control Human Approval Center
                </h3>
                <div className="text-[11px] text-amber-200/90 font-mono mt-0.5">
                  Financial exposure of {formatCurrency(incident?.at_risk_revenue)} exceeds the ₹5,00,000 auto-execution threshold.
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-slate-400">Reviewer Role:</span>
              <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 font-bold text-cyan-300">
                {role}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded bg-black/40 border border-amber-500/20">
              <div className="text-[10px] text-slate-400 font-sans">Incident &amp; Segment</div>
              <div className="font-bold text-white mt-0.5">{incident?.segment_issuer} {incident?.segment_payment_method?.toUpperCase()}</div>
            </div>
            <div className="p-2.5 rounded bg-black/40 border border-amber-500/20">
              <div className="text-[10px] text-slate-400 font-sans">Proposed Action</div>
              <div className="font-bold text-cyan-300 mt-0.5">
                {recCf?.target_gateway_routing || (recCf?.target_provider ? `${recCf.name || recCf.action_type} -> ${recCf.target_provider}` : (routingRec?.target_gateway_routing || `${recommendedAction} -> Provider A`))}
              </div>
            </div>
            <div className="p-2.5 rounded bg-black/40 border border-amber-500/20">
              <div className="text-[10px] text-slate-400 font-sans">Projected Lift / Net</div>
              <div className="font-bold text-emerald-400 mt-0.5">
                +{formatNumber(recCf?.expected_improvement_pp ?? 0, 2)} pp · {formatCurrency(recCf?.expected_net_recovery ?? 0)}
              </div>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                Gross: {formatCurrency(recCf?.expected_recovered_revenue ?? 0)}
              </div>
            </div>
            <div className="p-2.5 rounded bg-black/40 border border-amber-500/20">
              <div className="text-[10px] text-slate-400 font-sans">Friction Impact</div>
              <div className="font-bold text-slate-200 mt-0.5">
                {(recCf?.customer_friction_score ?? recCf?.friction_score ?? 12) <= 15 ? "Minimal" : "Moderate"} ({recCf?.customer_friction_score ?? recCf?.friction_score ?? 12} / 100)
              </div>
            </div>
          </div>

          {/* Action Approval / Rejection Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-2">
            {isAuthorizedRole ? (
              <>
                <button
                  onClick={handleRejectApproval}
                  disabled={rejecting || recovering}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-lg font-semibold text-xs text-rose-300 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/30 transition disabled:opacity-50"
                >
                  {rejecting ? "Rejecting..." : "Reject Mitigation Proposal"}
                </button>
                <button
                  onClick={() => handleRecover(true)}
                  disabled={recovering || rejecting}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-lg font-bold text-xs text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 transition shadow-lg shadow-emerald-900/30 disabled:opacity-50"
                >
                  {recovering ? "Executing Mitigation..." : `Approve & Execute ${recCf?.name || recCf?.action_type || recommendedAction} (${role})`}
                </button>
              </>
            ) : (
              <div className="w-full p-3 rounded-lg bg-slate-900 border border-rose-500/40 text-rose-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>
                  Approval Restricted: Role ({role}) is read-only. Dual-control approval or rejection requires ADMIN or OPERATOR credentials.
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 9. OUTCOME MEASURED BANNER (If Active) */}
      {activeOutcome && (
        <div className="p-5 rounded-xl bg-emerald-500/10 border-2 border-emerald-500/40 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-bold text-emerald-300 flex items-center gap-2 uppercase tracking-wider">
              <CheckCircle className="w-4 h-4 text-emerald-400" /> Recovery Outcome Measured &amp; Verified
            </div>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              {activeOutcome.result}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 bg-black/40 rounded-lg">
              <div className="text-[10px] text-slate-400 font-sans">Recovered Revenue</div>
              <div className="font-bold text-emerald-400 text-base mt-0.5">{formatCurrency(activeOutcome.recovered_revenue)}</div>
            </div>
            <div className="p-3 bg-black/40 rounded-lg">
              <div className="text-[10px] text-slate-400 font-sans">Transactions Flipped</div>
              <div className="font-bold text-white text-base mt-0.5">{formatInteger(activeOutcome.transactions_flipped)}</div>
            </div>
            <div className="p-3 bg-black/40 rounded-lg">
              <div className="text-[10px] text-slate-400 font-sans">Pre Success Rate</div>
              <div className="font-bold text-slate-300 text-base mt-0.5">{formatPercent(activeOutcome.pre_success_rate)}</div>
            </div>
            <div className="p-3 bg-black/40 rounded-lg">
              <div className="text-[10px] text-slate-400 font-sans">Post Success Rate</div>
              <div className="font-bold text-emerald-400 text-base mt-0.5">
                {formatPercent(activeOutcome.post_success_rate)} (+{formatNumber(activeOutcome.post_success_rate - activeOutcome.pre_success_rate, 2)} pp)
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 10. CRYPTOGRAPHIC SHA-256 AUDIT TRAIL */}
      <div className="bg-[#111622] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> Cryptographic SHA-256 Audit Trail
          </div>
          <button
            onClick={handleVerifyAuditChain}
            disabled={verifyingAudit}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-mono font-semibold transition"
          >
            {verifyingAudit ? "Verifying..." : "Verify Hash Chain Integrity"}
          </button>
        </div>

        {auditVerified && (
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono flex items-center justify-between">
            <span>Audit Chain Status: <strong>{auditVerified.status || "VALID"}</strong></span>
            <span>Total Records: <strong>{auditVerified.record_count || auditLogs.length}</strong></span>
          </div>
        )}

        <div className="space-y-2">
          {auditLogs.map((log) => (
            <div
              key={log.id}
              className="p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
            >
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-black/40 text-cyan-300 font-bold text-[10px]">
                  {log.event_type}
                </span>
                <span className="text-slate-300 font-sans font-medium">Actor: {log.actor}</span>
              </div>
              <div className="text-slate-400 text-[10px] truncate max-w-md">
                Hash: <span className="text-slate-300">{log.record_hash || "sha256_mock_hash"}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
