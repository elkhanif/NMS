"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import type {
  Alert,
  AlertRule,
  DashboardFilters,
  DashboardSummary,
  Device,
  DeviceAddress,
  DeviceCheck,
  DeviceCredentialMeta,
  DeviceDetail,
  DeviceInvestigation,
  DeviceStatusDistribution,
  DetectiveSearchResult,
  DiscoveryJob,
  DiscoveryResult,
  EventRow,
  Incident,
  IncidentDetail,
  InterfaceMetricPoint,
  InterfaceRow,
  Location,
  MetricSeries,
  ChartSeries as ChartSeriesT,
  TopologyGraph,
  User,
} from "@/lib/types";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore parse errors */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

const qs = (params: object): string => {
  const usp = new URLSearchParams();
  Object.entries(params as Record<string, unknown>).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") usp.set(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : "";
};

const LIVE_REFETCH_MS = 20_000;

// ---------- Dashboard ----------

export function useDashboardSummary(filters: DashboardFilters) {
  return useQuery({
    queryKey: ["dashboard-summary", filters],
    queryFn: () => apiFetch<DashboardSummary>(`dashboard/summary${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useStatusDistribution(filters: DashboardFilters) {
  return useQuery({
    queryKey: ["status-distribution", filters],
    queryFn: () => apiFetch<DeviceStatusDistribution[]>(`dashboard/status-distribution${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDashboardChart(series: string, hours = 24) {
  return useQuery({
    queryKey: ["dashboard-chart", series, hours],
    queryFn: () => apiFetch<ChartSeriesT>(`dashboard/charts/${series}${qs({ hours })}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

// ---------- Devices ----------

export interface DeviceFilters {
  location_id?: string;
  device_type?: string;
  vendor?: string;
  status?: string;
  search?: string;
}

export function useDevices(filters: DeviceFilters = {}) {
  return useQuery({
    queryKey: ["devices", filters],
    queryFn: () => apiFetch<Device[]>(`devices/${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDevice(id: string, options?: Partial<UseQueryOptions<DeviceDetail>>) {
  return useQuery({
    queryKey: ["device", id],
    queryFn: () => apiFetch<DeviceDetail>(`devices/${id}`),
    refetchInterval: LIVE_REFETCH_MS,
    enabled: Boolean(id),
    ...options,
  });
}

export function useDeviceMetrics(deviceId: string, metricType: string, hours = 24) {
  return useQuery({
    queryKey: ["device-metrics", deviceId, metricType, hours],
    queryFn: () => apiFetch<MetricSeries>(`devices/${deviceId}/metrics${qs({ metric_type: metricType, hours })}`),
    enabled: Boolean(deviceId && metricType),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDeviceAlerts(deviceId: string) {
  return useQuery({
    queryKey: ["device-alerts", deviceId],
    queryFn: () => apiFetch<Alert[]>(`devices/${deviceId}/alerts`),
    enabled: Boolean(deviceId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDeviceEvents(deviceId: string) {
  return useQuery({
    queryKey: ["device-events", deviceId],
    queryFn: () => apiFetch<EventRow[]>(`devices/${deviceId}/events`),
    enabled: Boolean(deviceId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDeviceCredentials(deviceId: string) {
  return useQuery({
    queryKey: ["device-credentials", deviceId],
    queryFn: () => apiFetch<DeviceCredentialMeta[]>(`devices/${deviceId}/credentials`),
    enabled: Boolean(deviceId),
  });
}

export function useBulkSetCredential() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { device_ids: string[]; credential_type: string; payload: Record<string, string> }) =>
      apiFetch<{ applied_count: number; skipped_ids: string[] }>("devices/bulk-credentials", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useBulkSetCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      device_ids: string[];
      check_type: string;
      enabled?: boolean;
      config?: Record<string, unknown>;
      interval_seconds?: number;
      timeout_seconds?: number;
      retries?: number;
    }) =>
      apiFetch<{ applied_count: number; skipped_ids: string[] }>("devices/bulk-checks", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useCreateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Device>) =>
      apiFetch<Device>("devices/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useUpdateDevice(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Device>) =>
      apiFetch<Device>(`devices/${deviceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["devices"] });
      qc.invalidateQueries({ queryKey: ["device", deviceId] });
    },
  });
}

export function useDeleteDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deviceId: string) => apiFetch<void>(`devices/${deviceId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useUpsertDeviceCheck(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<DeviceCheck>) =>
      apiFetch<DeviceCheck>(`devices/${deviceId}/checks`, { method: "PUT", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["device", deviceId] }),
  });
}

export function useSetDeviceCredential(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { credential_type: string; payload: Record<string, string> }) =>
      apiFetch<DeviceCredentialMeta>(`devices/${deviceId}/credentials`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["device-credentials", deviceId] }),
  });
}

// ---------- Interfaces ----------

export function useDeviceInterfaces(deviceId: string) {
  return useQuery({
    queryKey: ["device-interfaces", deviceId],
    queryFn: () => apiFetch<InterfaceRow[]>(`devices/${deviceId}/interfaces`),
    enabled: Boolean(deviceId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useInterfaceMetrics(interfaceId: string, hours = 24) {
  return useQuery({
    queryKey: ["interface-metrics", interfaceId, hours],
    queryFn: () => apiFetch<InterfaceMetricPoint[]>(`interfaces/${interfaceId}/metrics${qs({ hours })}`),
    enabled: Boolean(interfaceId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

// ---------- Alerts ----------

export interface AlertFilters {
  status?: string;
  severity?: string;
  device_id?: string;
}

export function useAlerts(filters: AlertFilters = {}) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => apiFetch<Alert[]>(`alerts/${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useAcknowledgeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => apiFetch<Alert>(`alerts/${alertId}/acknowledge`, { method: "PATCH" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useResolveAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) => apiFetch<Alert>(`alerts/${alertId}/resolve`, { method: "PATCH" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useAlertRules() {
  return useQuery({
    queryKey: ["alert-rules"],
    queryFn: () => apiFetch<AlertRule[]>("alert-rules/"),
  });
}

export function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<AlertRule>) =>
      apiFetch<AlertRule>("alert-rules/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-rules"] }),
  });
}

export function useUpdateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<AlertRule> }) =>
      apiFetch<AlertRule>(`alert-rules/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-rules"] }),
  });
}

export function useDeleteAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`alert-rules/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-rules"] }),
  });
}

// ---------- Events ----------

export function useEvents(
  filters: { device_id?: string; event_type?: string; severity?: string; category?: "change" } = {}
) {
  return useQuery({
    queryKey: ["events", filters],
    queryFn: () => apiFetch<EventRow[]>(`events/${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

// ---------- Discovery ----------

export function useDiscoveryJobs() {
  return useQuery({
    queryKey: ["discovery-jobs"],
    queryFn: () => apiFetch<DiscoveryJob[]>("discovery/"),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDiscoveryResults(jobId: string) {
  return useQuery({
    queryKey: ["discovery-results", jobId],
    queryFn: () => apiFetch<DiscoveryResult[]>(`discovery/${jobId}/results`),
    enabled: Boolean(jobId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useStartDiscovery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { cidr: string; credential_ref_id?: string; rate_limit_pps?: number }) =>
      apiFetch<DiscoveryJob>("discovery/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discovery-jobs"] }),
  });
}

export interface DiscoveryResultOverride {
  result_id: string;
  hostname?: string;
  device_type?: string;
  department?: string;
  location_id?: string;
}

export function useImportDiscoveryResults(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      result_ids: string[];
      location_id?: string;
      department?: string;
      overrides?: DiscoveryResultOverride[];
    }) => apiFetch<DiscoveryResult[]>(`discovery/${jobId}/import`, { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovery-results", jobId] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

// ---------- Topology ----------

export function useTopology() {
  return useQuery({
    queryKey: ["topology"],
    queryFn: () => apiFetch<TopologyGraph>("topology/"),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

// ---------- Locations ----------

export function useLocations() {
  return useQuery({
    queryKey: ["locations"],
    queryFn: () => apiFetch<Location[]>("locations/"),
  });
}

// ---------- Users ----------

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => apiFetch<User[]>("users/"),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; password: string; full_name?: string; role: string }) =>
      apiFetch<User>("users/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      apiFetch<User>(`users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}

// ---------- Network Detective ----------

export function useDetectiveSearch(q: string) {
  return useQuery({
    queryKey: ["detective-search", q],
    queryFn: () => apiFetch<DetectiveSearchResult>(`detective/search${qs({ q })}`),
    enabled: q.trim().length > 0,
  });
}

export function useDeviceInvestigation(deviceId: string) {
  return useQuery({
    queryKey: ["detective", deviceId],
    queryFn: () => apiFetch<DeviceInvestigation>(`detective/${deviceId}`),
    enabled: Boolean(deviceId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useDeviceAddresses(deviceId: string) {
  return useQuery({
    queryKey: ["device-addresses", deviceId],
    queryFn: () => apiFetch<DeviceAddress[]>(`devices/${deviceId}/addresses`),
    enabled: Boolean(deviceId),
  });
}

// ---------- Incidents ----------

export function useIncidents(filters: { status?: string; confidence?: string; device_id?: string } = {}) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => apiFetch<Incident[]>(`incidents/${qs(filters)}`),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useIncident(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => apiFetch<IncidentDetail>(`incidents/${incidentId}`),
    enabled: Boolean(incidentId),
    refetchInterval: LIVE_REFETCH_MS,
  });
}

export function useUpdateIncident(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { confidence?: string; status?: string; suspected_device_id?: string }) =>
      apiFetch<Incident>(`incidents/${incidentId}`, { method: "PATCH", body: JSON.stringify(payload) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["incidents"] });
      qc.invalidateQueries({ queryKey: ["incident", incidentId] });
    },
  });
}

export { ApiError, apiFetch };
