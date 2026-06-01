# variables.tf
variable "bucket_name" {
  description = "Base name for the S3 bucket (will be suffixed with environment)"
  type        = string
  default     = "secure-pipeline-assets"
}

variable "environment" {
  description = "Environment (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "ap-south-1"
}

variable "log_retention_days" {
  description = "CloudWatch log retention. Use 30 for demos, 365+ for prod."
  type        = number
  default     = 365
}

