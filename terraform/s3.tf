# Generate unique bucket name if not provided
locals {
  bucket_name = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-movie-data-${var.environment}-${random_id.bucket_suffix.hex}"
}

resource "random_id" "bucket_suffix" {
  byte_length = 8
}

# S3 bucket for movie data from providers
resource "aws_s3_bucket" "movie_data" {
  bucket = local.bucket_name
}

# Enable versioning for data protection
resource "aws_s3_bucket_versioning" "movie_data" {
  bucket = aws_s3_bucket.movie_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "movie_data" {
  bucket = aws_s3_bucket.movie_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "movie_data" {
  bucket = aws_s3_bucket.movie_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "movie_data" {
  bucket = aws_s3_bucket.movie_data.id

  rule {
    id     = "movie_data_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    # Move to Intelligent Tiering after 30 days
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    # Move to Glacier after 90 days
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Clean up incomplete multipart uploads
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    # Keep non-current versions for 30 days
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# Enable logging
resource "aws_s3_bucket_logging" "movie_data" {
  bucket = aws_s3_bucket.movie_data.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "movie-data-access-logs/"
}

# Separate bucket for access logs
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.bucket_name}-access-logs"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 event notification configuration - sends events directly to SQS
resource "aws_s3_bucket_notification" "movie_data_events" {
  bucket = aws_s3_bucket.movie_data.id

  queue {
    queue_arn = aws_sqs_queue.movie_data_events.arn
    events    = ["s3:ObjectCreated:*"]

    # Only trigger for JSON files in providers/ directory
    filter_prefix = "providers/"
    filter_suffix = ".json"
  }

  depends_on = [aws_sqs_queue_policy.movie_data_events]
}
