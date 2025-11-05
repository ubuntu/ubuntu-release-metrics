terraform {
  required_version = ">= 1.0"
}

module "ubuntu-release-metrics" {
  source = "../modules/ubuntu-release-metrics/"
  dry_run = true
  channel = "latest/edge"
  http_proxy = ""
  https_proxy = ""
  no_proxy = ""
  model_name = "release-metrics"
}
