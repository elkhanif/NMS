import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    NETWORK_ENGINEER = "NETWORK_ENGINEER"
    IT_SUPPORT = "IT_SUPPORT"
    VIEWER = "VIEWER"


class DeviceType(str, enum.Enum):
    ROUTER = "ROUTER"
    FIREWALL = "FIREWALL"
    SWITCH = "SWITCH"
    ACCESS_POINT = "ACCESS_POINT"
    SERVER = "SERVER"
    VM = "VM"
    PRINTER = "PRINTER"
    CCTV_NVR = "CCTV_NVR"
    IOT_DEVICE = "IOT_DEVICE"
    GENERIC = "GENERIC"


class DeviceStatus(str, enum.Enum):
    UP = "UP"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class CheckType(str, enum.Enum):
    ICMP = "ICMP"
    TCP = "TCP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    SNMP = "SNMP"


class CredentialType(str, enum.Enum):
    SNMPV2C = "SNMPV2C"
    SNMPV3 = "SNMPV3"
    HTTP_BASIC = "HTTP_BASIC"


class MetricType(str, enum.Enum):
    AVAILABILITY = "AVAILABILITY"
    RESPONSE_TIME = "RESPONSE_TIME"
    PACKET_LOSS = "PACKET_LOSS"
    CPU_USAGE = "CPU_USAGE"
    MEMORY_USAGE = "MEMORY_USAGE"
    DISK_USAGE = "DISK_USAGE"
    TEMPERATURE = "TEMPERATURE"
    UPTIME = "UPTIME"


class InterfaceStatus(str, enum.Enum):
    UP = "UP"
    DOWN = "DOWN"
    TESTING = "TESTING"
    UNKNOWN = "UNKNOWN"


class RelationshipType(str, enum.Enum):
    UPLINK = "UPLINK"
    DOWNLINK = "DOWNLINK"
    PEER = "PEER"


class AlertSeverity(str, enum.Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class AlertScope(str, enum.Enum):
    GLOBAL = "GLOBAL"
    DEVICE_TYPE = "DEVICE_TYPE"
    DEVICE = "DEVICE"


class AlertOperator(str, enum.Enum):
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    EQ = "EQ"


class RuleKind(str, enum.Enum):
    METRIC_THRESHOLD = "METRIC_THRESHOLD"
    DEVICE_UNREACHABLE = "DEVICE_UNREACHABLE"
    INTERFACE_DOWN = "INTERFACE_DOWN"


class EventSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EventType(str, enum.Enum):
    DEVICE_DISCOVERED = "DEVICE_DISCOVERED"
    DEVICE_DOWN = "DEVICE_DOWN"
    DEVICE_RECOVERED = "DEVICE_RECOVERED"
    INTERFACE_DOWN = "INTERFACE_DOWN"
    INTERFACE_RECOVERED = "INTERFACE_RECOVERED"
    CPU_THRESHOLD_EXCEEDED = "CPU_THRESHOLD_EXCEEDED"
    MEMORY_THRESHOLD_EXCEEDED = "MEMORY_THRESHOLD_EXCEEDED"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    ALERT_ACKNOWLEDGED = "ALERT_ACKNOWLEDGED"
    ALERT_RESOLVED = "ALERT_RESOLVED"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"


class MonitoringJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class DiscoveryJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
