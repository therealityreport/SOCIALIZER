/**
 * Drift Monitor Component
 *
 * Displays quality drift monitoring results:
 * - Agreement trends over time
 * - Latest drift check status
 * - Sentiment and sarcasm agreement breakdowns
 * - Alert history
 */
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Activity, AlertTriangle, CheckCircle, TrendingDown, TrendingUp } from 'lucide-react';

interface DriftCheck {
  check_date: string;
  primary_provider: string;
  secondary_provider: string;
  samples_checked: number;
  agreement_score: number;
  sentiment_agreement: number;
  sarcasm_agreement: number;
  status: string;
  alert_sent: boolean;
}

interface DriftTrend {
  date: string;
  agreement_score: number;
  sentiment_agreement: number;
  sarcasm_agreement: number;
}

export function DriftMonitor() {
  const [latestCheck, setLatestCheck] = useState<DriftCheck | null>(null);
  const [trendData, setTrendData] = useState<DriftTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDriftData();
    const interval = setInterval(fetchDriftData, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, []);

  const fetchDriftData = async () => {
    try {
      const [latestRes, trendRes] = await Promise.all([
        fetch('/api/llm/drift-latest'),
        fetch('/api/llm/drift-trend?days=30'),
      ]);

      if (latestRes.ok) {
        setLatestCheck(await latestRes.json());
      }
      if (trendRes.ok) {
        setTrendData(await trendRes.json());
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch drift data');
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === 'critical') return 'destructive';
    if (status === 'warning') return 'warning';
    return 'default';
  };

  const getStatusIcon = (status: string) => {
    if (status === 'critical') return <AlertTriangle className="h-4 w-4" />;
    if (status === 'warning') return <TrendingDown className="h-4 w-4" />;
    return <CheckCircle className="h-4 w-4" />;
  };

  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;
  const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Quality Drift Monitor</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Activity className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Quality Drift Monitor</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Quality Drift Monitor</CardTitle>
            <CardDescription>
              Weekly provider agreement checks to detect quality changes
            </CardDescription>
          </div>
          {latestCheck && (
            <Badge variant={getStatusColor(latestCheck.status)}>
              {latestCheck.status.toUpperCase()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Latest Check Status */}
        {latestCheck && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              {getStatusIcon(latestCheck.status)}
              <span className="font-medium">Latest Check</span>
              <span className="text-xs text-muted-foreground">
                {new Date(latestCheck.check_date).toLocaleString()}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Primary Provider</div>
                <div className="font-semibold">{latestCheck.primary_provider.toUpperCase()}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Secondary Provider</div>
                <div className="font-semibold">{latestCheck.secondary_provider.toUpperCase()}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Samples Checked</div>
                <div className="font-semibold">{latestCheck.samples_checked}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Alert Sent</div>
                <div className="font-semibold">{latestCheck.alert_sent ? 'Yes' : 'No'}</div>
              </div>
            </div>

            {/* Agreement Breakdown */}
            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Overall Agreement</span>
                <span className="text-lg font-semibold">
                  {formatPercentage(latestCheck.agreement_score)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Sentiment Agreement</span>
                <span className="font-medium">
                  {formatPercentage(latestCheck.sentiment_agreement)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Sarcasm Agreement</span>
                <span className="font-medium">
                  {formatPercentage(latestCheck.sarcasm_agreement)}
                </span>
              </div>
            </div>

            {/* Status Alerts */}
            {latestCheck.status === 'critical' && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  <strong>Critical drift detected!</strong> Agreement score below 70%.
                  Review recent analyses and consider re-benchmarking providers.
                </AlertDescription>
              </Alert>
            )}
            {latestCheck.status === 'warning' && (
              <Alert variant="warning">
                <TrendingDown className="h-4 w-4" />
                <AlertDescription>
                  <strong>Warning:</strong> Agreement score below 80% threshold.
                  Monitor for continued degradation.
                </AlertDescription>
              </Alert>
            )}
            {latestCheck.status === 'ok' && (
              <Alert>
                <CheckCircle className="h-4 w-4" />
                <AlertDescription>
                  Quality is stable. Provider results are consistent.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Trend Chart */}
        {trendData.length > 0 && (
          <div className="space-y-4 border-t pt-6">
            <div>
              <h4 className="text-sm font-medium mb-2">30-Day Agreement Trend</h4>
              <p className="text-xs text-muted-foreground">
                Agreement scores over time (threshold: 80%)
              </p>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  tick={{ fontSize: 12 }}
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  formatter={(value: number) => formatPercentage(value)}
                  labelFormatter={formatDate}
                />
                <Legend />
                <ReferenceLine
                  y={0.8}
                  stroke="#fbbf24"
                  strokeDasharray="3 3"
                  label={{ value: 'Threshold (80%)', fontSize: 10 }}
                />
                <ReferenceLine
                  y={0.7}
                  stroke="#ef4444"
                  strokeDasharray="3 3"
                  label={{ value: 'Critical (70%)', fontSize: 10 }}
                />
                <Line
                  type="monotone"
                  dataKey="agreement_score"
                  name="Overall Agreement"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="sentiment_agreement"
                  name="Sentiment"
                  stroke="#10b981"
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="sarcasm_agreement"
                  name="Sarcasm"
                  stroke="#8b5cf6"
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* No Data State */}
        {!latestCheck && trendData.length === 0 && (
          <Alert>
            <AlertDescription>
              No drift check data available yet. Weekly checks will begin after the first benchmark run.
            </AlertDescription>
          </Alert>
        )}

        {/* Explanation */}
        <div className="border-t pt-4 text-xs text-muted-foreground space-y-2">
          <p>
            <strong>How it works:</strong> Each week, we re-analyze a sample of recent comments
            with the secondary provider and compare results to the primary provider.
          </p>
          <p>
            <strong>Agreement Score:</strong> Composite of sentiment agreement (70%) and
            sarcasm score variance (30%). Lower agreement may indicate model drift or data distribution changes.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
