# SQS queue for processing movie data events
resource "aws_sqs_queue" "movie_data_events" {
  name                       = "${var.project_name}-movie-data-events-${var.environment}"
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600 # 14 days
  receive_wait_time_seconds  = 20      # Long polling
  visibility_timeout_seconds = 300     # 5 minutes

  # Enable server-side encryption
  # kms_master_key_id = "alias/aws/sqs"

  # Redrive policy for failed messages
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.movie_data_events_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name = "${var.project_name}-movie-data-events-${var.environment}"
  }
}

# Dead letter queue for failed messages
resource "aws_sqs_queue" "movie_data_events_dlq" {
  name                      = "${var.project_name}-movie-data-events-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days
  # kms_master_key_id         = "alias/aws/sqs"

  tags = {
    Name = "${var.project_name}-movie-data-events-dlq-${var.environment}"
  }
}

# SNS topic for DLQ notifications
resource "aws_sns_topic" "movie_data_dlq_alerts" {
  name = "${var.project_name}-movie-data-dlq-alerts-${var.environment}"

  tags = {
    Name = "${var.project_name}-movie-data-dlq-alerts-${var.environment}"
  }
}

# CloudWatch alarm for DLQ messages
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project_name}-movie-data-dlq-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0"
  alarm_description   = "This metric monitors dlq message count"
  alarm_actions       = [aws_sns_topic.movie_data_dlq_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.movie_data_events_dlq.name
  }
}

# IAM policy for S3 to send messages to SQS
resource "aws_sqs_queue_policy" "movie_data_events" {
  queue_url = aws_sqs_queue.movie_data_events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.movie_data_events.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.movie_data.arn
          }
        }
      }
    ]
  })
}