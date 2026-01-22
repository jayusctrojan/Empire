/**
 * Empire v7.3 - Service Status View Component
 * Visual component showing service health status
 *
 * Usage:
 *   <ServiceStatusView services={services} onRetry={handleRetry} />
 */

import React from 'react';
import type { ServiceHealth, ServiceCategory } from '../lib/services/orchestrator';

// =============================================================================
// TYPES
// =============================================================================

interface ServiceStatusViewProps {
  services: ServiceHealth[];
  onRetry?: (serviceName: string) => void;
  showDetails?: boolean;
  compact?: boolean;
}

interface ServiceItemProps {
  service: ServiceHealth;
  onRetry?: (serviceName: string) => void;
  showDetails?: boolean;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return '#22c55e'; // green
    case 'degraded':
      return '#f59e0b'; // yellow
    case 'checking':
      return '#3b82f6'; // blue
    case 'stopped':
    case 'error':
    default:
      return '#ef4444'; // red
  }
}

function getStatusIcon(status: string): string {
  switch (status) {
    case 'running':
      return '✓';
    case 'degraded':
      return '◐';
    case 'checking':
      return '○';
    case 'stopped':
    case 'error':
    default:
      return '✗';
  }
}

function getCategoryLabel(category: ServiceCategory): string {
  switch (category) {
    case 'required':
      return 'Required';
    case 'important':
      return 'Important';
    case 'optional':
      return 'Optional';
    case 'infrastructure':
      return 'Infrastructure';
    default:
      return category;
  }
}

function formatLatency(latencyMs?: number): string {
  if (latencyMs === undefined) return '';
  if (latencyMs < 1) return '<1ms';
  return `${Math.round(latencyMs)}ms`;
}

// =============================================================================
// STYLES
// =============================================================================

const styles: Record<string, React.CSSProperties> = {
  container: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    backgroundColor: '#1a1a1a',
    borderRadius: '8px',
    padding: '16px',
    color: '#e5e5e5',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
  },
  title: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#ffffff',
    margin: 0,
  },
  badge: {
    fontSize: '11px',
    padding: '2px 8px',
    borderRadius: '12px',
    backgroundColor: '#333',
    color: '#999',
  },
  serviceList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '8px',
  },
  serviceItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 12px',
    backgroundColor: '#252525',
    borderRadius: '6px',
    borderLeft: '3px solid transparent',
  },
  serviceInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  statusIndicator: {
    width: '20px',
    height: '20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
  },
  serviceName: {
    fontSize: '13px',
    fontWeight: 500,
  },
  serviceCategory: {
    fontSize: '10px',
    color: '#666',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  serviceDetails: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  latency: {
    fontSize: '11px',
    color: '#666',
    fontFamily: 'monospace',
  },
  retryButton: {
    fontSize: '11px',
    padding: '4px 8px',
    backgroundColor: '#333',
    border: 'none',
    borderRadius: '4px',
    color: '#999',
    cursor: 'pointer',
  },
  errorMessage: {
    fontSize: '11px',
    color: '#ef4444',
    marginTop: '4px',
    marginLeft: '30px',
  },
  categorySection: {
    marginBottom: '16px',
  },
  categoryHeader: {
    fontSize: '11px',
    fontWeight: 600,
    color: '#666',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    marginBottom: '8px',
  },
  compactItem: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    backgroundColor: '#252525',
    borderRadius: '16px',
    fontSize: '12px',
    marginRight: '6px',
    marginBottom: '6px',
  },
};

// =============================================================================
// SERVICE ITEM COMPONENT
// =============================================================================

const ServiceItem: React.FC<ServiceItemProps> = ({ service, onRetry, showDetails }) => {
  const statusColor = getStatusColor(service.status);
  const statusIcon = getStatusIcon(service.status);

  return (
    <div>
      <div
        style={{
          ...styles.serviceItem,
          borderLeftColor: statusColor,
        }}
      >
        <div style={styles.serviceInfo}>
          <span
            style={{
              ...styles.statusIndicator,
              color: statusColor,
            }}
          >
            {statusIcon}
          </span>
          <div>
            <div style={styles.serviceName}>{service.name}</div>
            {showDetails && (
              <div style={styles.serviceCategory}>
                {getCategoryLabel(service.category)}
                {service.required && ' • Required'}
              </div>
            )}
          </div>
        </div>

        <div style={styles.serviceDetails}>
          {service.latency_ms !== undefined && (
            <span
              style={{
                ...styles.latency,
                color: service.latency_ms < 100 ? '#22c55e' :
                       service.latency_ms < 500 ? '#f59e0b' : '#ef4444'
              }}
            >
              {formatLatency(service.latency_ms)}
            </span>
          )}

          {onRetry && (service.status === 'error' || service.status === 'stopped') && (
            <button
              style={styles.retryButton}
              onClick={() => onRetry(service.name)}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#444';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#333';
              }}
            >
              Retry
            </button>
          )}
        </div>
      </div>

      {showDetails && service.error_message && (
        <div style={styles.errorMessage}>
          {service.error_message}
        </div>
      )}
    </div>
  );
};

// =============================================================================
// COMPACT SERVICE ITEM
// =============================================================================

const CompactServiceItem: React.FC<{ service: ServiceHealth }> = ({ service }) => {
  const statusColor = getStatusColor(service.status);
  const statusIcon = getStatusIcon(service.status);

  return (
    <span style={styles.compactItem}>
      <span style={{ color: statusColor }}>{statusIcon}</span>
      <span>{service.name}</span>
    </span>
  );
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export const ServiceStatusView: React.FC<ServiceStatusViewProps> = ({
  services,
  onRetry,
  showDetails = true,
  compact = false,
}) => {
  // Group services by category
  const grouped = services.reduce((acc, service) => {
    const category = service.category || 'optional';
    if (!acc[category]) acc[category] = [];
    acc[category].push(service);
    return acc;
  }, {} as Record<ServiceCategory, ServiceHealth[]>);

  // Calculate summary
  const total = services.length;
  const healthy = services.filter(s => s.status === 'running').length;
  const requiredHealthy = services.filter(s => s.required && s.status === 'running').length;
  const requiredTotal = services.filter(s => s.required).length;

  // Compact mode
  if (compact) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h3 style={styles.title}>Services</h3>
          <span style={{
            ...styles.badge,
            backgroundColor: healthy === total ? '#22c55e20' : '#f59e0b20',
            color: healthy === total ? '#22c55e' : '#f59e0b',
          }}>
            {healthy}/{total} healthy
          </span>
        </div>
        <div>
          {services.map((service) => (
            <CompactServiceItem key={service.name} service={service} />
          ))}
        </div>
      </div>
    );
  }

  // Full mode
  const categoryOrder: ServiceCategory[] = ['required', 'important', 'optional', 'infrastructure'];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>Service Status</h3>
        <span style={{
          ...styles.badge,
          backgroundColor: requiredHealthy === requiredTotal ? '#22c55e20' : '#ef444420',
          color: requiredHealthy === requiredTotal ? '#22c55e' : '#ef4444',
        }}>
          {requiredHealthy === requiredTotal ? 'Ready' : 'Degraded'}
        </span>
      </div>

      {categoryOrder.map((category) => {
        const categoryServices = grouped[category];
        if (!categoryServices || categoryServices.length === 0) return null;

        return (
          <div key={category} style={styles.categorySection}>
            <div style={styles.categoryHeader}>
              {getCategoryLabel(category)}
            </div>
            <div style={styles.serviceList}>
              {categoryServices.map((service) => (
                <ServiceItem
                  key={service.name}
                  service={service}
                  onRetry={onRetry}
                  showDetails={showDetails}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ServiceStatusView;
