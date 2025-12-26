# IAM role for the data processor service (will run in EKS)
resource "aws_iam_role" "data_processor" {
  name = "${var.project_name}-data-processor-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      },
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = var.eks_cluster_name != "" ? "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${replace(data.aws_eks_cluster.existing[0].identity[0].oidc[0].issuer, "https://", "")}" : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/PLACEHOLDER-FOR-EKS-OIDC"
        }
        Condition = var.eks_cluster_name != "" ? {
          StringEquals = {
            "${replace(data.aws_eks_cluster.existing[0].identity[0].oidc[0].issuer, "https://", "")}:sub" = [
              "system:serviceaccount:movie-store:data-processor",
              "system:serviceaccount:movie-store:api-service"
            ]
            "${replace(data.aws_eks_cluster.existing[0].identity[0].oidc[0].issuer, "https://", "")}:aud" = "sts.amazonaws.com"
          }
          } : {
          StringEquals = {
            "PLACEHOLDER-FOR-EKS-OIDC:sub" = [
              "system:serviceaccount:movie-store:data-processor",
              "system:serviceaccount:movie-store:api-service"
            ]
            "PLACEHOLDER-FOR-EKS-OIDC:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-data-processor-${var.environment}"
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for existing EKS cluster
data "aws_eks_cluster" "existing" {
  count = var.eks_cluster_name != "" ? 1 : 0
  name  = var.eks_cluster_name
}

# Policy for Python services (API and data processor)
resource "aws_iam_policy" "python_services" {
  name        = "${var.project_name}-python-services-${var.environment}"
  description = "Policy for Python API and data processor services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [
          aws_sqs_queue.movie_data_events.arn,
          aws_sqs_queue.movie_data_events_dlq.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.movie_data.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.movie_data.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/database-v2-*",
          "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/redis-v2-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/${var.project_name}-${var.environment}/*"
      }
    ]
  })
}

# Attach policy to services role
resource "aws_iam_role_policy_attachment" "python_services" {
  role       = aws_iam_role.data_processor.name
  policy_arn = aws_iam_policy.python_services.arn
}

# IAM role for movie data providers
resource "aws_iam_role" "movie_data_provider" {
  count = length(var.allowed_provider_accounts) > 0 ? 1 : 0
  name  = "${var.project_name}-movie-data-provider-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = [for account in var.allowed_provider_accounts : "arn:aws:iam::${account}:root"]
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "${var.project_name}-provider-access"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-movie-data-provider-${var.environment}"
  }
}

# Policy for providers to upload movie data
resource "aws_iam_policy" "movie_data_provider" {
  count       = length(var.allowed_provider_accounts) > 0 ? 1 : 0
  name        = "${var.project_name}-movie-data-provider-${var.environment}"
  description = "Policy for movie data providers to upload files"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.movie_data.arn}/providers/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.movie_data.arn
        Condition = {
          StringLike = {
            "s3:prefix" = "providers/*"
          }
        }
      }
    ]
  })
}

# Attach policy to provider role
resource "aws_iam_role_policy_attachment" "movie_data_provider" {
  count      = length(var.allowed_provider_accounts) > 0 ? 1 : 0
  role       = aws_iam_role.movie_data_provider[0].name
  policy_arn = aws_iam_policy.movie_data_provider[0].arn
}