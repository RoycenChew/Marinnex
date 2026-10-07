import { useMemo, useState } from 'react'
import { useMutation, useQueries, useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Coins, Download, FileSpreadsheet, FileText, Layers } from 'lucide-react'
import { toast } from 'sonner'
import { createExport, exportDownloadUrl, getUsage } from '../api/queries'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../lib/theme'
import { Page } from '../components/layout/AppLayout'
import { Button } from '../components/ui/Button'
import { Card, CardHeader, StatCard } from '../components/ui/Card'
import {
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  TableShell,
} from '../components/ui/Table'
import { formatCost } from '../lib/format'
import { problemMessage } from '../lib/status'

/** The last six months, newest last, as `YYYY-MM`. */
function recentMonths(count = 6): string[] {
  const out: string[] = []
  const now = new Date()
  for (let i = count - 1; i >= 0; i -= 1) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
    out.push(
      `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`,
    )
  }
  return out
}

const MONTH_LABEL = (month: string) => {
  const [year, m] = month.split('-')
  return `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][Number(m) - 1]} ${year.slice(2)}`
}

export default function ExportsUsage() {
  const { activeProjectId } = useAuth()
  const { resolved } = useTheme()
  const months = useMemo(() => recentMonths(6), [])
  const [month, setMonth] = useState(months[months.length - 1])
  const [format, setFormat] = useState<'csv' | 'xlsx'>('xlsx')

  /*
   * There is no usage-history endpoint, so the trend is six separate calls for
   * six months. Cheap (the responses are four numbers each) and honest: the
   * chart shows exactly what the API can answer.
   */
  const history = useQueries({
    queries: months.map((m) => ({
      queryKey: ['usage', activeProjectId, m],
      queryFn: () => getUsage(m, activeProjectId),
      staleTime: 60_000,
    })),
  })

  const current = useQuery({
    queryKey: ['usage', activeProjectId, month],
    queryFn: () => getUsage(month, activeProjectId),
  })

  const exportMutation = useMutation({
    mutationFn: () => createExport({ format }, activeProjectId),
    onSuccess: (job) => {
      toast.success(`Export ready — ${job.row_count} rows`, {
        description: 'The download should start automatically.',
        action: {
          label: 'Download',
          onClick: () =>
            window.open(exportDownloadUrl(job.export_id, activeProjectId), '_blank'),
        },
      })
      window.open(exportDownloadUrl(job.export_id, activeProjectId), '_blank')
    },
    onError: (error) =>
      toast.error('Export failed', { description: problemMessage(error) }),
  })

  const chartData = months.map((m, index) => ({
    month: MONTH_LABEL(m),
    key: m,
    documents: history[index]?.data?.documents ?? 0,
    pages: history[index]?.data?.pages ?? 0,
    cost: history[index]?.data?.ai_cost_usd ?? 0,
  }))

  const usage = current.data
  const axis = resolved === 'dark' ? '#64748b' : '#94a3b8'
  const grid = resolved === 'dark' ? '#1e293b' : '#e2e8f0'
  const bar = resolved === 'dark' ? '#6366f1' : '#4f46e5'

  return (
    <Page
      title="Usage & exports"
      description="What this project has processed, and how to get the data out."
      action={
        <select
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          aria-label="Month"
          className="h-8 rounded-[var(--radius-sm)] border bg-[var(--surface-raised)] px-2 text-sm text-[var(--text-primary)]"
        >
          {[...months].reverse().map((m) => (
            <option key={m} value={m}>
              {MONTH_LABEL(m)}
            </option>
          ))}
        </select>
      }
    >
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <StatCard
          label="Documents"
          value={usage?.documents ?? 0}
          hint={MONTH_LABEL(month)}
          icon={<FileText className="h-4 w-4" />}
          loading={current.isLoading}
        />
        <StatCard
          label="Pages"
          value={usage?.pages ?? 0}
          hint="Counted at extraction"
          icon={<Layers className="h-4 w-4" />}
          loading={current.isLoading}
        />
        <StatCard
          label="AI cost"
          value={formatCost(usage?.ai_cost_usd)}
          hint="Charged by the provider"
          icon={<Coins className="h-4 w-4" />}
          loading={current.isLoading}
        />
      </div>

      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Documents per month" />
          <div className="mt-3 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
                <CartesianGrid stroke={grid} vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fill: axis, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: axis, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  cursor={{ fill: grid, opacity: 0.4 }}
                  contentStyle={{
                    background: 'var(--surface-overlay)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 12,
                    color: 'var(--text-primary)',
                  }}
                />
                <Bar dataKey="documents" radius={[3, 3, 0, 0]} maxBarSize={36}>
                  {chartData.map((entry) => (
                    // The selected month is solid; the rest are muted, so the
                    // chart says which month the cards above are describing.
                    <Cell
                      key={entry.key}
                      fill={bar}
                      fillOpacity={entry.key === month ? 1 : 0.35}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="AI cost per month" description="US dollars, as charged." />
          <div className="mt-3 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                <CartesianGrid stroke={grid} vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fill: axis, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: axis, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value: number) => `$${value.toFixed(2)}`}
                />
                <Tooltip
                  cursor={{ fill: grid, opacity: 0.4 }}
                  formatter={(value: number) => formatCost(value)}
                  contentStyle={{
                    background: 'var(--surface-overlay)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 12,
                    color: 'var(--text-primary)',
                  }}
                />
                <Bar dataKey="cost" radius={[3, 3, 0, 0]} maxBarSize={36}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.key}
                      fill={bar}
                      fillOpacity={entry.key === month ? 1 : 0.35}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <TableShell>
          <div className="border-b px-4 py-3">
            <CardHeader
              title="By key"
              description="Which integration is consuming the quota."
            />
          </div>
          <Table>
            <THead>
              <TH>Key</TH>
              <TH align="right">Documents</TH>
              <TH align="right">Pages</TH>
              <TH align="right">AI cost</TH>
            </THead>
            <TBody>
              {(usage?.by_key ?? []).length === 0 ? (
                <tr>
                  <TD colSpan={4} className="py-6 text-center text-[var(--text-tertiary)]">
                    Nothing recorded for {MONTH_LABEL(month)}.
                  </TD>
                </tr>
              ) : (
                (usage?.by_key ?? []).map((row, index) => (
                  <TR key={row.api_key_id ?? `ui-${index}`}>
                    <TD>
                      {row.api_key_id ? (
                        <code className="text-xs">{row.api_key_id}</code>
                      ) : (
                        <span className="text-[var(--text-secondary)]">
                          This web app
                        </span>
                      )}
                    </TD>
                    <TD numeric>{row.documents}</TD>
                    <TD numeric>{row.pages}</TD>
                    <TD numeric>{formatCost(row.ai_cost_usd)}</TD>
                  </TR>
                ))
              )}
            </TBody>
          </Table>
        </TableShell>

        <Card>
          <CardHeader
            title="Export"
            description="Every completed and reviewed document in this project."
          />
          <div className="mt-3 flex gap-2">
            {(['xlsx', 'csv'] as const).map((option) => (
              <button
                key={option}
                onClick={() => setFormat(option)}
                className={
                  'flex-1 rounded-[var(--radius-sm)] border px-3 py-2 text-left transition-colors ' +
                  (format === option
                    ? 'border-[var(--accent-solid)] bg-[var(--surface-selected)]'
                    : 'hover:bg-[var(--surface-hover)]')
                }
              >
                <span className="flex items-center gap-1.5 text-sm font-medium text-[var(--text-primary)]">
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  {option.toUpperCase()}
                </span>
                <span className="mt-0.5 block text-xs text-[var(--text-tertiary)]">
                  {option === 'xlsx'
                    ? 'Two sheets: documents and line items'
                    : 'One flat file with a record_type column'}
                </span>
              </button>
            ))}
          </div>
          <Button
            variant="primary"
            className="mt-3 w-full"
            loading={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            <Download className="h-3.5 w-3.5" />
            Export {format.toUpperCase()}
          </Button>
          <p className="mt-2 text-xs text-[var(--text-tertiary)]">
            Amounts are written as text so a spreadsheet cannot reformat a tax
            number into scientific notation.
          </p>
        </Card>
      </div>
    </Page>
  )
}
