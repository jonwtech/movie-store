variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "movie-store"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for movie data"
  type        = string
  default     = ""
}

variable "allowed_provider_accounts" {
  description = "List of AWS account IDs allowed to upload data"
  type        = list(string)
  default     = []
}

variable "notification_email" {
  description = "Email address for validation alerts"
  type        = string
  default     = ""
}

variable "eks_cluster_name" {
  description = "Name of the existing EKS cluster"
  type        = string
  default     = ""
}