"use client";

import {
  useAlertRules,
  useCreateAlertRule,
  useDeleteAlertRule,
  useUpdateAlertRule,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AlertOperator, AlertSeverity, MetricType, RuleKind } from "@/lib/types";

const METRIC_TYPES: MetricType[] = ["CPU_USAGE", "MEMORY_USAGE", "DISK_USAGE", "PACKET_LOSS", "RESPONSE_TIME", "TEMPERATURE"];
const OPERATORS: AlertOperator[] = ["GT", "GTE", "LT", "LTE", "EQ"];
const RULE_KINDS: RuleKind[] = ["METRIC_THRESHOLD", "DEVICE_UNREACHABLE", "INTERFACE_DOWN"];
const SEVERITIES: AlertSeverity[] = ["WARNING", "CRITICAL"];

export default function AlertRulesPage() {
  const { isConfigWriter, loading } = useAuth();
  const { data: rules } = useAlertRules();
  const createRule = useCreateAlertRule();
  const updateRule = useUpdateAlertRule();
  const deleteRule = useDeleteAlertRule();

  if (!loading && !isConfigWriter) {
    return <div className="card text-gray-400">Access denied -- ADMIN or NETWORK_ENGINEER only.</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Alert Rules</h1>

      <form
        className="card flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          const ruleKind = form.get("rule_kind") as RuleKind;
          createRule.mutate({
            name: String(form.get("name")),
            rule_kind: ruleKind,
            metric_type: ruleKind === "METRIC_THRESHOLD" ? (form.get("metric_type") as MetricType) : undefined,
            operator: ruleKind === "METRIC_THRESHOLD" ? (form.get("operator") as AlertOperator) : undefined,
            threshold: ruleKind === "METRIC_THRESHOLD" ? Number(form.get("threshold")) : undefined,
            severity: form.get("severity") as AlertSeverity,
          });
          e.currentTarget.reset();
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Name
          <input name="name" required className="input" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Kind
          <select name="rule_kind" className="input">
            {RULE_KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Metric
          <select name="metric_type" className="input">
            {METRIC_TYPES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Operator
          <select name="operator" className="input">
            {OPERATORS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Threshold
          <input name="threshold" type="number" className="input w-24" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Severity
          <select name="severity" className="input">
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={createRule.isPending}>
          Add rule
        </button>
      </form>

      <div className="card overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>Name</th>
              <th>Kind</th>
              <th>Condition</th>
              <th>Severity</th>
              <th>Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rules?.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="text-xs">{r.rule_kind}</td>
                <td className="text-xs">
                  {r.rule_kind === "METRIC_THRESHOLD" ? `${r.metric_type} ${r.operator} ${r.threshold}` : "-"}
                </td>
                <td>{r.severity}</td>
                <td>
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) => updateRule.mutate({ id: r.id, payload: { enabled: e.target.checked } })}
                  />
                </td>
                <td>
                  <button className="btn-danger" onClick={() => deleteRule.mutate(r.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!rules?.length && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-gray-500">
                  No alert rules yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
