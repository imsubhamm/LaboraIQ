locals { name = "laboraiq-${var.environment}" }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${local.name}-vpc" }
}

resource "aws_subnet" "private" {
  count             = length(var.private_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags              = { Name = "${local.name}-private-${count.index + 1}" }
}

resource "aws_security_group" "database" {
  name        = "${local.name}-database"
  description = "PostgreSQL access from application compute only"
  vpc_id      = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "application" {
  name        = "${local.name}-application"
  description = "Application compute security group"
  vpc_id      = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "database_from_application" {
  type                     = "ingress"
  security_group_id        = aws_security_group.database.id
  source_security_group_id = aws_security_group.application.id
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
}

resource "aws_kms_key" "platform" {
  description             = "${local.name} platform data key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms.json
}
resource "aws_kms_alias" "platform" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.platform.key_id
}

data "aws_caller_identity" "current" {}
data "aws_iam_policy_document" "kms" {
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}
resource "aws_db_instance" "postgres" {
  identifier                      = "${local.name}-postgres"
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = var.db_instance_class
  allocated_storage               = var.db_allocated_storage
  max_allocated_storage           = var.db_max_allocated_storage
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.platform.arn
  db_name                         = "laboraiq"
  username                        = "laboraiq_admin"
  manage_master_user_password     = true
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [aws_security_group.database.id]
  backup_retention_period         = var.db_backup_retention_days
  copy_tags_to_snapshot           = true
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = var.environment != "production"
  final_snapshot_identifier       = var.environment == "production" ? "${local.name}-final" : null
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.platform.arn
}

resource "aws_secretsmanager_secret" "application" {
  name        = "${local.name}/application"
  kms_key_id  = aws_kms_key.platform.arn
  description = "Runtime application configuration; values populated outside Terraform."
}

resource "aws_s3_bucket" "evidence" { bucket_prefix = "${local.name}-evidence-" }
resource "aws_s3_bucket" "raw_messages" { bucket_prefix = "${local.name}-raw-messages-" }
resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_versioning" "raw_messages" {
  bucket = aws_s3_bucket.raw_messages.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.platform.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "raw_messages" {
  bucket = aws_s3_bucket.raw_messages.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.platform.arn
      sse_algorithm     = "aws:kms"
    }
  }
}
resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_public_access_block" "raw_messages" {
  bucket                  = aws_s3_bucket.raw_messages.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${local.name}-integration-dlq"
  kms_master_key_id         = aws_kms_key.platform.arn
  message_retention_seconds = 1209600
}
resource "aws_sqs_queue" "integration" {
  name                       = "${local.name}-integration"
  kms_master_key_id          = aws_kms_key.platform.arn
  visibility_timeout_seconds = 120
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dead_letter.arn, maxReceiveCount = 5 })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/laboraiq/${var.environment}/api"
  retention_in_days = var.environment == "production" ? 365 : 30
  kms_key_id        = aws_kms_key.platform.arn
}
resource "aws_cloudwatch_log_group" "web" {
  name              = "/laboraiq/${var.environment}/web"
  retention_in_days = var.environment == "production" ? 365 : 30
  kms_key_id        = aws_kms_key.platform.arn
}
resource "aws_cloudwatch_metric_alarm" "queue_age" {
  alarm_name          = "${local.name}-queue-age"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 600
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { QueueName = aws_sqs_queue.integration.name }
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}
resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${local.name}-database-free-storage"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 5368709120
  comparison_operator = "LessThanThreshold"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.postgres.id }
  alarm_actions       = var.alarm_sns_topic_arn == "" ? [] : [var.alarm_sns_topic_arn]
}

# Compute boundary: task definitions, load balancers and autoscaling are added with
# the first deployable image and approved ingress design.
resource "aws_ecs_cluster" "application" {
  name = "${local.name}-application"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
