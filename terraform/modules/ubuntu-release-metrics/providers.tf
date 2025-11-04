terraform {
  required_version = ">= 1.0"
  required_providers {
    juju = {
      version = "0.15.0"
      source  = "juju/juju"
    }
  }
}
