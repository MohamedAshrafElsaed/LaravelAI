'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  Zap,
  Code,
  FileWarning,
  TestTube,
  FileText,
  Bot,
  Server,
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { projectsApi, getErrorMessage } from '@/lib/api';
import { useToast } from '@/components/Toast';
import { Button } from '@/components/ui/Button';

interface Issue {
  id: string;
  category: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  file_path?: string;
  line_number?: number;
  suggestion?: string;
  auto_fixable: boolean;
  status: 'open' | 'fixed' | 'ignored';
}

interface HealthCategory {
  score: number;
  issues: number;
}

interface HealthData {
  score: number;
  production_ready: boolean;
  categories: Record<string, HealthCategory>;
  issues_summary: {
    total: number;
    open: number;
    fixed: number;
    ignored: number;
    by_severity: {
      critical: number;
      warning: number;
      info: number;
    };
  };
  scanned_at: string | null;
}

interface ScanStatus {
  status: 'pending' | 'scanning' | 'analyzing' | 'completed' | 'error';
  progress: number;
  message?: string;
  stack?: any;
  file_stats?: any;
  health_score?: number;
  health_check?: any;
  scanned_at?: string;
}

interface ProjectHealthProps {
  projectId: string;
  clonePath?: string;
}

const categoryIcons: Record<string, React.ElementType> = {
  architecture: Server,
  security: ShieldCheck,
  performance: Zap,
  code_quality: Code,
  error_handling: AlertCircle,
  logging: FileText,
  testing: TestTube,
  documentation: FileText,
  ai_readiness: Bot,
};

const categoryLabels: Record<string, string> = {
  architecture: 'Architecture',
  security: 'Security',
  performance: 'Performance',
  code_quality: 'Code Quality',
  error_handling: 'Error Handling',
  logging: 'Logging & Monitoring',
  testing: 'Testing',
  documentation: 'Documentation',
  ai_readiness: 'AI Readiness',
};

const severityColors = {
  critical: 'text-red-400 bg-red-500/10 border-red-500/30',
  warning: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  info: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
};

const severityIcons = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

export function ProjectHealth({ projectId, clonePath }: ProjectHealthProps) {
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [selectedSeverity, setSelectedSeverity] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const [healthRes, issuesRes] = await Promise.all([
        projectsApi.getHealth(projectId),
        projectsApi.getIssues(projectId),
      ]);
      setHealth(healthRes.data);
      setIssues(issuesRes.data);
    } catch (error: any) {
      // If 400, project hasn't been scanned yet
      if (error.status !== 400) {
        console.error('Failed to fetch health:', error);
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const fetchScanStatus = useCallback(async () => {
    try {
      const response = await projectsApi.getScanStatus(projectId);
      setScanStatus(response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch scan status:', error);
      return null;
    }
  }, [projectId]);

  useEffect(() => {
    fetchHealth();
    fetchScanStatus();
  }, [fetchHealth, fetchScanStatus]);

  // Poll for scan progress
  useEffect(() => {
    if (!scanning) return;

    const interval = setInterval(async () => {
      const status = await fetchScanStatus();
      if (status?.status === 'completed' || status?.status === 'error') {
        setScanning(false);
        if (status.status === 'completed') {
          toast.success('Scan completed');
          fetchHealth();
        } else {
          toast.error('Scan failed', status.message || 'Unknown error');
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [scanning, fetchScanStatus, fetchHealth, toast]);

  const startScan = async () => {
    if (!clonePath) {
      toast.error('Project not cloned', 'Clone the project first before scanning');
      return;
    }

    setScanning(true);
    try {
      await projectsApi.startScan(projectId);
      toast.info('Scan started', 'Analyzing your project...');
    } catch (error) {
      setScanning(false);
      toast.error('Failed to start scan', getErrorMessage(error));
    }
  };

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  const updateIssueStatus = async (issueId: string, status: string) => {
    try {
      await projectsApi.updateIssueStatus(projectId, issueId, status);
      setIssues(issues.map(i => i.id === issueId ? { ...i, status: status as Issue['status'] } : i));
      toast.success('Issue updated');
    } catch (error) {
      toast.error('Failed to update issue', getErrorMessage(error));
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400';
    if (score >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const filteredIssues = selectedSeverity
    ? issues.filter(i => i.severity === selectedSeverity && i.status === 'open')
    : issues.filter(i => i.status === 'open');

  const issuesByCategory = filteredIssues.reduce((acc, issue) => {
    if (!acc[issue.category]) acc[issue.category] = [];
    acc[issue.category].push(issue);
    return acc;
  }, {} as Record<string, Issue[]>);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500/30 border-t-blue-500" />
      </div>
    );
  }

  // No health data yet - show scan prompt
  if (!health) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center p-8">
        <ShieldCheck className="h-12 w-12 text-gray-500 mb-4" />
        <h3 className="text-lg font-semibold text-white">No Health Check Yet</h3>
        <p className="text-gray-400 mt-2 max-w-md">
          Run a health check to analyze your project's architecture, security, performance, and more.
        </p>
        <Button
          variant="primary"
          size="lg"
          className="mt-6"
          onClick={startScan}
          loading={scanning}
          leftIcon={<RefreshCw className="h-4 w-4" />}
        >
          {scanning ? 'Scanning...' : 'Run Health Check'}
        </Button>
        {scanning && scanStatus && (
          <div className="mt-4 w-full max-w-xs">
            <div className="flex items-center justify-between text-sm text-gray-400 mb-2">
              <span>{scanStatus.message}</span>
              <span>{scanStatus.progress}%</span>
            </div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${scanStatus.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header with Score */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className={`relative h-20 w-20 rounded-full flex items-center justify-center ${getScoreColor(health.score)} bg-gray-800 border-2 border-current`}>
              <span className="text-2xl font-bold">{Math.round(health.score)}</span>
              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="45"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="6"
                  strokeDasharray={`${health.score * 2.83} 283`}
                  className="opacity-30"
                />
              </svg>
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">Health Score</h2>
              <p className={`text-sm ${health.production_ready ? 'text-green-400' : 'text-yellow-400'}`}>
                {health.production_ready ? 'Production Ready' : 'Needs Improvement'}
              </p>
              {health.scanned_at && (
                <p className="text-xs text-gray-500 mt-1">
                  Last scanned: {new Date(health.scanned_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>
          <Button
            variant="outline"
            size="md"
            onClick={startScan}
            loading={scanning}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Re-scan
          </Button>
        </div>

        {/* Issues Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            onClick={() => setSelectedSeverity(selectedSeverity === 'critical' ? null : 'critical')}
            className={`p-4 rounded-lg border transition-colors ${
              selectedSeverity === 'critical'
                ? 'border-red-500 bg-red-500/10'
                : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
            }`}
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <span className="text-2xl font-bold text-red-400">{health.issues_summary.by_severity.critical}</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Critical</p>
          </button>
          <button
            onClick={() => setSelectedSeverity(selectedSeverity === 'warning' ? null : 'warning')}
            className={`p-4 rounded-lg border transition-colors ${
              selectedSeverity === 'warning'
                ? 'border-yellow-500 bg-yellow-500/10'
                : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
            }`}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-400" />
              <span className="text-2xl font-bold text-yellow-400">{health.issues_summary.by_severity.warning}</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Warnings</p>
          </button>
          <button
            onClick={() => setSelectedSeverity(selectedSeverity === 'info' ? null : 'info')}
            className={`p-4 rounded-lg border transition-colors ${
              selectedSeverity === 'info'
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
            }`}
          >
            <div className="flex items-center gap-2">
              <Info className="h-5 w-5 text-blue-400" />
              <span className="text-2xl font-bold text-blue-400">{health.issues_summary.by_severity.info}</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Info</p>
          </button>
          <div className="p-4 rounded-lg border border-gray-700 bg-gray-800/50">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-400" />
              <span className="text-2xl font-bold text-green-400">{health.issues_summary.fixed}</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">Fixed</p>
          </div>
        </div>

        {/* Categories Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(health.categories).map(([category, data]) => {
            const Icon = categoryIcons[category] || FileWarning;
            const label = categoryLabels[category] || category;
            return (
              <div
                key={category}
                className="p-4 rounded-lg border border-gray-700 bg-gray-800/50"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className={`h-4 w-4 ${getScoreColor(data.score)}`} />
                    <span className="text-sm font-medium text-white">{label}</span>
                  </div>
                  <span className={`text-lg font-bold ${getScoreColor(data.score)}`}>
                    {Math.round(data.score)}
                  </span>
                </div>
                <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${getScoreBg(data.score)} transition-all duration-500`}
                    style={{ width: `${data.score}%` }}
                  />
                </div>
                {data.issues > 0 && (
                  <p className="text-xs text-gray-500 mt-2">{data.issues} issues</p>
                )}
              </div>
            );
          })}
        </div>

        {/* Issues List */}
        {filteredIssues.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white">
              {selectedSeverity ? `${selectedSeverity.charAt(0).toUpperCase() + selectedSeverity.slice(1)} Issues` : 'All Open Issues'}
              <span className="ml-2 text-sm font-normal text-gray-400">({filteredIssues.length})</span>
            </h3>

            {Object.entries(issuesByCategory).map(([category, categoryIssues]) => {
              const Icon = categoryIcons[category] || FileWarning;
              const label = categoryLabels[category] || category;
              const isExpanded = expandedCategories.has(category);

              return (
                <div key={category} className="border border-gray-700 rounded-lg overflow-hidden">
                  <button
                    onClick={() => toggleCategory(category)}
                    className="w-full flex items-center justify-between p-4 bg-gray-800/50 hover:bg-gray-800 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="h-5 w-5 text-gray-400" />
                      <span className="font-medium text-white">{label}</span>
                      <span className="text-sm text-gray-500">({categoryIssues.length})</span>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="h-5 w-5 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-5 w-5 text-gray-400" />
                    )}
                  </button>

                  {isExpanded && (
                    <div className="divide-y divide-gray-700">
                      {categoryIssues.map((issue) => {
                        const SeverityIcon = severityIcons[issue.severity];
                        return (
                          <div key={issue.id} className="p-4 bg-gray-900/50">
                            <div className="flex items-start gap-3">
                              <div className={`p-1.5 rounded ${severityColors[issue.severity]}`}>
                                <SeverityIcon className="h-4 w-4" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <h4 className="font-medium text-white">{issue.title}</h4>
                                <p className="text-sm text-gray-400 mt-1">{issue.description}</p>
                                {issue.file_path && (
                                  <p className="text-xs text-gray-500 mt-2 font-mono">
                                    {issue.file_path}
                                    {issue.line_number && `:${issue.line_number}`}
                                  </p>
                                )}
                                {issue.suggestion && (
                                  <div className="mt-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
                                    <p className="text-xs text-gray-500 mb-1">Suggestion</p>
                                    <p className="text-sm text-gray-300">{issue.suggestion}</p>
                                  </div>
                                )}
                                <div className="flex items-center gap-2 mt-3">
                                  <button
                                    onClick={() => updateIssueStatus(issue.id, 'fixed')}
                                    className="text-xs text-green-400 hover:text-green-300 transition-colors"
                                  >
                                    Mark as Fixed
                                  </button>
                                  <span className="text-gray-600">|</span>
                                  <button
                                    onClick={() => updateIssueStatus(issue.id, 'ignored')}
                                    className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
                                  >
                                    Ignore
                                  </button>
                                  {issue.auto_fixable && (
                                    <>
                                      <span className="text-gray-600">|</span>
                                      <span className="text-xs text-blue-400">Auto-fixable</span>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {filteredIssues.length === 0 && (
          <div className="text-center py-8">
            <CheckCircle className="h-12 w-12 text-green-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white">
              {selectedSeverity ? `No ${selectedSeverity} issues` : 'No open issues'}
            </h3>
            <p className="text-gray-400 mt-2">
              {selectedSeverity ? 'Try selecting a different severity filter.' : 'All issues have been addressed. Great job!'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// Small badge for showing health score on cards
export function HealthScoreBadge({ score }: { score: number | null | undefined }) {
  if (score === null || score === undefined) return null;

  const getColor = () => {
    if (score >= 80) return 'text-green-400 bg-green-500/10 border-green-500/30';
    if (score >= 60) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
    return 'text-red-400 bg-red-500/10 border-red-500/30';
  };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium border ${getColor()}`}>
      <ShieldCheck className="h-3 w-3" />
      {Math.round(score)}
    </span>
  );
}
