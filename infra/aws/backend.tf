terraform {
  backend "s3" {
    bucket       = "auto-shop-tfstate-035611741563-use1"
    key          = "auto-shop-system/infra/aws/staging/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
