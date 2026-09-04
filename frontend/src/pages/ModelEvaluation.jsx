import { useState, useEffect } from "react";
import { ShieldCheck, Target, RefreshCw, BarChart2 } from "lucide-react";
import api from "../api";
import { formatPercent, formatInteger } from "../utils/format";

export default function ModelEvaluation() {
  const [evalData, setEvalData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchEvaluation = async () => {
    setLoading(true);
    try {
      const res = await api.get("/evaluation");
      setEvalData(res.data);
    } catch (err) {
      console.error("Failed to load evaluation benchmark", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    api.get("/evaluation")
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
  }, []);

  if (loading || !evalData) {
    return (
      <div className="text-center py-16 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
        Running diagnostic evaluation on 60 ground-truth payment scenarios...
      </div>
    );
  }

  const { metrics, confusion_matrix, per_class_performance, scenarios, dataset_size } = evalData;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Target className="text-emerald-400 w-7 h-7" /> Diagnostic Model Evaluation
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real benchmark calculated from {dataset_size} ground-truth payment failure test cases across multi-bank issuer rails.
          </p>
        </div>

        <button
          onClick={fetchEvaluation}
          className="self-start px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-2 transition"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Re-run Benchmark
        </button>
      </div>

      {/* Primary Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Accuracy</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-1">{formatPercent(metrics.accuracy)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">overall classification</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Precision</div>
          <div className="text-xl font-bold font-mono text-indigo-400 mt-1">{formatPercent(metrics.precision)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">anomaly detection</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">Recall</div>
          <div className="text-xl font-bold font-mono text-blue-400 mt-1">{formatPercent(metrics.recall)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">incident capture rate</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">F1 Score</div>
          <div className="text-xl font-bold font-mono text-purple-400 mt-1">{formatPercent(metrics.f1_score)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">harmonic mean</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">False Positive Rate</div>
          <div className="text-xl font-bold font-mono text-amber-400 mt-1">{formatPercent(metrics.false_positive_rate)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">safe bounded envelope</div>
        </div>

        <div className="bg-[#151822] border border-slate-800 p-4 rounded-xl">
          <div className="text-xs text-slate-400">False Negative Rate</div>
          <div className="text-xl font-bold font-mono text-rose-400 mt-1">{formatPercent(metrics.false_negative_rate)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">missed incidents</div>
        </div>
      </div>

      {/* Confusion Matrix & Per-Class Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Confusion Matrix (5 cols) */}
        <div className="lg:col-span-5 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" /> Confusion Matrix
          </h2>

          <div className="grid grid-cols-2 gap-3 font-mono text-center">
            <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <div className="text-xs text-slate-400 font-sans">True Positives (TP)</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">{confusion_matrix.true_positives}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">True anomalies caught</div>
            </div>

            <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400 font-sans">False Positives (FP)</div>
              <div className="text-2xl font-bold text-amber-400 mt-1">{confusion_matrix.false_positives}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">False alerts</div>
            </div>

            <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
              <div className="text-xs text-slate-400 font-sans">False Negatives (FN)</div>
              <div className="text-2xl font-bold text-rose-400 mt-1">{confusion_matrix.false_negatives}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">Missed anomalies</div>
            </div>

            <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
              <div className="text-xs text-slate-400 font-sans">True Negatives (TN)</div>
              <div className="text-2xl font-bold text-blue-400 mt-1">{confusion_matrix.true_negatives}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">Normal traffic validated</div>
            </div>
          </div>

          <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
            <span>Action Compatibility Matching:</span>
            <span className="font-bold text-emerald-400">{formatPercent(metrics.action_compatibility_accuracy)}</span>
          </div>
        </div>

        {/* Per-Class Breakdown (7 cols) */}
        <div className="lg:col-span-7 bg-[#151822] border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> Hypothesis Class Accuracy
          </h2>

          <div className="space-y-3">
            {Object.entries(per_class_performance).map(([cls, stat]) => (
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
            ))}
          </div>
        </div>
      </div>

      {/* Sample Evaluation Scenarios */}
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
    </div>
  );
}
