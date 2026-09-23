export type UserRole = "ADMIN" | "NETWORK_ENGINEER" | "IT_SUPPORT" | "VIEWER";

export type DeviceType =
  | "ROUTER"
  | "FIREWALL"
  | "SWITCH"
  | "ACCESS_POINT"
  | "SERVER"
  | "VM"
  | "PRINTER"
  | "CCTV_NVR"
  | "IOT_DEVICE"
  | "GENERIC";

export type DeviceStatus = "UP" | "WARNING" | "CRITICAL" | "DOWN" | "UNKNOWN";
export type CheckType = "ICMP" | "TCP" | "HTTP" | "HTTPS" | "SNMP";
export type CredentialType = "SNMPV2C" | "SNMPV3" | "HTTP_BASIC";
export type MetricType =
  | "AVAILABILITY"
  | "RESPONSE_TIME"
  | "PACKET_LOSS"
  | "CPU_USAGE"
  | "MEMORY_USAGE"
  | "DISK_USAGE"
  | "TEMPERATURE"
  | "UPTIME";
export type InterfaceStatus = "UP" | "DOWN" | "TESTING" | "UNKNOWN";
export type RelationshipType = "UPLINK" | "DOWNLINK" | "PEER";
export type AlertSeverity = "WARNING" | "CRITICAL";
export type AlertStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
export type AlertScope = "GLOBAL" | "DEVICE_TYPE" | "DEVICE";
export type AlertOperator = "GT" | "GTE" | "LT" | "LTE" | "EQ";
export type RuleKind = "METRIC_THRESHOLD" | "DEVICE_UNREACHABLE" | "INTERFACE_DOWN";
export type EventType =
  | "DEVICE_DISCOVERED"
  | "DEVICE_DOWN"
  | "DEVICE_RECOVERED"
  | "INTERFACE_DOWN"
  | "INTERFACE_RECOVERED"
  | "CPU_THRESHOLD_EXCEEDED"
  | "MEMORY_THRESHOLD_EXCEEDED"
  | "CONFIG_CHANGED"
  | "ALERT_ACKNOWLEDGED"
  | "ALERT_RESOLVED"
  | "DISCOVERY_COMPLETED";
export type EventSeverity = "INFO" | "WARNING" | "CRITICAL";
export type DiscoveryJobStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Location {
  id: string;
  name: string;
  description: string | null;
  parent_location_id: string | null;
}

export interface Device {
  id: string;
  hostname: string;
  ip_address: string;
  mac_address: string | null;
  device_type: DeviceType;
  vendor: string | null;
  model: string | null;
  location_id: string | null;
  department: string | null;
  status: DeviceStatus;
  primary_check_type: CheckType;
  is_monitored: boolean;
  last_seen: string | null;
  created_at: string;
  has_snmp_credential: boolean;
}

export interface DeviceCheck {
  id: string;
  check_type: CheckType;
  enabled: boolean;
  config: Record<string, unknown>;
  interval_seconds: number;
  timeout_seconds: number;
  retries: number;
}

export interface InterfaceRow {
  id: string;
  if_index: number;
  name: string;
  alias: string | null;
  oper_status: InterfaceStatus;
  admin_status: InterfaceStatus;
  speed_bps: number | null;
  mac_address: string | null;
  last_change_at: string | null;
}

export interface LatestMetric {
  metric_type: string;
  value: number;
  unit: string | null;
  time: string;
}

export interface DeviceDetail extends Device {
  checks: DeviceCheck[];
  interfaces: InterfaceRow[];
  latest_metrics: LatestMetric[];
}

export interface DeviceCredentialMeta {
  id: string;
  credential_type: CredentialType;
  created_at: string;
  updated_at: string;
}

export interface MetricPoint {
  time: string;
  value: number;
}

export interface MetricSeries {
  metric_type: MetricType;
  unit: string | null;
  points: MetricPoint[];
}

export interface InterfaceMetricPoint {
  time: string;
  in_bps: number | null;
  out_bps: number | null;
  errors_in: number | null;
  errors_out: number | null;
  discards_in: number | null;
  discards_out: number | null;
}

export interface AlertRule {
  id: string;
  name: string;
  rule_kind: RuleKind;
  metric_type: MetricType | null;
  operator: AlertOperator | null;
  threshold: number | null;
  severity: AlertSeverity;
  scope: AlertScope;
  device_type: DeviceType | null;
  device_id: string | null;
  enabled: boolean;
  consecutive_breaches_to_open: number;
  consecutive_ok_to_resolve: number;
}

export interface Alert {
  id: string;
  device_id: string;
  interface_id: string | null;
  alert_rule_id: string | null;
  severity: AlertSeverity;
  metric: string;
  threshold: number | null;
  current_value: number | null;
  message: string;
  status: AlertStatus;
  opened_at: string;
  acknowledged_by_id: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface EventRow {
  id: string;
  device_id: string | null;
  interface_id: string | null;
  event_type: EventType;
  severity: EventSeverity;
  message: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface DiscoveryJob {
  id: string;
  cidr: string;
  status: DiscoveryJobStatus;
  rate_limit_pps: number;
  started_at: string | null;
  finished_at: string | null;
  total_hosts: number | null;
  found_count: number | null;
  error_message: string | null;
  created_at: string;
}

export interface DiscoveryResult {
  id: string;
  discovery_job_id: string;
  ip_address: string;
  hostname_guess: string | null;
  mac_address: string | null;
  open_ports: number[];
  snmp_reachable: boolean;
  suggested_device_type: DeviceType | null;
  imported: boolean;
  device_id: string | null;
}

export interface TopologyNode {
  id: string;
  hostname: string;
  ip_address: string;
  device_type: DeviceType;
  status: DeviceStatus;
  location_id: string | null;
}

export interface TopologyEdge {
  id: string;
  parent_device_id: string;
  child_device_id: string;
  relationship_type: RelationshipType;
  discovered: boolean;
}

export interface TopologyGraph {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface DashboardSummary {
  total_devices: number;
  online: number;
  warning: number;
  critical: number;
  offline: number;
  unknown: number;
  overall_availability_pct: number;
  active_alerts: number;
  active_critical_alerts: number;
  avg_latency_ms: number | null;
  avg_packet_loss_pct: number | null;
  total_inbound_bps: number | null;
  total_outbound_bps: number | null;
  worker_last_heartbeat_at: string | null;
}

export interface ChartSeries {
  label: string;
  points: { time: string; value: number }[];
}

export interface DeviceStatusDistribution {
  status: string;
  count: number;
}

export interface DashboardFilters {
  location_id?: string;
  device_type?: DeviceType;
  vendor?: string;
  status?: DeviceStatus;
}
