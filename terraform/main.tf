module "etl_infrastructure" {
  source = "./modules/etl_infrastructure"

  project_id_base    = var.project_id_base
  project_name       = var.project_name
  billing_account_id = var.billing_account_id
  region             = var.region
  zone               = var.zone
  environment        = var.environment
  instance_number    = var.instance_number
  bucket_suffix      = var.bucket_suffix
  resource_type      = var.resource_type
  github_repository  = var.github_repository
}
