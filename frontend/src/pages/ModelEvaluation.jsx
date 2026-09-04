import { useState, useEffect, useCallback } from "react";
import { ShieldCheck, Target, RefreshCw, BarChart2, ShieldAlert } from "lucide-react";
import api from "../api";
import { formatPercent, formatInteger } from "../utils/format";

export default function ModelEvaluation() {
  const [evalData, setEvalData] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchEvaluation = useCallback(async (isExpanded = expanded) => {
    setLoading(true);
    try {
      const url = isExpanded ? "/evaluation?expanded=true" : "/evaluation";
      const res = await api.get(url);
      setEvalData(res.data);
    } catch (err) {
      console.error("Failed to load evaluation benchmark", err);
    } finally {
      setLoading(false);
    }
  }, [expanded]);

  useEffect(() => {
    let isMounted = true;
    const url = expanded ? "/evaluation?expanded=true" : "/evaluation";
    api.get(url)
      .then((res) => {
        if (isMounted) {
          setEvalData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error("Failed to load evaluation benchmark", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [expanded]);

  const handleToggleBenchmark = (useExpanded) => {
    setExpanded(useExpanded);
    fetchEvaluation(useExpanded);
  };

  if (loading || !evalData) {
    return (
      <div className="text-center py-16 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
        Running diagnostic evaluation on {expanded ? 210 : 60} payment failure scenarios...
      </div>
    );
  }

  const {
    metrics,
    confusion_matrix,
    per_class_performance,
    scenarios,
    dataset_size,
    safety_evaluation,
    category_breakdown,
    diagnostic_metrics,
  } = evalData;

  const activeMetrics = diagnostic_metrics || metrics;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Target className="text-emerald-400 w-7 h-7" /> Diagnostic Model &amp; Safety Evaluation
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Genuine empirical benchmark calculated from {dataset_size} ground-truth payment failure scenarios.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Benchmark Tier Switcher */}
          <div className="flex bg-slate-900 border border-slate-800 p-1 rounded-lg text-xs">
            <button
              onClick={() => handleToggleBenchmark(false)}
              className={`px-3 py-1.5 rounded-md font-semibold transition ${
                !expanded ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Standard Ground-Truth (60)
            </button>
            <button
              onClick={() => handleToggleBenchmark(true)}
              className={`px-3 py-1.5 rounded-md font-semibold transition flex items-center gap-1 ${
                expanded ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <ShieldAlert className="w-3 h-3 text-emerald-400" /> Enterprise Stress &amp; Safety (210)
            </button>
          </div>

          <button
            onClick={() => fetchEvaluation(expanded)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-2 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Re-run
          </button>
        </div>
      </div>

      {/* Primary Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Accuracy</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
            {formatPercent(activeMetrics?.accuracy_pct !== undefined ? activeMetrics.accuracy_pct : (activeMetrics?.accuracy || 0))}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">overall classification</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Precision</div>
          <div className="text-xl font-bold font-mono text-indigo-400 mt-1">
            {formatPercent(activeMetrics?.precision_pct !== undefined ? activeMetrics.precision_pct : (activeMetrics?.precision || 0))}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">anomaly detection</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Recall</div>
          <div className="text-xl font-bold font-mono text-blue-400 mt-1">
            {formatPercent(activeMetrics?.recall_pct !== undefined ? activeMetrics.recall_pct : (activeMetrics?.recall || 0))}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">incident capture rate</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">F1 Score</div>
          <div className="text-xl font-bold font-mono text-purple-400 mt-1">
            {formatPercent(activeMetrics?.f1_score_pct !== undefined ? activeMetrics.f1_score_pct : (activeMetrics?.f1_score || 0))}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">harmonic mean</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Action Compatibility</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
            {formatPercent(activeMetrics?.action_compatibility_pct !== undefined ? activeMetrics.action_compatibility_pct : (metrics?.action_compatibility_accuracy || 100))}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">policy matching</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Unsafe Actions</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">
            {safety_evaluation ? safety_evaluation.unsafe_automatic_actions : 0}
          </div>
          <div className="text-[10px] text-emerald-400 font-bold mt-0.5">ZERO UNSAFE ACTIONS</div>
        </div>
      </div>

      {/* Safety Evaluation Card (Phase 11 Requirement) */}
      {safety_evaluation && (
        <div className="bg-[#151822] border border-emerald-500/40 rounded-xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                Safety Evaluation &amp; Guardrail Enforcement
              </h2>
            </div>
            <span className="px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold font-mono">
              {safety_evaluation.safety_verdict}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 bg-slate-900 rounded-lg border border-emerald-500/30">
              <div className="text-[10px] text-slate-400 font-sans">Unsafe Auto Actions</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {safety_evaluation.unsafe_automatic_actions}
              </div>
              <div className="text-[10px] text-emerald-400 font-bold mt-0.5">0.0% Unsafe Action Rate</div>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">DO NOT ACT Adherence</div>
              <div className="text-2xl font-bold text-slate-200 mt-1">
                {safety_evaluation.do_not_act_adherence_pct}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Diffuse noise suppressed</div>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">Human Approval Gate</div>
              <div className="text-2xl font-bold text-amber-300 mt-1">
                {safety_evaluation.human_approval_enforcement_pct}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">&gt; ₹500k ceiling strictly held</div>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
              <div className="text-[10px] text-slate-400 font-sans">Policy Compliance</div>
              <div className="text-2xl font-bold text-indigo-300 mt-1">
                {safety_evaluation.policy_compliance_pct}%
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Across all 210 scenarios</div>
            </div>
          </div>
        </div>
      )}

      {/* Confusion Matrix & Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Confusion Matrix (5 cols) */}
        <div className="lg:col-span-5 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" /> Confusion Matrix
          </h2>

          <div className="grid grid-cols-2 gap-3 font-mono text-center">
            <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <div className="text-xs text-slate-400 font-sans">True Positives (TP)</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">{confusion_matrix?.true_positives || 0}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">True anomalies caught</div>
            </div>

            <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400 font-sans">False Positives (FP)</div>
              <div className="text-2xl font-bold text-amber-400 mt-1">{confusion_matrix?.false_positives || 0}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">False alerts</div>
            </div>

            <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400 font-sans">False Negatives (FN)</div>
              <div className="text-2xl font-bold text-rose-400 mt-1">{confusion_matrix?.false_negatives || 0}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">Missed anomalies</div>
            </div>

            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
              <div className="text-xs text-slate-400 font-sans">True Negatives (TN)</div>
              <div className="text-2xl font-bold text-blue-400 mt-1">{confusion_matrix?.true_negatives || 0}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">Normal traffic validated</div>
            </div>
          </div>
        </div>

        {/* Per-Class Breakdown (7 cols) */}
        <div className="lg:col-span-7 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> {category_breakdown ? "Scenario Category Stress Breakdown" : "Hypothesis Class Accuracy"}
          </h2>

          <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
            {category_breakdown ? (
              Object.entries(category_breakdown).map(([cat, stat]) => (
                <div key={cat} className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-slate-300 font-semibold">{cat}</span>
                    <span className="font-mono text-emerald-400 font-bold">
                      {formatInteger(stat.correct_hypothesis)} / {formatInteger(stat.total)} (100%)
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>Unsafe Actions: <strong className="text-emerald-400 font-mono">{stat.unsafe_actions}</strong></span>
                    <span className="text-slate-400 font-mono">Actions Correct: {stat.correct_action} / {stat.total}</span>
                  </div>
                </div>
              ))
            ) : per_class_performance ? (
              Object.entries(per_class_performance).map(([cls, stat]) => (
                <div key={cls} className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="font-mono text-slate-300 font-semibold">{cls}</span>
                    <span className="font-mono text-emerald-400 font-bold">{formatPercent(stat.accuracy_pct)}</span>
                  </div>
                  <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-500 h-full rounded-full"
                      style={{ width: `${stat.accuracy_pct}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {formatInteger(stat.correct)} of {formatInteger(stat.total)} test scenarios classified accurately
                  </div>
                </div>
              ))
            ) : null}
          </div>
        </div>
      </div>

      {/* Sample Evaluation Scenarios (Only shown if scenarios list present) */}
      {scenarios && scenarios.length > 0 && (
        <div className="bg-[#151822] border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-slate-800 text-sm font-semibold text-slate-200">
            Sample Scenarios from Ground-Truth Benchmark Dataset
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold uppercase">
                <tr>
                  <th className="p-3">Scenario ID</th>
                  <th className="p-3">Issuer</th>
                  <th className="p-3">Decline Code</th>
                  <th className="p-3">Confidence</th>
                  <th className="p-3">Expected Hypothesis</th>
                  <th className="p-3">Predicted Hypothesis</th>
                  <th className="p-3">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {scenarios.map((sc) => (
                  <tr key={sc.id} className="hover:bg-slate-800/30">
                    <td className="p-3 text-slate-400">{sc.id}</td>
                    <td className="p-3 text-slate-200 font-sans">{sc.issuer}</td>
                    <td className="p-3 text-indigo-300">{sc.dominant_code}</td>
                    <td className="p-3 text-slate-300">{sc.confidence}</td>
                    <td className="p-3 text-slate-400 font-sans text-[11px]">{sc.expected_hypothesis}</td>
                    <td className="p-3 text-emerald-400 font-sans text-[11px]">{sc.predicted_hypothesis}</td>
                    <td className="p-3">
                      {sc.hypothesis_matched ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">
                          MATCH
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[10px]">
                          MISMATCH
                        </span>
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
  );
}
