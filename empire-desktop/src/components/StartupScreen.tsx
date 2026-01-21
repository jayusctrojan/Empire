/**
 * Empire v7.3 - Startup Screen Component
 * Shows loading progress while services are initializing
 *
 * Usage:
 *   <StartupScreen
 *     apiUrl="http://localhost:8000"
 *     onReady={() => setShowMainApp(true)}
 *     onError={(error) => console.error(error)}
 *   />
 */

import React, { useEffect, useState, useCallback } from 'react';
import { ServiceOrchestrator, ServiceHealth, ServiceStatusUpdate } from '../lib/services/orchestrator';
import { ServiceStatusView } from './ServiceStatusView';

// =============================================================================
// TYPES
// =============================================================================

interface StartupScreenProps {
  apiUrl?: string;
  onReady?: () => void;
  onError?: (error: Error) => void;
  onSkip?: () => void;
  logo?: React.ReactNode;
  title?: string;
  skipEnabled?: boolean;
  timeout?: number;
}

interface StartupState {
  phase: 'starting' | 'checking' | 'ready' | 'error' | 'skipped';
  message: string;
  progress: number;
  services: ServiceHealth[];
  error?: string;
}

// =============================================================================
// STYLES
// =============================================================================

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: '#0a0a0a',
    color: '#e5e5e5',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    padding: '20px',
  },
  content: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    maxWidth: '500px',
    width: '100%',
  },
  logo: {
    marginBottom: '24px',
  },
  logoText: {
    fontSize: '48px',
    fontWeight: 700,
    color: '#ffffff',
    letterSpacing: '-2px',
  },
  logoSubtext: {
    fontSize: '14px',
    color: '#666',
    marginTop: '4px',
  },
  progressContainer: {
    width: '100%',
    marginBottom: '24px',
  },
  progressBar: {
    width: '100%',
    height: '4px',
    backgroundColor: '#333',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#3b82f6',
    borderRadius: '2px',
    transition: 'width 0.3s ease-out',
  },
  statusMessage: {
    fontSize: '14px',
    color: '#999',
    marginTop: '12px',
    textAlign: 'center' as const,
  },
  servicesContainer: {
    width: '100%',
    marginTop: '24px',
    maxHeight: '400px',
    overflowY: 'auto' as const,
  },
  actions: {
    marginTop: '24px',
    display: 'flex',
    gap: '12px',
  },
  skipButton: {
    padding: '8px 20px',
    fontSize: '13px',
    backgroundColor: 'transparent',
    border: '1px solid #333',
    borderRadius: '6px',
    color: '#666',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  retryButton: {
    padding: '8px 20px',
    fontSize: '13px',
    backgroundColor: '#3b82f6',
    border: 'none',
    borderRadius: '6px',
    color: '#ffffff',
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  errorContainer: {
    marginTop: '16px',
    padding: '12px 16px',
    backgroundColor: '#1c1c1c',
    border: '1px solid #ef4444',
    borderRadius: '6px',
    width: '100%',
  },
  errorTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#ef4444',
    marginBottom: '8px',
  },
  errorMessage: {
    fontSize: '13px',
    color: '#999',
    lineHeight: 1.5,
  },
  readyContainer: {
    textAlign: 'center' as const,
    marginTop: '16px',
  },
  readyTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: '#22c55e',
    marginBottom: '8px',
  },
  readyMessage: {
    fontSize: '14px',
    color: '#666',
  },
  pulseAnimation: {
    animation: 'pulse 2s ease-in-out infinite',
  },
};

// =============================================================================
// DEFAULT LOGO
// =============================================================================

const DefaultLogo: React.FC = () => (
  <div style={styles.logo}>
    <div style={styles.logoText}>Empire</div>
    <div style={styles.logoSubtext}>v7.3</div>
  </div>
);

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const StartupScreen: React.FC<StartupScreenProps> = ({
  apiUrl = 'http://localhost:8000',
  onReady,
  onError,
  onSkip,
  logo,
  title = 'Starting Empire...',
  skipEnabled = true,
  timeout = 30000,
}) => {
  const [state, setState] = useState<StartupState>({
    phase: 'starting',
    message: title,
    progress: 0,
    services: [],
  });

  const [orchestrator] = useState(() => new ServiceOrchestrator(apiUrl));

  // Handle status updates from orchestrator
  const handleStatusUpdate = useCallback((update: ServiceStatusUpdate) => {
    setState(prev => ({
      ...prev,
      phase: update.phase,
      message: update.message,
      progress: update.progress,
      services: update.services,
    }));

    // Trigger callbacks
    if (update.phase === 'ready' && onReady) {
      setTimeout(onReady, 1000); // Brief delay to show ready state
    }
  }, [onReady]);

  // Start preflight on mount
  useEffect(() => {
    orchestrator.onStatusUpdate(handleStatusUpdate);

    const startPreflight = async () => {
      try {
        // First do a quick required check
        setState(prev => ({
          ...prev,
          message: 'Checking database connection...',
          progress: 10,
        }));

        const { ok, services } = await orchestrator.checkRequired();

        if (ok) {
          // Quick path: required services ready
          setState(prev => ({
            ...prev,
            phase: 'ready',
            message: 'All services ready',
            progress: 100,
            services,
          }));

          if (onReady) {
            setTimeout(onReady, 500);
          }

          // Continue checking other services in background
          orchestrator.startPolling(5000);

        } else {
          // Poll until ready or timeout
          setState(prev => ({
            ...prev,
            message: 'Waiting for services...',
            progress: 30,
          }));

          const ready = await orchestrator.pollUntilReady(timeout, 1000);

          if (!ready) {
            // Full preflight to get details
            try {
              const result = await orchestrator.runPreflight();

              if (!result.all_required_healthy) {
                const failedServices = Object.entries(result.services)
                  .filter(([_, s]) => s.required && s.status !== 'running')
                  .map(([name, _]) => name);

                setState(prev => ({
                  ...prev,
                  phase: 'error',
                  message: 'Required services unavailable',
                  error: `Failed services: ${failedServices.join(', ')}`,
                  services: Object.entries(result.services).map(([name, s]) => ({
                    ...s,
                    name,
                  })),
                }));

                if (onError) {
                  onError(new Error(`Required services unavailable: ${failedServices.join(', ')}`));
                }
              }
            } catch (e) {
              setState(prev => ({
                ...prev,
                phase: 'error',
                message: 'Cannot connect to backend',
                error: e instanceof Error ? e.message : 'Unknown error',
              }));

              if (onError) {
                onError(e instanceof Error ? e : new Error('Unknown error'));
              }
            }
          }
        }

      } catch (e) {
        setState(prev => ({
          ...prev,
          phase: 'error',
          message: 'Startup failed',
          error: e instanceof Error ? e.message : 'Unknown error',
        }));

        if (onError) {
          onError(e instanceof Error ? e : new Error('Unknown error'));
        }
      }
    };

    startPreflight();

    return () => {
      orchestrator.stopPolling();
    };
  }, [orchestrator, handleStatusUpdate, onReady, onError, timeout]);

  // Handle retry
  const handleRetry = useCallback(async () => {
    setState({
      phase: 'starting',
      message: 'Retrying...',
      progress: 0,
      services: [],
    });

    try {
      const result = await orchestrator.runPreflight();

      if (result.ready) {
        setState(prev => ({
          ...prev,
          phase: 'ready',
          message: 'All services ready',
          progress: 100,
        }));

        if (onReady) {
          setTimeout(onReady, 500);
        }
      }
    } catch (e) {
      setState(prev => ({
        ...prev,
        phase: 'error',
        error: e instanceof Error ? e.message : 'Unknown error',
      }));
    }
  }, [orchestrator, onReady]);

  // Handle skip
  const handleSkip = useCallback(() => {
    setState(prev => ({
      ...prev,
      phase: 'skipped',
      message: 'Skipping checks...',
    }));

    if (onSkip) {
      onSkip();
    } else if (onReady) {
      onReady();
    }
  }, [onSkip, onReady]);

  // Handle service retry
  const handleServiceRetry = useCallback(async (serviceName: string) => {
    await orchestrator.startService(serviceName);
    await orchestrator.clearCache();

    // Re-check status
    const result = await orchestrator.runPreflight();
    setState(prev => ({
      ...prev,
      services: Object.entries(result.services).map(([name, s]) => ({
        ...s,
        name,
      })),
    }));
  }, [orchestrator]);

  // Render
  return (
    <div style={styles.container}>
      <div style={styles.content}>
        {/* Logo */}
        {logo || <DefaultLogo />}

        {/* Progress */}
        {state.phase !== 'error' && state.phase !== 'ready' && (
          <div style={styles.progressContainer}>
            <div style={styles.progressBar}>
              <div
                style={{
                  ...styles.progressFill,
                  width: `${state.progress}%`,
                }}
              />
            </div>
            <div style={styles.statusMessage}>{state.message}</div>
          </div>
        )}

        {/* Ready State */}
        {state.phase === 'ready' && (
          <div style={styles.readyContainer}>
            <div style={styles.readyTitle}>✓ Ready</div>
            <div style={styles.readyMessage}>All services are operational</div>
          </div>
        )}

        {/* Error State */}
        {state.phase === 'error' && (
          <div style={styles.errorContainer}>
            <div style={styles.errorTitle}>Startup Failed</div>
            <div style={styles.errorMessage}>
              {state.error || 'Unable to connect to required services.'}
            </div>
          </div>
        )}

        {/* Service List */}
        {state.services.length > 0 && (
          <div style={styles.servicesContainer}>
            <ServiceStatusView
              services={state.services}
              onRetry={state.phase === 'error' ? handleServiceRetry : undefined}
              showDetails={state.phase === 'error'}
              compact={state.phase === 'checking'}
            />
          </div>
        )}

        {/* Actions */}
        <div style={styles.actions}>
          {state.phase === 'error' && (
            <>
              <button
                style={styles.retryButton}
                onClick={handleRetry}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#2563eb';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#3b82f6';
                }}
              >
                Retry
              </button>
              {skipEnabled && (
                <button
                  style={styles.skipButton}
                  onClick={handleSkip}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#666';
                    e.currentTarget.style.color = '#999';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#333';
                    e.currentTarget.style.color = '#666';
                  }}
                >
                  Skip checks
                </button>
              )}
            </>
          )}

          {state.phase === 'checking' && skipEnabled && (
            <button
              style={styles.skipButton}
              onClick={handleSkip}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#666';
                e.currentTarget.style.color = '#999';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#333';
                e.currentTarget.style.color = '#666';
              }}
            >
              Skip optional checks
            </button>
          )}
        </div>
      </div>

      {/* CSS Animation for pulse */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}
      </style>
    </div>
  );
};

export default StartupScreen;
