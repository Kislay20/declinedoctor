import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ShieldAlert,
  Cpu,
  Play,
  CheckCircle,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  HelpCircle,
  BarChart2,
  ChevronDown,
  ChevronUp,
  Clock,
} from "lucide-react";
import api from "../api";
import {
  formatCurrency,
  formatPercent,
  formatPp,
  formatConfidence,
  formatNumber,
  formatInteger,
  formatPValue,
} from "../utils/format";

export default function IncidentView() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [counterfactuals, setCounterfactuals] = useState([]);
  const [explanation, setExplanation] = useState(null);
  const [safetyCheck, setSafetyCheck] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [showExplanation, setShowExplanation] = useState(false);
  const [showCounterfactuals, setShowCounterfactuals] = useState(true);
  const [role, setRole] = useState(localStorage.getItem("declinedoctor_user_role") || "OPERATOR");

  const getRecommendedAction = (hypothesis) => {
    if (hypothesis === "ROUTING_CONNECTIVITY_ISSUE") return "REROUTE";
    if (hypothesis === "BIN_LEVEL_TEMPORARY_ISSUE") return "ADJUST_RETRY_TIMING";
    return "SUPPRESS_RETRIES";
  };

  const fetchIncidentData = useCallback(async () => {
    const [incRes, cfRes, expRes, safeRes, auditRes] = await Promise.all([
      api.get(`/incidents/${id}`),
      api.get(`/incidents/${id}/counterfactuals`).catch(() => ({ data: [] })),
      api.get(`/incidents/${id}/explain`).catch(() => ({ data: null })),
      api.get(`/incidents/${id}/safety`).catch(() => ({ data: null })),
      api.get(`/incidents/${id}/audit`).catch(() => ({ data: [] })),
    ]);

    return {
      incidentData: incRes.data,
      cfData: cfRes.data || [],
      expData: expRes.data,
      safeData: safeRes.data,
      auditData: auditRes.data || [],
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
      const actionType = getRecommendedAction(data?.diagnosis?.hypothesis);
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

  if (!data)
    return (
      <div className="text-center py-16 text-slate-400">Loading evidence...</div>
    );

  const { incident, diagnosis, recovery_action, outcome } = data;
  const activeOutcome = recoveryResult?.outcome || outcome;
  const recommendedAction = diagnosis ? getRecommendedAction(diagnosis.hypothesis) : "REROUTE";

  const isTerminal = [
    "RESOLVED",
    "ESCALATED_LOW_CONFIDENCE",
    "ESCALATED_LOW_REVENUE",
    "ESCALATED_INSUFFICIENT_RECOVERY",
    "ROLLED_BACK",
  ].includes(incident?.state);

  const isHumanApprovalRequired =
    incident?.state === "AWAITING_HUMAN_APPROVAL" ||
    safetyCheck?.status === "HUMAN_APPROVAL_REQUIRED" ||
    ((incident?.at_risk_revenue || 0) > 500000 && !activeOutcome && !isTerminal);

  const isAuthorizedRole = role === "ADMIN" || role === "OPERATOR";

  // Strict audit verification: An action is shown as Applied ONLY when an actual recovery action was executed and an ACTION_APPLIED audit event exists
  const hasActionAppliedAudit = auditLogs.some((l) => l.event_type === "ACTION_APPLIED");
  const isActionApplied = hasActionAppliedAudit && Boolean(recovery_action) && !recovery_action?.is_rollback;

  const isRolledBack =
    incident?.state === "ROLLED_BACK" ||
    auditLogs.some((l) => l.event_type === "ROLLBACK_EXECUTED") ||
    Boolean(recovery_action?.is_rollback);

  const isBlockedLowConfidence =
    incident?.state === "ESCALATED_LOW_CONFIDENCE" ||
    (Boolean(diagnosis) && diagnosis.confidence < 0.70 && !isActionApplied);

  const isBlockedLowRevenue =
    incident?.state === "ESCALATED_LOW_REVENUE" ||
    (recoveryResult?.status === "escalated" && recoveryResult?.reason === "low_revenue");

  const isUnauthorizedBlocked =
    (recoveryResult?.status === "blocked" && recoveryResult?.reason === "unauthorized_role") ||
    auditLogs.some((l) =>
      l.event_type === "RECOVERY_BLOCKED" &&
      (
        (typeof l.details_json === "string" ? l.details_json : JSON.stringify(l.details_json || {})).includes("unauthorized") ||
        (typeof l.details_json === "string" ? l.details_json : JSON.stringify(l.details_json || {})).includes("not authorized") ||
        (typeof l.details_json === "string" ? l.details_json : JSON.stringify(l.details_json || {})).includes("Requires ADMIN")
      )
    );

  const isAwaitingHumanApproval =
    !isActionApplied && (
      incident?.state === "AWAITING_HUMAN_APPROVAL" ||
      isHumanApprovalRequired ||
      recoveryResult?.status === "pending_human_approval"
    );

  const appliedActionType =
    recovery_action?.action_type ||
    recoveryResult?.action?.action_type ||
    recommendedAction;

  const getStep5Presentation = () => {
    if (isRolledBack) {
      return {
        borderStyle: "border-purple-500/50 bg-purple-500/5",
        textStyle: "text-purple-400",
        title: "Recovery Rolled Back",
        subtitle: "Mitigation reverted by operator",
        detail: "Rollback audit hash recorded",
      };
    }
    if (isActionApplied) {
      return {
        borderStyle: "border-emerald-500/50 bg-emerald-500/5",
        textStyle: "text-emerald-400",
        title: `${appliedActionType} Applied`,
        subtitle: "Audit hash recorded",
        detail: "Autonomous execution complete",
      };
    }
    if (isBlockedLowConfidence) {
      return {
        borderStyle: "border-rose-500/50 bg-rose-500/5",
        textStyle: "text-rose-400",
        title: "Mitigation Blocked",
        subtitle: "BLOCKED / NOT EXECUTED",
        detail: `Low confidence (${formatConfidence(diagnosis?.confidence || 0.69)} < 0.70)`,
      };
    }
    if (isUnauthorizedBlocked) {
      return {
        borderStyle: "border-rose-500/50 bg-rose-500/5",
        textStyle: "text-rose-400",
        title: "Execution Blocked",
        subtitle: "Unauthorized role attempt",
        detail: "Requires ADMIN or OPERATOR role",
      };
    }
    if (isBlockedLowRevenue) {
      return {
        borderStyle: "border-rose-500/50 bg-rose-500/5",
        textStyle: "text-rose-400",
        title: "Mitigation Blocked",
        subtitle: "BLOCKED / NOT EXECUTED",
        detail: "At-risk revenue < ₹50K floor",
      };
    }
    if (isAwaitingHumanApproval) {
      return {
        borderStyle: "border-amber-500/50 bg-amber-500/5",
        textStyle: "text-amber-400",
        title: "Approval Required",
        subtitle: "Awaiting human authorization",
        detail: "Exposure > ₹5.00L policy limit",
      };
    }
    if (isTerminal) {
      return {
        borderStyle: "border-slate-800",
        textStyle: "text-slate-400",
        title: "Recovery Blocked",
        subtitle: "Terminal state locked",
        detail: "No action applied",
      };
    }
    return {
      borderStyle: "border-slate-800",
      textStyle: "text-slate-500",
      title: "Mitigation Pending",
      subtitle: diagnosis ? `Recommended: ${recommendedAction}` : "Pending execution",
      detail: "Awaiting execution trigger",
    };
  };

  const step5 = getStep5Presentation();

  const getStep6Presentation = () => {
    if (isRolledBack) {
      return {
        borderStyle: "border-purple-500/50 bg-purple-500/5",
        textStyle: "text-purple-400",
        title: "Rollback Finalized",
        subtitle: "Transaction states restored",
      };
    }
    if (activeOutcome && isActionApplied) {
      const lift = activeOutcome.post_success_rate - activeOutcome.pre_success_rate;
      return {
        borderStyle: "border-emerald-500/50 bg-emerald-500/5",
        textStyle: "text-emerald-400",
        title: "Outcome Verified",
        subtitle: `+${formatNumber(lift, 1)}pp lift measured`,
      };
    }
    if (isBlockedLowConfidence) {
      return {
        borderStyle: "border-rose-500/30",
        textStyle: "text-rose-400",
        title: "Mitigation Skipped",
        subtitle: "No recovery telemetry",
      };
    }
    if (isUnauthorizedBlocked) {
      return {
        borderStyle: "border-rose-500/30",
        textStyle: "text-rose-400",
        title: "Execution Rejected",
        subtitle: "No recovery telemetry",
      };
    }
    if (isBlockedLowRevenue) {
      return {
        borderStyle: "border-rose-500/30",
        textStyle: "text-rose-400",
        title: "Mitigation Skipped",
        subtitle: "Immaterial exposure",
      };
    }
    if (isAwaitingHumanApproval) {
      return {
        borderStyle: "border-amber-500/30",
        textStyle: "text-amber-400",
        title: "Pending Approval",
        subtitle: "Awaiting execution trigger",
      };
    }
    return {
      borderStyle: "border-slate-800",
      textStyle: "text-slate-500",
      title: incident?.state ? incident.state.replace(/_/g, " ") : "Telemetry Pending",
      subtitle: "Awaiting telemetry",
    };
  };

  const step6 = getStep6Presentation();

  const canRollback =
    (incident?.state === "RESOLVED" || incident?.state === "ACTION_APPLIED") &&
    recovery_action &&
    !recovery_action.is_rollback &&
    isAuthorizedRole;

  // Parse advanced stats if available
  let advancedStats = null;
  if (incident?.advanced_stats_json) {
    try {
      advancedStats = typeof incident.advanced_stats_json === "string"
        ? JSON.parse(incident.advanced_stats_json)
        : incident.advanced_stats_json;
    } catch {
      advancedStats = null;
    }
  }

  const getStatusBadge = (state) => {
    if (state === "RESOLVED") {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">RESOLVED</span>;
    }
    if (state === "AWAITING_HUMAN_APPROVAL") {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">AWAITING HUMAN APPROVAL</span>;
    }
    if (state?.startsWith("ESCALATED_")) {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">{state.replace("ESCALATED_", "ESCALATED: ")}</span>;
    }
    if (state === "ROLLED_BACK") {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">ROLLED BACK</span>;
    }
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">{state}</span>;
  };

  const getSafetyBannerInfo = () => {
    if (!diagnosis) {
      return {
        statusText: "RECOVERY NOT YET EVALUATED",
        reasonText: "Run diagnosis to evaluate recovery eligibility.",
        style: "bg-slate-800/80 border-slate-700 text-slate-300",
        icon: <Clock className="w-6 h-6 text-slate-400 flex-shrink-0" />,
        confText: "N/A (Not Diagnosed)",
      };
    }
    if (incident?.state === "RESOLVED") {
      return {
        statusText: "RECOVERY LOCKED — INCIDENT RESOLVED",
        reasonText: "Further automated recovery is blocked by terminal-state protection.",
        style: "bg-blue-500/10 border-blue-500/30 text-blue-300",
        icon: <ShieldCheck className="w-6 h-6 text-blue-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)} (Terminal Locked)`,
      };
    }
    if (incident?.state === "ESCALATED_LOW_CONFIDENCE") {
      return {
        statusText: "RECOVERY BLOCKED — LOW CONFIDENCE",
        reasonText: "Confidence is below the 0.70 safety threshold. Automated recovery is blocked to prevent misrouting.",
        style: "bg-rose-500/10 border-rose-500/30 text-rose-300",
        icon: <AlertTriangle className="w-6 h-6 text-rose-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)} (< 0.70 Threshold)`,
      };
    }
    if (incident?.state === "ESCALATED_LOW_REVENUE") {
      return {
        statusText: "RECOVERY BLOCKED — BELOW REVENUE FLOOR",
        reasonText: "At-risk revenue is below the ₹50,000.00 minimum auto-action threshold.",
        style: "bg-rose-500/10 border-rose-500/30 text-rose-300",
        icon: <AlertTriangle className="w-6 h-6 text-rose-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)} (Below Floor)`,
      };
    }
    if (incident?.state === "ESCALATED_INSUFFICIENT_RECOVERY") {
      return {
        statusText: "RECOVERY TERMINATED — INSUFFICIENT LIFT",
        reasonText: "Recovery produced insufficient success rate improvement. Escalated to human on-call.",
        style: "bg-rose-500/10 border-rose-500/30 text-rose-300",
        icon: <AlertTriangle className="w-6 h-6 text-rose-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)}`,
      };
    }
    if (incident?.state === "ROLLED_BACK") {
      return {
        statusText: "RECOVERY ROLLED BACK",
        reasonText: "Applied mitigation has been rolled back by human operator.",
        style: "bg-purple-500/10 border-purple-500/30 text-purple-300",
        icon: <RotateCcw className="w-6 h-6 text-purple-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)}`,
      };
    }
    if (isHumanApprovalRequired) {
      return {
        statusText: "HUMAN APPROVAL REQUIRED",
        reasonText: "At-risk revenue exceeds the ₹5,00,000 automatic execution limit.",
        style: "bg-amber-500/10 border-amber-500/30 text-amber-300",
        icon: <AlertCircle className="w-6 h-6 text-amber-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)} (≥ 0.70)`,
      };
    }
    if (safetyCheck?.status === "SAFE_TO_EXECUTE") {
      return {
        statusText: "SAFE TO EXECUTE",
        reasonText: "All safety checks passed.",
        style: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
        icon: <ShieldCheck className="w-6 h-6 text-emerald-400 flex-shrink-0" />,
        confText: `${formatConfidence(diagnosis.confidence)} (≥ 0.70)`,
      };
    }
    return {
      statusText: safetyCheck?.status ? safetyCheck.status.replace(/_/g, " ") : "EVALUATION IN PROGRESS",
      reasonText: safetyCheck?.reason || "Evaluating safety policies...",
      style: "bg-rose-500/10 border-rose-500/30 text-rose-300",
      icon: <AlertTriangle className="w-6 h-6 text-rose-400 flex-shrink-0" />,
      confText: diagnosis ? `${formatConfidence(diagnosis.confidence)}` : "N/A",
    };
  };

  const bannerInfo = getSafetyBannerInfo();

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
            <Link to="/" className="hover:text-white transition">Dashboard</Link>
            <span>/</span>
            <span className="text-slate-200">Incident {incident?.id}</span>
          </div>
          <h1 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
            {incident?.segment_issuer} {incident?.segment_payment_method} Degradation
            {getStatusBadge(incident?.state)}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to={`/incident/${id}/audit`}
            className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition"
          >
            Cryptographic Audit Trail
          </Link>

          {canRollback && (
            <button
              onClick={handleRollback}
              disabled={rollingBack}
              className="px-3.5 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-semibold flex items-center gap-1.5 transition"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${rollingBack ? "animate-spin" : ""}`} /> Rollback Recovery
            </button>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center gap-3 text-xs">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Safety Gate Banner (Phase 4, Updated Semantics) */}
      <div className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-3 ${bannerInfo.style}`}>
        <div className="flex items-center gap-3">
          {bannerInfo.icon}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider">
              Safety Evaluation: {bannerInfo.statusText}
            </div>
            <div className="text-xs opacity-90 mt-0.5">{bannerInfo.reasonText}</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded bg-black/40 border border-white/10">
            Conf: {bannerInfo.confText}
          </span>
          <span className="px-2 py-0.5 rounded bg-black/40 border border-white/10">
            Risk: {formatCurrency(incident?.at_risk_revenue)}
          </span>
          <span className="px-2 py-0.5 rounded bg-black/40 border border-white/10">
            Retry Cap: {safetyCheck?.retry_limit || 2}
          </span>
        </div>
      </div>

      {/* Recovery Timeline (Phase 13 Demo Component) */}
      <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Autonomous Recovery Timeline &amp; State Progression
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            Lifecycle: RECEIVED &rarr; ANOMALY &rarr; DIAGNOSED &rarr; POLICY &rarr; ACTION &rarr; OUTCOME
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5 pt-1">
          {/* Step 1: Anomaly Detected */}
          <div className="p-3 rounded-lg bg-slate-900 border border-emerald-500/30">
            <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400">
              <span>10:02:00</span>
              <span className="font-bold">STEP 1</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">Anomaly Detected</div>
            <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
              Drop -{formatNumber(incident?.drop_pp || 0, 1)}pp ({formatInteger(incident?.sample_size || 0)} txns)
            </div>
          </div>

          {/* Step 2: Exposure Risk */}
          <div className="p-3 rounded-lg bg-slate-900 border border-emerald-500/30">
            <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400">
              <span>10:02:45</span>
              <span className="font-bold">STEP 2</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">Revenue at Risk</div>
            <div className="text-[10px] text-rose-400 font-mono mt-0.5 font-bold">
              {formatCurrency(incident?.at_risk_revenue)}
            </div>
          </div>

          {/* Step 3: AI Diagnosis */}
          <div className={`p-3 rounded-lg bg-slate-900 border ${diagnosis ? "border-emerald-500/30" : "border-slate-800"}`}>
            <div className={`flex items-center justify-between text-[10px] font-mono ${diagnosis ? "text-emerald-400" : "text-slate-500"}`}>
              <span>10:03:10</span>
              <span className="font-bold">STEP 3</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">
              {diagnosis ? "AI Causal Diagnosis" : "Diagnosis Pending"}
            </div>
            <div className="text-[10px] text-indigo-300 font-mono mt-0.5 truncate">
              {diagnosis ? `${diagnosis.hypothesis} (${formatConfidence(diagnosis.confidence)})` : "Awaiting classification"}
            </div>
          </div>

          {/* Step 4: Policy Gate */}
          <div className={`p-3 rounded-lg bg-slate-900 border ${
            isBlockedLowConfidence
              ? "border-rose-500/50 bg-rose-500/5"
              : isBlockedLowRevenue
              ? "border-rose-500/50 bg-rose-500/5"
              : isUnauthorizedBlocked
              ? "border-rose-500/50 bg-rose-500/5"
              : isAwaitingHumanApproval
              ? "border-amber-500/50 bg-amber-500/5"
              : diagnosis
              ? "border-emerald-500/30"
              : "border-slate-800"
          }`}>
            <div className={`flex items-center justify-between text-[10px] font-mono ${
              isBlockedLowConfidence || isBlockedLowRevenue || isUnauthorizedBlocked
                ? "text-rose-400"
                : isAwaitingHumanApproval
                ? "text-amber-400"
                : "text-emerald-400"
            }`}>
              <span>10:03:30</span>
              <span className="font-bold">STEP 4</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">
              {isBlockedLowConfidence
                ? "Gate: Low Conf Block"
                : isBlockedLowRevenue
                ? "Gate: Rev Floor Block"
                : isUnauthorizedBlocked
                ? "Gate: Role Restricted"
                : isAwaitingHumanApproval
                ? "Gate: Human Approval"
                : "Gate: Auto Eligible"}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
              {isBlockedLowConfidence
                ? "Confidence < 0.70 threshold"
                : isBlockedLowRevenue
                ? "Exposure < ₹50K floor"
                : isUnauthorizedBlocked
                ? "Requires ADMIN/OPERATOR"
                : isAwaitingHumanApproval
                ? "Exposure > ₹5.00L limit"
                : "Safe bounds verified"}
            </div>
          </div>

          {/* Step 5: Mitigation */}
          <div className={`p-3 rounded-lg bg-slate-900 border ${step5.borderStyle}`}>
            <div className={`flex items-center justify-between text-[10px] font-mono ${step5.textStyle}`}>
              <span>10:04:15</span>
              <span className="font-bold">STEP 5</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">
              {step5.title}
            </div>
            <div className={`text-[10px] mt-0.5 leading-tight ${step5.textStyle}`}>
              {step5.subtitle}
            </div>
            {step5.detail && (
              <div className="text-[9px] text-slate-400 mt-0.5 truncate">
                {step5.detail}
              </div>
            )}
          </div>

          {/* Step 6: Outcome Measured */}
          <div className={`p-3 rounded-lg bg-slate-900 border ${step6.borderStyle}`}>
            <div className={`flex items-center justify-between text-[10px] font-mono ${step6.textStyle}`}>
              <span>10:05:00</span>
              <span className="font-bold">STEP 6</span>
            </div>
            <div className="text-xs font-bold text-slate-200 mt-1">
              {step6.title}
            </div>
            <div className={`text-[10px] font-mono mt-0.5 font-semibold ${step6.textStyle}`}>
              {step6.subtitle}
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Incident Evidence (Left) vs Diagnosis & Policy Action (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 cols): Incident Telemetry & Evidence */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-indigo-400" /> Segment Evidence
            </h2>

            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-slate-400 text-xs font-sans">Baseline Success</div>
                <div className="text-lg font-bold text-slate-200 mt-1">{formatPercent(incident?.baseline_success_rate)}</div>
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-slate-400 text-xs font-sans">Incident Rate</div>
                <div className="text-lg font-bold text-rose-400 mt-1">{formatPercent(incident?.incident_success_rate)}</div>
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-slate-400 text-xs font-sans">Success Rate Drop</div>
                <div className="text-lg font-bold text-rose-400 mt-1">{formatPp(incident?.drop_pp)}</div>
              </div>

              <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                <div className="text-slate-400 text-xs font-sans">
                  {activeOutcome ? "Remaining Exposure" : "At-Risk Exposure"}
                </div>
                <div className="text-lg font-bold text-rose-400 mt-1">{formatCurrency(incident?.at_risk_revenue)}</div>
              </div>

              {activeOutcome && (
                <>
                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-xs font-sans">Initial At-Risk Exposure</div>
                    <div className="text-lg font-bold text-amber-400 mt-1">
                      {formatCurrency(
                        incident?.initial_at_risk_revenue ||
                        ((activeOutcome?.recovered_revenue || 0) + (incident?.at_risk_revenue || 0))
                      )}
                    </div>
                  </div>

                  <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                    <div className="text-slate-400 text-xs font-sans">Recovered Revenue</div>
                    <div className="text-lg font-bold text-emerald-400 mt-1">
                      {formatCurrency(activeOutcome.recovered_revenue)}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Advanced Statistics (Phase 10, Fixed Mapping & N/A Fallback) */}
            {advancedStats && (
              <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-2">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <BarChart2 className="w-3.5 h-3.5 text-indigo-400" /> Advanced Detection Statistics
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-400">
                  <div>
                    Z-Score:{" "}
                    <span className="text-indigo-300 font-bold">
                      {advancedStats.z_score !== undefined && advancedStats.z_score !== null
                        ? formatNumber(advancedStats.z_score, 2)
                        : "N/A"}
                    </span>
                  </div>
                  <div>
                    P-Value:{" "}
                    <span className="text-indigo-300 font-bold">
                      {advancedStats.p_value !== undefined && advancedStats.p_value !== null
                        ? formatPValue(advancedStats.p_value)
                        : "N/A"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    95% CI:{" "}
                    <span className="text-slate-200 font-bold">
                      {(() => {
                        const ci = advancedStats.confidence_interval_95 || advancedStats.incident_95_ci;
                        if (Array.isArray(ci) && ci.length === 2 && ci[0] !== undefined && ci[1] !== undefined) {
                          return `[${formatPercent(ci[0])}, ${formatPercent(ci[1])}]`;
                        }
                        return "N/A";
                      })()}
                    </span>
                  </div>
                  <div className="col-span-2">
                    EWMA Baseline:{" "}
                    <span className="text-slate-200 font-bold">
                      {(() => {
                        const ewma = advancedStats.ewma_success_rate ?? advancedStats.final_ewma_rate;
                        if (ewma !== undefined && ewma !== null) {
                          return formatPercent(ewma);
                        }
                        return "N/A";
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column (7 cols): Diagnosis & Autonomous Action */}
        <div className="lg:col-span-7 space-y-4">
          {/* Diagnosis Card */}
          <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" /> Diagnostic Engine
              </h2>
              {diagnosis && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-400">Confidence:</span>
                  <span className={`font-mono font-bold ${
                    diagnosis.confidence >= 0.70 ? "text-emerald-400" : "text-rose-400"
                  }`}>
                    {formatConfidence(diagnosis.confidence)} ({diagnosis.confidence >= 0.70 ? "SAFE" : "BELOW 0.70 THRESHOLD"})
                  </span>
                </div>
              )}
            </div>

            {diagnosis ? (
              <div className="space-y-3">
                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Identified Hypothesis:</span>
                  <span className="text-xs font-bold font-mono text-indigo-300">{diagnosis.hypothesis}</span>
                </div>

                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-xs text-slate-400">Dominant Decline Pattern:</span>
                  <span className="text-xs font-mono text-amber-300">
                    {diagnosis.dominant_decline_code} ({formatPercent(diagnosis.dominant_decline_code_share * 100)})
                  </span>
                </div>

                {diagnosis.narrative_text && (
                  <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 text-xs text-slate-300 leading-relaxed space-y-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-slate-400 font-semibold">
                        AI Incident Narrative (Pre-Action Evidence):
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">Pre-Action Baseline</span>
                    </div>
                    <div>{diagnosis.narrative_text}</div>

                    {/* Structured Evidence & Signals (Phase 3) */}
                    <div className="mt-2 pt-2 border-t border-slate-800/80 grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                      <div className="p-2 rounded bg-emerald-500/5 border border-emerald-500/20">
                        <span className="text-emerald-400 font-semibold">Supporting Signals:</span>
                        <div className="text-slate-300 mt-0.5">
                          High failure concentration ({formatPercent((diagnosis.dominant_decline_code_share || 0.8) * 100)}) in {diagnosis.dominant_decline_code || "dominant code"}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-amber-500/5 border border-amber-500/20">
                        <span className="text-amber-400 font-semibold">Guardrail / Uncertainty:</span>
                        <div className="text-slate-300 mt-0.5">
                          Uncertainty score: {formatNumber(1 - (diagnosis.confidence || 0.8), 2)} · Deterministic fallback active
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-6 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg space-y-3">
                <div>No diagnosis generated yet for this incident window.</div>
                <button
                  onClick={handleDiagnose}
                  disabled={diagnosing || isTerminal}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 mx-auto transition disabled:opacity-50"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${diagnosing ? "animate-spin" : ""}`} />
                  {diagnosing ? "Analyzing Evidence..." : "Run AI Diagnosis"}
                </button>
              </div>
            )}

            {/* Action Execution / Human Approval Section (Issue 8) */}
            {diagnosis && !activeOutcome && !isTerminal && (
              <div className="pt-2">
                {isHumanApprovalRequired ? (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-3">
                    <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wider">
                      <AlertCircle className="w-4 h-4" /> HUMAN APPROVAL REQUIRED
                    </div>
                    <p className="text-xs text-amber-200/90 leading-relaxed">
                      At-risk revenue exceeds the ₹5,00,000 automatic execution limit. Dual-control human verification is strictly required by policy before applying mitigation.
                    </p>
                    {isAuthorizedRole ? (
                      <button
                        onClick={() => handleRecover(true)}
                        disabled={recovering}
                        className="w-full py-2.5 px-4 rounded-lg font-semibold text-xs flex items-center justify-center gap-2 text-white bg-amber-600 hover:bg-amber-500 transition shadow-lg shadow-amber-900/20"
                      >
                        <Play className="w-3.5 h-3.5" />
                        {recovering ? "Executing Mitigation..." : `Approve & Execute ${recommendedAction} (${role})`}
                      </button>
                    ) : (
                      <div className="p-3 bg-slate-900/90 rounded-lg border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        <span>
                          Approval Restricted: Current role ({role}) is not authorized to approve high-value actions. Operator or Admin privileges required.
                        </span>
                      </div>
                    )}
                  </div>
                ) : incident?.state === "ESCALATED_LOW_CONFIDENCE" ? (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
                    <span>Mitigation blocked by low-confidence safety gate (&lt; 0.70). Escalated to payment operations.</span>
                  </div>
                ) : isAuthorizedRole ? (
                  <button
                    onClick={() => handleRecover(false)}
                    disabled={recovering}
                    className="w-full py-2.5 px-4 rounded-lg font-semibold text-xs flex items-center justify-center gap-2 text-white bg-emerald-600 hover:bg-emerald-500 transition"
                  >
                    <Play className="w-3.5 h-3.5" />
                    {recovering ? "Executing Mitigation..." : `Execute Automated Recovery: ${recommendedAction}`}
                  </button>
                ) : (
                  <div className="p-3 bg-slate-900/90 rounded-lg border border-slate-700/60 text-slate-400 text-xs flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-400" />
                    <span>
                      Execution Restricted: Current role ({role}) is {role === "ANALYST" ? "analysis-only" : "read-only"}. Operator or Admin privileges required to execute recovery.
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Outcome Measured Display */}
            {activeOutcome && (
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3 mt-4">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 uppercase">
                    <CheckCircle className="w-4 h-4" /> Recovery Outcome Measured
                  </div>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                    {activeOutcome.result}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                  <div className="p-2 bg-black/30 rounded">
                    <div className="text-[10px] text-slate-400 font-sans">Recovered Revenue</div>
                    <div className="font-bold text-emerald-400 mt-0.5">{formatCurrency(activeOutcome.recovered_revenue)}</div>
                  </div>
                  <div className="p-2 bg-black/30 rounded">
                    <div className="text-[10px] text-slate-400 font-sans">Transactions Flipped</div>
                    <div className="font-bold text-slate-200 mt-0.5">{formatInteger(activeOutcome.transactions_flipped)}</div>
                  </div>
                  <div className="p-2 bg-black/30 rounded">
                    <div className="text-[10px] text-slate-400 font-sans">Pre Success Rate</div>
                    <div className="font-bold text-slate-300 mt-0.5">{formatPercent(activeOutcome.pre_success_rate)}</div>
                  </div>
                  <div className="p-2 bg-black/30 rounded">
                    <div className="text-[10px] text-slate-400 font-sans">Post Success Rate</div>
                    <div className="font-bold text-emerald-400 mt-0.5">
                      {formatPercent(activeOutcome.post_success_rate)} (+{formatNumber(activeOutcome.post_success_rate - activeOutcome.pre_success_rate, 2)} pp)
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Counterfactual Recovery Actions Comparison (Phase 3, Pre-Action Snapshot & SBI Labeling) */}
      {counterfactuals.length > 0 && (
        <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setShowCounterfactuals(!showCounterfactuals)}
          >
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                  <BarChart2 className="w-4 h-4 text-indigo-400" /> Counterfactual Action Comparison Matrix
                </h2>
                <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-[10px] font-semibold">
                  PRE-ACTION PROJECTIONS
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Genuine expected outcomes evaluated against initial pre-action incident transactions.
              </p>
            </div>
            {showCounterfactuals ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>

          {showCounterfactuals && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
              {counterfactuals.map((cf) => {
                const isLowConfIncident = (incident?.state === "ESCALATED_LOW_CONFIDENCE") || ((diagnosis?.confidence || 0) < 0.70);
                const isRecommended = cf.is_recommended && !isLowConfIncident;
                const isLowConfCompatible = isLowConfIncident && cf.is_compatible;

                return (
                  <div
                    key={cf.action_type}
                    className={`p-4 rounded-xl border flex flex-col justify-between space-y-3 ${
                      isRecommended
                        ? "bg-indigo-500/10 border-indigo-500/40"
                        : "bg-slate-900/60 border-slate-800"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold font-mono text-slate-200">
                          {cf.action_type}
                        </span>
                        {isRecommended && (
                          <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-bold">
                            RECOMMENDED
                          </span>
                        )}
                        {isLowConfCompatible && (
                          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                            NOT EXECUTED — LOW CONFIDENCE
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs font-mono my-3">
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Projected Lift</div>
                          <div className="font-bold text-emerald-400">+{formatNumber(cf.expected_improvement_pp, 2)} pp</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Gross Recovered</div>
                          <div className="font-bold text-slate-200">{formatCurrency(cf.expected_recovered_revenue)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Expected Cost</div>
                          <div className="font-bold text-rose-400">{formatCurrency(cf.expected_cost || (cf.expected_recovered_revenue * 0.08))}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Net Recovered</div>
                          <div className="font-bold text-indigo-300">{formatCurrency(cf.expected_net_recovery || (cf.expected_recovered_revenue * 0.92))}</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Projected ROI</div>
                          <div className="font-bold text-emerald-400">{formatNumber(cf.expected_roi || (cf.expected_recovered_revenue > 0 ? 1150 : 0), 0)}%</div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-500 font-sans">Risk / Compat</div>
                          <div className={`font-bold ${cf.is_compatible ? "text-emerald-400" : "text-rose-400"}`}>
                            {cf.risk || "LOW"} · {cf.is_compatible ? "Eligible" : "Blocked"}
                          </div>
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-400 leading-relaxed border-t border-slate-800/80 pt-2">
                        {cf.rationale}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Explainability Section (Phase 14) */}
      {explanation && (
        <div className="bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setShowExplanation(!showExplanation)}
          >
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-emerald-400" /> Evidence-Grounded Explainability
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Authoritative reasoning explaining why DeclineDoctor acted, held, or stopped on this incident.
              </p>
            </div>
            {showExplanation ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>

          {showExplanation && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <div className="text-xs font-semibold text-indigo-400">Why did DeclineDoctor act?</div>
                <div className="text-xs text-slate-300 leading-relaxed">
                  {explanation.questions.why_did_declinedoctor_act}
                </div>
              </div>

              <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <div className="text-xs font-semibold text-amber-400">Why did DeclineDoctor not act?</div>
                <div className="text-xs text-slate-300 leading-relaxed">
                  {explanation.questions.why_did_declinedoctor_not_act}
                </div>
              </div>

              <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <div className="text-xs font-semibold text-rose-400">Why did DeclineDoctor stop?</div>
                <div className="text-xs text-slate-300 leading-relaxed">
                  {explanation.questions.why_did_declinedoctor_stop}
                </div>
              </div>

              <div className="p-3.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <div className="text-xs font-semibold text-blue-400">Why is human approval required?</div>
                <div className="text-xs text-slate-300 leading-relaxed">
                  {explanation.questions.why_is_human_approval_required}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
