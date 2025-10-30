/**
 * Provider Comparison Chart
 *
 * Displays bar chart comparing LLM providers from benchmark results:
 * - Provider score (composite)
 * - Mean confidence
 * - Cost per 1K tokens
 * - Mean latency
 * - Agreement scores
 */
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { Activity, AlertTriangle } from 'lucide-react';

interface ProviderMetrics {
  provider: string;
  call_count: number;
  mean_confidence: number;
  std_confidence: number;
  mean_latency: number;
  std_latency: number;
  total_tokens: number;
  total_cost: number;
  cost_per_1k_tokens: number;
  mean_agreement: number;
  provider_score: number;
}

const COLORS = {
  openai: '#10a37f',
  anthropic: '#d97757',
  gemini: '#4285f4',
};

export function ProviderComparisonChart() {
  const [providers, setProviders] = useState<ProviderMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    fetchBenchmarkData();
    const interval = setInterval(fetchBenchmarkData, 60000); // Refresh every 60s
    return () => clearInterval(interval);
  }, []);

  const fetchBenchmarkData = async () => {
    try {
      const res = await fetch('/api/llm/benchmark-summary');
      if (!res.ok) throw new Error('Failed to fetch benchmark data');

      const data = await res.json();
      setProviders(data.providers || []);
      setLastUpdated(data.last_updated || null);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch benchmark data');
      setLoading(false);
    }
  };

  const formatCost = (cost: number) => `$${cost.toFixed(6)}`;
  const formatLatency = (seconds: number) => `${(seconds * 1000).toFixed(0)}ms`;
  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Provider Comparison</CardTitle>
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
          <CardTitle>Provider Comparison</CardTitle>
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

  if (providers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Provider Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>
            <AlertDescription>
              No benchmark data available. Run benchmarks to compare providers.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // Prepare data for charts
  const scoreData = providers.map((p) => ({
    name: p.provider.toUpperCase(),
    score: p.provider_score,
    provider: p.provider,
  }));

  const confidenceData = providers.map((p) => ({
    name: p.provider.toUpperCase(),
    confidence: p.mean_confidence,
    provider: p.provider,
  }));

  const costData = providers.map((p) => ({
    name: p.provider.toUpperCase(),
    cost: p.cost_per_1k_tokens,
    provider: p.provider,
  }));

  const latencyData = providers.map((p) => ({
    name: p.provider.toUpperCase(),
    latency: p.mean_latency,
    provider: p.provider,
  }));

  const agreementData = providers.map((p) => ({
    name: p.provider.toUpperCase(),
    agreement: p.mean_agreement,
    provider: p.provider,
  }));

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Provider Comparison</CardTitle>
            <CardDescription>
              Benchmark results from latest comparison run
            </CardDescription>
          </div>
          {lastUpdated && (
            <Badge variant="outline" className="text-xs">
              Updated {new Date(lastUpdated).toLocaleDateString()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="score" className="space-y-4">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="score">Score</TabsTrigger>
            <TabsTrigger value="confidence">Confidence</TabsTrigger>
            <TabsTrigger value="cost">Cost</TabsTrigger>
            <TabsTrigger value="latency">Latency</TabsTrigger>
            <TabsTrigger value="agreement">Agreement</TabsTrigger>
          </TabsList>

          <TabsContent value="score" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Composite score (40% confidence + 30% agreement + 20% speed + 10% cost)
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={scoreData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 1]} />
                <Tooltip formatter={(value) => (value as number).toFixed(4)} />
                <Legend />
                <Bar dataKey="score" name="Provider Score" radius={[8, 8, 0, 0]}>
                  {scoreData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.provider as keyof typeof COLORS] || '#888'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>

          <TabsContent value="confidence" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Mean confidence score across all analyzed comments
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={confidenceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 1]} />
                <Tooltip formatter={(value) => formatPercentage(value as number)} />
                <Legend />
                <Bar dataKey="confidence" name="Mean Confidence" radius={[8, 8, 0, 0]}>
                  {confidenceData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.provider as keyof typeof COLORS] || '#888'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>

          <TabsContent value="cost" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Cost per 1,000 tokens (lower is better)
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={costData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(value) => formatCost(value as number)} />
                <Legend />
                <Bar dataKey="cost" name="Cost per 1K Tokens" radius={[8, 8, 0, 0]}>
                  {costData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.provider as keyof typeof COLORS] || '#888'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>

          <TabsContent value="latency" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Mean API response time (lower is better)
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(value) => formatLatency(value as number)} />
                <Legend />
                <Bar dataKey="latency" name="Mean Latency" radius={[8, 8, 0, 0]}>
                  {latencyData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.provider as keyof typeof COLORS] || '#888'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>

          <TabsContent value="agreement" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Mean agreement with other providers (higher is better)
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={agreementData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 1]} />
                <Tooltip formatter={(value) => formatPercentage(value as number)} />
                <Legend />
                <Bar dataKey="agreement" name="Mean Agreement" radius={[8, 8, 0, 0]}>
                  {agreementData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.provider as keyof typeof COLORS] || '#888'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>
        </Tabs>

        {/* Provider Summary Table */}
        <div className="mt-6 border-t pt-4">
          <h4 className="text-sm font-medium mb-3">Provider Summary</h4>
          <div className="space-y-2">
            {providers
              .sort((a, b) => b.provider_score - a.provider_score)
              .map((p, idx) => (
                <div
                  key={p.provider}
                  className="flex items-center justify-between p-3 rounded-lg border bg-card"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={idx === 0 ? 'default' : 'outline'}>
                      {idx === 0 ? '★ Best' : `#${idx + 1}`}
                    </Badge>
                    <span className="font-medium">{p.provider.toUpperCase()}</span>
                    <span className="text-xs text-muted-foreground">{p.call_count} calls</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Score:</span>{' '}
                      <span className="font-semibold">{p.provider_score.toFixed(4)}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Cost:</span>{' '}
                      <span>{formatCost(p.cost_per_1k_tokens)}</span>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
