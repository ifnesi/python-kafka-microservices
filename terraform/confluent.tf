# -------------------------------------------------------
# Confluent Cloud Organization
# -------------------------------------------------------
data "confluent_organization" "cc_org" {
    # This data source fetches the organization details
}

# -------------------------------------------------------
# Confluent Cloud Environment
# -------------------------------------------------------
resource "confluent_environment" "cc_pizza_env" {
    display_name = "env-${var.demo_prefix}-${random_id.id.hex}"
    stream_governance {
        package = var.stream_governance
    }
}

output "cc_environment_id" {
    description = "Confluent Cloud Environment ID"
    value       = confluent_environment.cc_pizza_env.id
}

# --------------------------------------------------------
# Apache Kafka Cluster (BASIC)
# --------------------------------------------------------
resource "confluent_kafka_cluster" "cc_kafka_cluster" {
    display_name = "kafka-${var.demo_prefix}-${random_id.id.hex}"
    cloud        = var.cc_cloud_provider
    region       = var.cloud_region
    availability = var.cc_availability
    basic {}
    environment {
        id = confluent_environment.cc_pizza_env.id
    }
}

output "cc_kafka_cluster_id" {
    description = "Kafka Cluster ID"
    value       = confluent_kafka_cluster.cc_kafka_cluster.id
}

output "cc_kafka_cluster_bootstrap" {
    description = "Kafka Cluster Bootstrap Endpoint"
    value       = confluent_kafka_cluster.cc_kafka_cluster.bootstrap_endpoint
}

# --------------------------------------------------------
# Schema Registry Cluster
# --------------------------------------------------------
data "confluent_schema_registry_cluster" "sr" {
    environment {
        id = confluent_environment.cc_pizza_env.id
    }
    depends_on = [
        confluent_kafka_cluster.cc_kafka_cluster
    ]
}

output "sr_cluster_id" {
    description = "Schema Registry Cluster ID"
    value       = data.confluent_schema_registry_cluster.sr.id
}

output "sr_cluster_url" {
    description = "Schema Registry REST Endpoint"
    value       = data.confluent_schema_registry_cluster.sr.rest_endpoint
}

# --------------------------------------------------------
# Service Account
# --------------------------------------------------------
resource "confluent_service_account" "app_main" {
    display_name = "sa-${var.demo_prefix}-${random_id.id.hex}"
    description  = "Service account for pizza microservices demo"
}

output "service_account_id" {
    description = "Service Account ID"
    value       = confluent_service_account.app_main.id
}

# --------------------------------------------------------
# Role Binding - Environment Admin
# --------------------------------------------------------
resource "confluent_role_binding" "app_main_env_admin" {
    principal   = "User:${confluent_service_account.app_main.id}"
    role_name   = "EnvironmentAdmin"
    crn_pattern = confluent_environment.cc_pizza_env.resource_name
}

# --------------------------------------------------------
# API Keys
# --------------------------------------------------------
# Kafka API Key
resource "confluent_api_key" "app_kafka_key" {
    display_name = "api-key-kafka-${var.demo_prefix}-${random_id.id.hex}"
    description  = "Kafka API Key for pizza microservices"
    owner {
        id          = confluent_service_account.app_main.id
        api_version = confluent_service_account.app_main.api_version
        kind        = confluent_service_account.app_main.kind
    }
    managed_resource {
        id          = confluent_kafka_cluster.cc_kafka_cluster.id
        api_version = confluent_kafka_cluster.cc_kafka_cluster.api_version
        kind        = confluent_kafka_cluster.cc_kafka_cluster.kind
        environment {
            id = confluent_environment.cc_pizza_env.id
        }
    }
    depends_on = [
        confluent_role_binding.app_main_env_admin
    ]
}

output "kafka_api_key" {
    description = "Kafka API Key"
    value       = confluent_api_key.app_kafka_key.id
}

output "kafka_api_secret" {
    description = "Kafka API Secret"
    value       = confluent_api_key.app_kafka_key.secret
    sensitive   = true
}

# Schema Registry API Key
resource "confluent_api_key" "sr_key" {
    display_name = "api-key-sr-${var.demo_prefix}-${random_id.id.hex}"
    description  = "Schema Registry API Key for pizza microservices"
    owner {
        id          = confluent_service_account.app_main.id
        api_version = confluent_service_account.app_main.api_version
        kind        = confluent_service_account.app_main.kind
    }
    managed_resource {
        id          = data.confluent_schema_registry_cluster.sr.id
        api_version = data.confluent_schema_registry_cluster.sr.api_version
        kind        = data.confluent_schema_registry_cluster.sr.kind
        environment {
            id = confluent_environment.cc_pizza_env.id
        }
    }
    depends_on = [
        confluent_role_binding.app_main_env_admin,
        data.confluent_schema_registry_cluster.sr
    ]
}

output "sr_api_key" {
    description = "Schema Registry API Key"
    value       = confluent_api_key.sr_key.id
}

output "sr_api_secret" {
    description = "Schema Registry API Secret"
    value       = confluent_api_key.sr_key.secret
    sensitive   = true
}

# Flink API Key
resource "confluent_api_key" "flink_api_key" {
    display_name = "api-key-flink-${var.demo_prefix}-${random_id.id.hex}"
    description  = "Flink API Key for pizza microservices"
    owner {
        id          = confluent_service_account.app_main.id
        api_version = confluent_service_account.app_main.api_version
        kind        = confluent_service_account.app_main.kind
    }
    managed_resource {
        id          = data.confluent_flink_region.flink_region.id
        api_version = data.confluent_flink_region.flink_region.api_version
        kind        = data.confluent_flink_region.flink_region.kind
        environment {
            id = confluent_environment.cc_pizza_env.id
        }
    }
    depends_on = [
        confluent_role_binding.app_main_env_admin
    ]
}

output "flink_api_key" {
    description = "Flink API Key"
    value       = confluent_api_key.flink_api_key.id
}

output "flink_api_secret" {
    description = "Flink API Secret"
    value       = confluent_api_key.flink_api_key.secret
    sensitive   = true
}

# --------------------------------------------------------
# Kafka Topics with Schema Configuration
# --------------------------------------------------------
variable "topics" {
    type = map(object({
        partitions_count = number
        cleanup_policy   = string
        retention_ms     = string
        needs_schema     = bool
    }))
    default = {
        # topic_name      = {partitions_count, cleanup_policy, retention_ms, needs_schema}
        pizza-pending     = { partitions_count = 6, cleanup_policy = "delete", retention_ms = "604800000", needs_schema = true }
        pizza-ordered     = { partitions_count = 6, cleanup_policy = "delete", retention_ms = "604800000", needs_schema = true }
        pizza-assembled   = { partitions_count = 6, cleanup_policy = "delete", retention_ms = "604800000", needs_schema = true }
        pizza-baked       = { partitions_count = 6, cleanup_policy = "delete", retention_ms = "604800000", needs_schema = true }
        pizza-delivered   = { partitions_count = 6, cleanup_policy = "delete", retention_ms = "604800000", needs_schema = true }
    }
}

resource "confluent_kafka_topic" "topics" {
    for_each = var.topics
    kafka_cluster {
        id = confluent_kafka_cluster.cc_kafka_cluster.id
    }
    topic_name    = each.key
    rest_endpoint = confluent_kafka_cluster.cc_kafka_cluster.rest_endpoint
    credentials {
        key    = confluent_api_key.app_kafka_key.id
        secret = confluent_api_key.app_kafka_key.secret
    }
    partitions_count = each.value.partitions_count
    config = {
        "cleanup.policy" = each.value.cleanup_policy
        "retention.ms"   = each.value.retention_ms
    }
    depends_on = [
        confluent_kafka_cluster.cc_kafka_cluster,
        confluent_api_key.app_kafka_key
    ]
}

# --------------------------------------------------------
# Avro Schemas for Topics
# --------------------------------------------------------
# Filter topics that need schemas
locals {
    topics_with_schemas = [
        for topic, config in var.topics : topic
        if config.needs_schema
    ]
}

resource "confluent_schema" "avro_schemas" {
    for_each = toset(local.topics_with_schemas)
    schema_registry_cluster {
        id = data.confluent_schema_registry_cluster.sr.id
    }
    rest_endpoint = data.confluent_schema_registry_cluster.sr.rest_endpoint
    subject_name  = "${each.value}-value"
    format        = "AVRO"
    schema        = file("${path.module}/../schemas/${each.value}.avro")
    credentials {
        key    = confluent_api_key.sr_key.id
        secret = confluent_api_key.sr_key.secret
    }
    depends_on = [
        confluent_kafka_topic.topics
    ]
}

# --------------------------------------------------------
# Flink Compute Pool (10 CFUs)
# --------------------------------------------------------
resource "confluent_flink_compute_pool" "flink_compute_pool" {
    display_name = "flink-${var.demo_prefix}-${random_id.id.hex}"
    cloud        = var.cc_cloud_provider
    region       = var.cloud_region
    max_cfu      = var.flink_max_cfu
    environment {
        id = confluent_environment.cc_pizza_env.id
    }
}

output "flink_compute_pool_id" {
    description = "Flink Compute Pool ID"
    value       = confluent_flink_compute_pool.flink_compute_pool.id
}

data "confluent_flink_region" "flink_region" {
    cloud  = var.cc_cloud_provider
    region = var.cloud_region
}

output "flink_rest_endpoint" {
    description = "Flink REST Endpoint"
    value       = data.confluent_flink_region.flink_region.rest_endpoint
}

# --------------------------------------------------------
# Flink Statement - PIZZA_STATUS Table
# --------------------------------------------------------
resource "confluent_flink_statement" "pizza_status" {
    organization {
        id = data.confluent_organization.cc_org.id
    }
    environment {
        id = confluent_environment.cc_pizza_env.id
    }
    compute_pool {
        id = confluent_flink_compute_pool.flink_compute_pool.id
    }
    principal {
        id = confluent_service_account.app_main.id
    }
    statement = file("${path.module}/flink/001_TABLE_PIZZA_STATUS.sql")
    properties = {
        "sql.current-catalog"  = confluent_environment.cc_pizza_env.id
        "sql.current-database" = confluent_kafka_cluster.cc_kafka_cluster.id
    }
    rest_endpoint = data.confluent_flink_region.flink_region.rest_endpoint
    credentials {
        key    = confluent_api_key.flink_api_key.id
        secret = confluent_api_key.flink_api_key.secret
    }
    depends_on = [
        confluent_flink_compute_pool.flink_compute_pool,
        confluent_kafka_topic.topics,
        confluent_schema.avro_schemas
    ]
}

output "flink_statement_pizza_status" {
    description = "Flink PIZZA_STATUS Statement Name"
    value       = confluent_flink_statement.pizza_status.statement_name
}

resource "confluent_flink_statement" "pizza_status_insert" {
    organization {
        id = data.confluent_organization.cc_org.id
    }
    environment {
        id = confluent_environment.cc_pizza_env.id
    }
    compute_pool {
        id = confluent_flink_compute_pool.flink_compute_pool.id
    }
    principal {
        id = confluent_service_account.app_main.id
    }
    statement = file("${path.module}/flink/002_INSERT_PIZZA_STATUS.sql")
    properties = {
        "sql.current-catalog"  = confluent_environment.cc_pizza_env.id
        "sql.current-database" = confluent_kafka_cluster.cc_kafka_cluster.id
    }
    rest_endpoint = data.confluent_flink_region.flink_region.rest_endpoint
    credentials {
        key    = confluent_api_key.flink_api_key.id
        secret = confluent_api_key.flink_api_key.secret
    }
    depends_on = [
        confluent_flink_statement.pizza_status
    ]
}

output "flink_statement_pizza_status_insert" {
    description = "Flink PIZZA_STATUS Insert Statement Name"
    value       = confluent_flink_statement.pizza_status_insert.statement_name
}

# --------------------------------------------------------
# Generate Python Kafka Config File
# --------------------------------------------------------
resource "local_file" "kafka_config" {
    filename = "${path.module}/../config_kafka/cc_demo.ini"
    content = templatefile("${path.module}/scripts/kafka_config_template.ini", {
        kafka_bootstrap_servers = replace(confluent_kafka_cluster.cc_kafka_cluster.bootstrap_endpoint, "SASL_SSL://", "")
        kafka_api_key           = confluent_api_key.app_kafka_key.id
        kafka_api_secret        = confluent_api_key.app_kafka_key.secret
        sr_url                  = data.confluent_schema_registry_cluster.sr.rest_endpoint
        sr_api_key              = confluent_api_key.sr_key.id
        sr_api_secret           = confluent_api_key.sr_key.secret
    })
    file_permission = "0600"
    depends_on = [
        confluent_api_key.app_kafka_key,
        confluent_api_key.sr_key
    ]
}
