variable "channel" {
    description = "channel for metrics charm"
    type = string
    default = "latest/stable"
}

variable "base" {
    description = "base for metrics charm to be deployed onto"
    type = string
    default = "ubuntu@24.04"
}

variable "model_name" {
    description = "name of juju model to deploy in"
    type = string
}

variable "dry_run" {
    description = "dry run"
    type = bool
}

variable "influxdb_hostname" {
    description = "hostname for influxdb server to send metrics to"
    type = string
    default = "ubuntu-release-kpi-influx.internal"
}

variable "influxdb_port" {
    description = "port for influxdb server to send metrics to"
    type = number
    default = 8086
}

variable "influxdb_password" {
    description = "password for influxdb server to send metrics to"
    type = string
    default = "XXX"
}

variable "influxdb_database" {
    description = "database name in influxdb server to send metrics to"
    type = string
    default = "metrics"
}

variable "influxdb_username" {
    description = "username for influxdb server to send metrics to"
    type = string
    default = "metrics"
}

variable "http_proxy" {
    description = "http_proxy environment variable for the metrics collectors"
    type = string
    default = "http://squid.internal:3128"
}

variable "https_proxy" {
    description = "https_proxy environment variable for the metrics collectors"
    type = string
    default = "http://squid.internal:3128"
}

variable "no_proxy" {
    description = "no_proxy environment variable for the metrics collectors"
    type = string
    default = "127.0.0.1,::1,localhost,10.0.0.0/8,canonical.com,ubuntu.com,launchpad.net,internal"
}
