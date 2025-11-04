resource "juju_application" "ubuntu-release-metrics-collector" {
  name = "ubuntu-release-metrics-collector"
  model = var.model_name

  charm {
    name = "ubuntu-release-metrics-collector"
    channel = var.channel
    base = var.base
  }

  units = 1

  config = {
    dry_run             = var.dry_run
    influxdb_hostname   = var.influxdb_hostname
    influxdb_port       = var.influxdb_port
    influxdb_password   = var.influxdb_password
    influxdb_database   = var.influxdb_database
    influxdb_username   = var.influxdb_username
    http_proxy          = var.http_proxy
    https_proxy         = var.https_proxy
    no_proxy            = var.no_proxy
  }
}
