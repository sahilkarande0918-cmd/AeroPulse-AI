import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { api } from '../api'
import { ErrorState, Loading, PageHeader, Panel, Stat, Table, Tag, fmt } from '../ui'

type M = { mae: number; rmse: number; bias: number; phm08_score: number; n: number }
interface Report {
  model_version: string; selected_model: string; trained_at_utc: string; training_seconds: number
  config: { rul_cap: number; alpha: number; cv_folds: number; split: Record<string, number>; seed: number }
  provenance: { dataset: string; source_url: string; archive_sha256: string; note: string }
  environment: Record<string, string>; sensors_used: string[]; sensors_dropped: string[]; n_features: number; n_fit_rows: number
  cv: Record<string, M>
  test: { protocol: string; selected_model: M; selected_model_vs_capped_truth: M; ridge_baseline: M; mean_baseline: M
          interval_coverage_capped_truth: number; interval_coverage_raw_truth: number; mean_interval_width: number }
  holdout: { protocol: string; selected_model: M; selected_model_rul_le_50: M; interval_coverage: number; interval_coverage_rul_le_50: number }
  conformal: { method: string; alpha: number; bin_edges: number[]; quantiles: number[]; bin_counts: number[]; n_calibration_rows: number }
  shap: { method: string; max_abs_diff_shap_vs_pred_contrib: number; mean_abs_shap: { feature: string; value: number }[] }
  test_predictions: { unit: number; true_rul: number; pred: number; lo: number; hi: number; ridge: number }[]
}
interface Drift { method: string; sensors: { sensor: string; symbol: string; n: number; train_mean: number; fleet_mean: number; std_shift: number; out_of_range_share: number; flag: boolean }[] }

function histogram(errors: number[], width = 10) {
  const bins = new Map<number, number>()
  for (const e of errors) { const b = Math.floor(e / width) * width; bins.set(b, (bins.get(b) ?? 0) + 1) }
  return [...bins.entries()].sort((a, b) => a[0] - b[0]).map(([b, n]) => ({ bin: `${b}…${b + width}`, n }))
}

export default function Intelligence() {
  const q = useQuery({ queryKey: ['model'], queryFn: () => api.get<{ report: Report }>('/model') })
  const drift = useQuery({ queryKey: ['drift'], queryFn: () => api.get<Drift>('/model/drift') })
  if (q.isPending) return <Loading />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
  const r = q.data.report
  const t = r.test
  const preds = r.test_predictions
  const errHist = histogram(preds.map((p) => p.pred - p.true_rul))
  const shapTop = r.shap.mean_abs_shap.slice(0, 12).map((s) => ({ ...s, value: +s.value.toFixed(2) }))
  const rows: [string, M][] = [['LightGBM (selected)', t.selected_model], ['Ridge regression baseline', t.ridge_baseline], ['Mean-RUL baseline', t.mean_baseline]]

  return (
    <>
      <PageHeader title="Predictive intelligence" subtitle={`All figures computed by ml/train.py on the official NASA C-MAPSS FD001 data and stored in ml/artifacts/evaluation_report.json. Model ${r.model_version}.`} />
      <div className="mb-5 grid grid-cols-2 gap-4 rounded-md border border-line bg-surface p-4 md:grid-cols-5">
        <Stat label="Test RMSE (100 engines)" value={fmt(t.selected_model.rmse, 2)} unit="cycles" />
        <Stat label="Test MAE" value={fmt(t.selected_model.mae, 2)} unit="cycles" />
        <Stat label="Ridge baseline RMSE" value={fmt(t.ridge_baseline.rmse, 2)} unit="cycles" tone="warn" />
        <Stat label="90% interval coverage (test)" value={`${fmt(t.interval_coverage_capped_truth * 100, 0)}%`} tone="ok" note={`vs RUL capped at ${r.config.rul_cap}; ${fmt(t.interval_coverage_raw_truth * 100, 0)}% vs raw truth`} />
        <Stat label="Hold-out coverage (20 engines)" value={`${fmt(r.holdout.interval_coverage * 100, 1)}%`} tone="ok" note={`${fmt(r.holdout.interval_coverage_rul_le_50 * 100, 1)}% when RUL ≤ 50`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Baseline vs trained model — official test set" meta={t.protocol}>
          <Table head={['Model', 'RMSE', 'MAE', 'Bias (+ late)', 'PHM08 score']}>
            {rows.map(([n, m]) => (
              <tr key={n}><td>{n}</td><td className="num">{fmt(m.rmse, 2)}</td><td className="num">{fmt(m.mae, 2)}</td><td className="num">{fmt(m.bias, 2)}</td><td className="num">{fmt(m.phm08_score, 0)}</td></tr>
            ))}
          </Table>
          <div className="mt-4 text-xs font-medium text-muted">Model selection — engine-grouped {r.config.cv_folds}-fold CV on {r.config.split.fit} fit engines (capped target)</div>
          <Table head={['Candidate', 'CV RMSE', 'CV MAE']} dense>
            {Object.entries(r.cv).map(([k, m]) => (
              <tr key={k}><td>{k} {k === r.selected_model && <Tag tone="ok">selected</Tag>}</td><td className="num">{fmt(m.rmse, 2)}</td><td className="num">{fmt(m.mae, 2)}</td></tr>
            ))}
          </Table>
        </Panel>

        <Panel title="Predicted vs true RUL — 100 test engines" meta="diagonal = perfect prediction">
          <div className="h-72">
            <ResponsiveContainer>
              <ScatterChart margin={{ left: 0, right: 12, top: 6, bottom: 16 }}>
                <CartesianGrid strokeDasharray="2 4" />
                <XAxis type="number" dataKey="true_rul" name="true RUL" domain={[0, 160]} label={{ value: 'true RUL (cycles)', position: 'insideBottom', offset: -8 }} />
                <YAxis type="number" dataKey="pred" name="predicted" domain={[0, 160]} width={44} label={{ value: 'predicted (cycles)', angle: -90, position: 'insideLeft', offset: 10 }} />
                <ZAxis range={[24, 24]} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 160, y: 160 }]} stroke="var(--color-muted)" strokeDasharray="4 4" />
                <Tooltip cursor={false} formatter={(v: number) => v.toFixed(1)} />
                <Scatter data={preds} fill="var(--color-tech)" isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-muted">Points above ~125 true RUL are under-predicted by design: the training target is capped at {r.config.rul_cap} cycles.</p>
        </Panel>

        <Panel title="Prediction error distribution (test)" meta="predicted − true, cycles">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={errHist} margin={{ left: 0, right: 12, top: 6, bottom: 16 }}>
                <CartesianGrid strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="bin" label={{ value: 'error bin (cycles; positive = late/optimistic)', position: 'insideBottom', offset: -8 }} />
                <YAxis allowDecimals={false} width={32} label={{ value: 'engines', angle: -90, position: 'insideLeft', offset: 12 }} />
                <Tooltip />
                <Bar dataKey="n" fill="var(--color-tech)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Global feature importance — mean |SHAP|" meta="cycles of RUL">
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={shapTop} layout="vertical" margin={{ left: 10, right: 12, top: 4, bottom: 14 }}>
                <CartesianGrid strokeDasharray="2 4" horizontal={false} />
                <XAxis type="number" label={{ value: 'mean |SHAP| (cycles)', position: 'insideBottom', offset: -6 }} />
                <YAxis type="category" dataKey="feature" width={100} />
                <Tooltip />
                <Bar dataKey="value" fill="var(--color-ok)" isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-muted">{r.shap.method}. Max |SHAP − pred_contrib| = {r.shap.max_abs_diff_shap_vs_pred_contrib}.</p>
        </Panel>

        <Panel title="Uncertainty calibration" meta={r.conformal.method}>
          <Table head={['Predicted-RUL bin', 'Calibration rows', `${(1 - r.conformal.alpha) * 100}% half-width (cycles)`]}>
            {r.conformal.quantiles.map((qv, i) => (
              <tr key={i}><td className="num">{r.conformal.bin_edges[i]}–{r.conformal.bin_edges[i + 1] > 1e6 ? '∞' : r.conformal.bin_edges[i + 1]}</td>
                <td className="num">{r.conformal.bin_counts[i]}</td><td className="num">±{fmt(qv, 1)}</td></tr>
            ))}
          </Table>
          <p className="mt-3 text-xs text-muted">
            Calibrated on {r.conformal.n_calibration_rows} rows from 15 engines never used for fitting. Coverage is measured, not assumed: {fmt(t.interval_coverage_capped_truth * 100)}% on the test set,
            {' '}{fmt(r.holdout.interval_coverage * 100, 1)}% on hold-out engines. Limitation: rows within one engine are correlated, so exchangeability is approximate, and
            coverage is not guaranteed when TrustTwin marks inputs DEGRADED.
          </p>
        </Panel>

        <Panel title="Training & evaluation protocol">
          <ul className="list-disc space-y-1.5 pl-4 text-[13px] text-muted">
            <li>100 training engines split by engine: {r.config.split.fit} fit · {r.config.split.calibration} calibration · {r.config.split.holdout} hold-out (seed {r.config.seed}). No engine in two splits.</li>
            <li>Features are causal: rolling mean/std (10 cycles) and slope (20 cycles) per sensor using only past readings; {r.n_features} features from {r.sensors_used.length} sensors.</li>
            <li>Dropped as constant/low-information on fit engines: {r.sensors_dropped.join(', ')}.</li>
            <li>Target: RUL capped at {r.config.rul_cap} cycles. Final test: last observed cycle of each official test engine vs RUL_FD001.</li>
            <li>{r.holdout.protocol} RMSE {fmt(r.holdout.selected_model.rmse, 2)}; RMSE {fmt(r.holdout.selected_model_rul_le_50.rmse, 2)} when true RUL ≤ 50.</li>
          </ul>
          <div className="mt-4 border-t border-line pt-3 text-xs text-muted">
            <div className="text-ink">Provenance</div>
            <div>{r.provenance.dataset}</div>
            <div className="break-all"><span className="num">{r.provenance.source_url}</span></div>
            <div className="num break-all">sha256 {r.provenance.archive_sha256}</div>
            <div className="mt-1 text-warn">{r.provenance.note}</div>
            <div className="num mt-1">trained {r.trained_at_utc} in {r.training_seconds}s · python {r.environment.python} · lightgbm {r.environment.lightgbm} · {r.n_fit_rows} fit rows</div>
          </div>
        </Panel>

        <Panel title="Monitoring — fleet sensor drift vs training data" className="lg:col-span-2" meta={drift.data?.method}>
          {drift.isPending ? <Loading /> : drift.isError ? <ErrorState error={drift.error} /> : (
            <Table head={['Sensor', 'Readings', 'Training mean', 'Fleet mean', 'Shift (σ)', 'Outside training range', 'Flag']} dense>
              {drift.data.sensors.map((s) => (
                <tr key={s.sensor}>
                  <td className="num">{s.sensor} · {s.symbol}</td><td className="num">{s.n}</td><td className="num">{fmt(s.train_mean, 3)}</td>
                  <td className="num">{fmt(s.fleet_mean, 3)}</td><td className="num">{fmt(s.std_shift, 2)}</td><td className="num">{fmt(s.out_of_range_share * 100, 1)}%</td>
                  <td>{s.flag ? <Tag tone="warn">review</Tag> : <Tag tone="ok">ok</Tag>}</td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>
      </div>
    </>
  )
}
