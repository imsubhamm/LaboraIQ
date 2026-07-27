output "vpc_id" {
  value = aws_vpc.main.id
}
output "database_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}
output "database_secret_arn" {
  value     = aws_db_instance.postgres.master_user_secret[0].secret_arn
  sensitive = true
}
output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}
output "evidence_bucket" {
  value = aws_s3_bucket.evidence.id
}
output "raw_messages_bucket" {
  value = aws_s3_bucket.raw_messages.id
}
output "integration_queue_url" {
  value = aws_sqs_queue.integration.url
}
output "dead_letter_queue_url" {
  value = aws_sqs_queue.dead_letter.url
}
output "ecs_cluster_arn" {
  value = aws_ecs_cluster.application.arn
}
