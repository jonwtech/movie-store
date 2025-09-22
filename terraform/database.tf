# Data source for existing EKS cluster VPC (if provided)
data "aws_eks_cluster" "cluster_vpc" {
  count = var.eks_cluster_name != "" ? 1 : 0
  name  = var.eks_cluster_name
}

# Always create dedicated database subnets for security isolation

# VPC for database resources (only if EKS cluster not provided)
resource "aws_vpc" "main" {
  count = var.eks_cluster_name == "" ? 1 : 0

  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

# Dedicated private subnets for databases (one per AZ for maximum availability)
resource "aws_subnet" "database_private" {
  count = length(data.aws_availability_zones.available.names)

  vpc_id            = var.eks_cluster_name != "" ? data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].vpc_id : aws_vpc.main[0].id
  cidr_block        = var.eks_cluster_name != "" ? "10.0.${count.index + 10}.0/24" : "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-database-private-${count.index + 1}-${var.environment}"
    Type = "database"
    AZ   = data.aws_availability_zones.available.names[count.index]
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# DB subnet group - using dedicated database subnets
resource "aws_db_subnet_group" "main" {
  name = "${var.project_name}-db-subnet-group-${var.environment}"

  subnet_ids = aws_subnet.database_private[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group-${var.environment}"
  }
}

# ElastiCache subnet group - using dedicated database subnets
resource "aws_elasticache_subnet_group" "main" {
  name = "${var.project_name}-cache-subnet-group-${var.environment}"

  subnet_ids = aws_subnet.database_private[*].id

  tags = {
    Name = "${var.project_name}-cache-subnet-group-${var.environment}"
  }
}

# Security group for database access
resource "aws_security_group" "database" {
  name_prefix = "${var.project_name}-database-${var.environment}"
  description = "Security group for RDS PostgreSQL database"

  vpc_id = var.eks_cluster_name != "" ? data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].vpc_id : aws_vpc.main[0].id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = var.eks_cluster_name != "" ? null : ["10.0.0.0/16"]
    security_groups = var.eks_cluster_name != "" ? [data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].cluster_security_group_id] : null
    description     = "PostgreSQL access from application services"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "${var.project_name}-database-sg-${var.environment}"
  }
}

# Security group for Redis cache
resource "aws_security_group" "cache" {
  name_prefix = "${var.project_name}-cache-${var.environment}"
  description = "Security group for ElastiCache Redis"

  vpc_id = var.eks_cluster_name != "" ? data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].vpc_id : aws_vpc.main[0].id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    cidr_blocks     = var.eks_cluster_name != "" ? null : ["10.0.0.0/16"]
    security_groups = var.eks_cluster_name != "" ? [data.aws_eks_cluster.cluster_vpc[0].vpc_config[0].cluster_security_group_id] : null
    description     = "Redis access from application services"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "${var.project_name}-cache-sg-${var.environment}"
  }
}

# Random password for database
resource "random_password" "db_password" {
  length  = 16
  special = true
}

# Store database credentials in Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.project_name}/${var.environment}/database-v2"
  description             = "Database credentials for movie store"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-db-credentials-${var.environment}"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  secret_string = jsonencode({
    username = "moviestore"
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.main.endpoint
    port     = aws_db_instance.main.port
    dbname   = aws_db_instance.main.db_name
  })
}

# RDS PostgreSQL instance
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-db-${var.environment}"

  # Engine configuration
  engine         = "postgres"
  engine_version = "15.8"
  instance_class = var.environment == "prod" ? "db.r5.large" : "db.t3.micro"

  # Database configuration
  db_name  = "moviestore"
  username = "moviestore"
  password = random_password.db_password.result

  # Storage configuration
  allocated_storage     = var.environment == "prod" ? 100 : 20
  max_allocated_storage = var.environment == "prod" ? 1000 : 100
  storage_type          = "gp3"
  storage_encrypted     = true

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false

  # High availability configuration
  multi_az                = var.environment == "prod"
  backup_retention_period = var.environment == "prod" ? 7 : 3
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  # Performance configuration
  performance_insights_enabled = var.environment == "prod"
  monitoring_interval          = var.environment == "prod" ? 60 : 0

  # Security configuration
  deletion_protection       = var.environment == "prod"
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}" : null

  # Parameter group for optimizations
  parameter_group_name = aws_db_parameter_group.main.name

  tags = {
    Name = "${var.project_name}-database-${var.environment}"
  }
}

# Database parameter group for performance tuning
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "${var.project_name}-db-params-${var.environment}"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = var.environment == "prod" ? "1000" : "100"
  }

  parameter {
    name         = "max_connections"
    value        = var.environment == "prod" ? "200" : "100"
    apply_method = "pending-reboot"
  }

  tags = {
    Name = "${var.project_name}-db-params-${var.environment}"
  }
}

# ElastiCache Redis cluster
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-redis-${var.environment}"
  description          = "Redis cache for movie store"

  # Node configuration
  node_type            = var.environment == "prod" ? "cache.r6g.large" : "cache.t3.micro"
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  # Cluster configuration
  num_cache_clusters         = var.environment == "prod" ? 3 : 1
  automatic_failover_enabled = var.environment == "prod" ? true : false
  multi_az_enabled           = var.environment == "prod" ? true : false

  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.cache.id]

  # Engine configuration
  engine_version             = "7.0"
  auto_minor_version_upgrade = true

  # Security configuration
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  # auth_token can be set here if needed for production security

  # Backup configuration
  snapshot_retention_limit = var.environment == "prod" ? 5 : 1
  snapshot_window          = "03:00-05:00"
  maintenance_window       = "sun:05:00-sun:07:00"

  # Monitoring
  notification_topic_arn = aws_sns_topic.movie_data_dlq_alerts.arn

  tags = {
    Name = "${var.project_name}-redis-${var.environment}"
  }
}

# Redis parameter group for optimization
resource "aws_elasticache_parameter_group" "main" {
  family = "redis7"
  name   = "${var.project_name}-redis-params-${var.environment}"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = {
    Name = "${var.project_name}-redis-params-${var.environment}"
  }
}

# Store Redis connection details in Secrets Manager
resource "aws_secretsmanager_secret" "redis_credentials" {
  name                    = "${var.project_name}/${var.environment}/redis-v2"
  description             = "Redis connection details for movie store"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project_name}-redis-credentials-${var.environment}"
  }
}

resource "aws_secretsmanager_secret_version" "redis_credentials" {
  secret_id = aws_secretsmanager_secret.redis_credentials.id

  secret_string = jsonencode({
    host         = aws_elasticache_replication_group.main.configuration_endpoint_address != "" ? aws_elasticache_replication_group.main.configuration_endpoint_address : aws_elasticache_replication_group.main.primary_endpoint_address
    port         = aws_elasticache_replication_group.main.port
    engine       = "redis"
    cluster_mode = var.environment == "prod" ? true : false
  })
}