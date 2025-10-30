/**
 * LLM Performance Panel
 *
 * Displays current active provider performance metrics:
 * - Provider name and model
 * - Daily cost and budget utilization
 * - Mean latency and confidence
 * - Recent API call statistics
 */
import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock, DollarSign, Activity } from 'lucide-react';

interface ProviderConfig {
  provider: string;
  model: string;
  selected_at: string;
  provider_score: number;
  mean_confidence: number;
  cost_per_1k_tokens: number;
  reason: string;
}

interface BudgetStatus {
  total_cost: number;
  monthly_threshold: number;
  percentage_used: number;
  provider_costs: Record<string, number>;
  status: string;
  remaining_budget: number;
}

interface PerformanceMetrics {
  daily_calls: number;
  daily_cost: number;
  mean_latency: number;
  mean_confidence: number;
  error_rate: number;
}

export function LLMPerformancePanel() {
  const [config, setConfig] = useState<ProviderConfig | null>(null);
  const [budget, setBudget] = useState<BudgetStatus | null>(null);
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPerformanceData();
    const interval = setInterval(fetchPerformanceData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchPerformanceData = async () => {
    try {
      const [configRes, budgetRes, metricsRes] = await Promise.all([
        fetch('/api/llm/active-provider'),
        fetch('/api/llm/budget-status'),
        fetch('/api/llm/performance-metrics'),
      ]);

      if (configRes.ok) {
        setConfig(await configRes.json());
      }
      if (budgetRes.ok) {
        setBudget(await budgetRes.json());
      }
      if (metricsRes.ok) {
        setMetrics(await metricsRes.json());
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch performance data');
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === 'critical' || status.startsWith('warning_90')) return 'destructive';
    if (status.startsWith('warning_75')) return 'warning';
    return 'default';
  };

  const formatCost = (cost: number) => `$${cost.toFixed(2)}`;
  const formatPercentage = (value: number) => `${value.toFixed(1)}%`;
  const formatDuration = (seconds: number) => `${(seconds * 1000).toFixed(0)}ms`;

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>LLM Performance</CardTitle>
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
          <CardTitle>LLM Performance</CardTitle>
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
        <CardTitle className="flex items-center justify-between">
          <span>LLM Performance</span>
          {config && (
            <Badge variant="outline" className="text-sm">
              {config.provider.toUpperCase()}
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Active provider performance and cost monitoring
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Active Provider Info */}
        {config && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Model</span>
              <span className="font-mono">{config.model}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Provider Score</span>
              <span className="font-semibold">{config.provider_score.toFixed(4)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Selected</span>
              <span className="text-xs">
                {new Date(config.selected_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        )}

        {/* Budget Status */}
        {budget && (
          <div className="space-y-2 border-t pt-4">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Monthly Budget</span>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Spent</span>
                <span className="font-semibold">{formatCost(budget.total_cost)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Remaining</span>
                <span>{formatCost(budget.remaining_budget)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Utilization</span>
                <Badge variant={getStatusColor(budget.status)}>
                  {formatPercentage(budget.percentage_used)}
                </Badge>
              </div>
            </div>
            {(budget.status === 'critical' || budget.status.startsWith('warning')) && (
              <Alert variant="destructive" className="mt-2">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {budget.status === 'critical'
                    ? 'Budget exceeded! Review usage immediately.'
                    : `Budget at ${budget.percentage_used.toFixed(0)}% - approaching limit.`}
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Performance Metrics */}
        {metrics && (
          <div className="space-y-2 border-t pt-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Today's Performance</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>Latency</span>
                </div>
                <div className="text-lg font-semibold">
                  {formatDuration(metrics.mean_latency)}
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <CheckCircle className="h-3 w-3" />
                  <span>Confidence</span>
                </div>
                <div className="text-lg font-semibold">
                  {formatPercentage(metrics.mean_confidence * 100)}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">API Calls</div>
                <div className="text-lg font-semibold">{metrics.daily_calls}</div>
              </div>
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Error Rate</div>
                <div className="text-lg font-semibold">
                  {formatPercentage(metrics.error_rate)}
                </div>
              </div>
            </div>
            {metrics.error_rate > 5 && (
              <Alert variant="destructive" className="mt-2">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  High error rate detected. Fallback provider may be activated.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Selection Reason */}
        {config && config.reason && (
          <div className="border-t pt-4">
            <p className="text-xs text-muted-foreground">
              <strong>Selection Reason:</strong> {config.reason}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
