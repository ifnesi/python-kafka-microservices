# ----------------------------------------
# General variables
# ----------------------------------------
variable "demo_prefix" {
    description = "Prefix for resource names"
    type        = string
    default     = "pizza-demo"
}

# ----------------------------------------
# Confluent Cloud Kafka cluster variables
# ----------------------------------------
variable "cc_cloud_provider" {
    description = "Cloud Provider for Confluent resources"
    type        = string
    default     = "AWS"
}

variable "cloud_region" {
    description = "Region for Confluent resources"
    type        = string
    default     = "eu-west-1"
}

variable "cc_availability" {
    description = "Availability zone configuration"
    type        = string
    default     = "SINGLE_ZONE"
}

variable "stream_governance" {
    description = "Stream Governance package"
    type        = string
    default     = "ESSENTIALS"
}

variable "flink_max_cfu" {
    description = "Maximum CFUs for Flink compute pool"
    type        = number
    default     = 10
}

# --------------------------------------------------------
# Random ID for unique resource naming
# --------------------------------------------------------
resource "random_id" "id" {
    byte_length = 4
}
