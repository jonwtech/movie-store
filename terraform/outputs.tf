output "s3_bucket_name" {
  description = "Name of the S3 bucket for movie data"
  value       = aws_s3_bucket.movie_data.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for movie data"
  value       = aws_s3_bucket.movie_data.arn
}

output "sqs_queue_url" {
  description = "URL of the SQS queue for processing movie data events"
  value       = aws_sqs_queue.movie_data_events.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue for processing movie data events"
  value       = aws_sqs_queue.movie_data_events.arn
}

output "data_processor_role_arn" {
  description = "ARN of the IAM role for data processing service"
  value       = aws_iam_role.data_processor.arn
}

output "movie_data_provider_role_arn" {
  description = "ARN of the IAM role for movie data providers"
  value       = length(aws_iam_role.movie_data_provider) > 0 ? aws_iam_role.movie_data_provider[0].arn : "No provider accounts configured"
}

output "provider_access_instructions" {
  description = "Instructions for movie data providers"
  value       = length(var.allowed_provider_accounts) > 0 ? "Providers should assume role ${aws_iam_role.movie_data_provider[0].arn} with external ID '${var.project_name}-provider-access' and upload JSON files to s3://${aws_s3_bucket.movie_data.bucket}/providers/" : "Configure allowed_provider_accounts variable to enable provider access"
}

output "dlq_sns_topic_arn" {
  description = "SNS topic ARN for DLQ alerts"
  value       = aws_sns_topic.movie_data_dlq_alerts.arn
}

output "dlq_queue_url" {
  description = "URL of the Dead Letter Queue"
  value       = aws_sqs_queue.movie_data_events_dlq.url
}

# Database outputs
output "database_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "database_secret_arn" {
  description = "ARN of database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address != "" ? aws_elasticache_replication_group.main.configuration_endpoint_address : aws_elasticache_replication_group.main.primary_endpoint_address
  sensitive   = true
}

output "redis_secret_arn" {
  description = "ARN of Redis credentials secret"
  value       = aws_secretsmanager_secret.redis_credentials.arn
}

# EKS cluster information (if provided)
output "eks_cluster_info" {
  description = "EKS cluster information"
  value = var.eks_cluster_name != "" ? {
    cluster_name = var.eks_cluster_name
    vpc_id       = data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].vpc_id
    oidc_issuer  = data.aws_eks_cluster.existing[0].identity[0].oidc[0].issuer
  } : null 
}
