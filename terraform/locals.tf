locals {
  func_name      = "tca${random_string.unique.result}"
  loc_for_naming = lower(replace(var.location, " ", ""))
  loc_short      = upper("${substr(local.loc_for_naming, 0, 1)}${trimprefix(trimprefix(local.loc_for_naming, "east"), "west")}")
  gh_repo        = split("/", var.gh_repo)[1]

  foundry_name     = "aif${local.func_name}"
  foundry_project  = "fp${local.func_name}"
  foundry_endpoint = "https://${local.foundry_name}.services.ai.azure.com/api/projects/${local.foundry_project}"
  foundry_base     = "https://${local.foundry_name}.services.ai.azure.com/"

  tags = {
    "managed_by" = "terraform"
    "repo"       = local.gh_repo
    "workload"   = "travel-concierge-agent"
  }
}
