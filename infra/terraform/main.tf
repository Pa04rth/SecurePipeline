data "aws_caller_identity" "current" {}
resource "aws_kms_key" "eks_secrets" {
  description             = "KMS key for EKS Kubernetes Secrets envelope encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Project     = "securepipe"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "eks-secrets-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountAdmin"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowEKSToUseTheKey"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "eks_secrets" {
  name          = "alias/securepipe-eks-secrets"
  target_key_id = aws_kms_key.eks_secrets.key_id
}


module "vpc" {
  source = "../vendor/terraform-aws-vpc"


  name = "securepipe-vpc"
  cidr = "10.0.0.0/16"


  azs             = ["ap-south-1a", "ap-south-1b"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.20.0/24"]


  enable_nat_gateway     = true
  single_nat_gateway     = true
  one_nat_gateway_per_az = false

  # VPC flow logs
  enable_flow_log                                 = true
  create_flow_log_cloudwatch_log_group            = true
  create_flow_log_cloudwatch_iam_role             = true
  flow_log_max_aggregation_interval               = 60
  flow_log_cloudwatch_log_group_retention_in_days = var.log_retention_days



  # EKS-required subnet tags

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = {
    Project     = "securepipe"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}



module "eks" {
  source = "../vendor/terraform-aws-eks"


  cluster_name    = "securepipe"
  cluster_version = "1.30"


  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets # nodes go in private
  control_plane_subnet_ids = module.vpc.private_subnets # control plane ENIs

  # API endpoint: public (CIDR-restricted) 
  #Public endpoint required for laptop kubectl access during demo; mitigated by CIDR restriction to operator IP (CKV_AWS_38 passes)
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = ["106.214.8.88/32"]

  # Audit logging
  cluster_enabled_log_types = [
    "api", "audit", "authenticator", "controllerManager", "scheduler"
  ]

  cluster_encryption_config = {
    resources        = ["secrets"]
    provider_key_arn = aws_kms_key.eks_secrets.arn
  }

  create_kms_key                         = false # disable the submodule call
  cloudwatch_log_group_retention_in_days = var.log_retention_days


  enable_irsa = true

  enable_cluster_creator_admin_permissions = true

  # Managed node group
  eks_managed_node_groups = {
    primary = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.medium"] # 2 vCPU, 4GB — cheapest viable for demo
      min_size       = 1
      desired_size   = 2
      max_size       = 3

      # IMDSv2 required, no IMDSv1 fallback
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required" # ← this is IMDSv2
        http_put_response_hop_limit = 2
      }
    }
  }

  # Cluster addons
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
    # aws-ebs-csi-driver = { most_recent = true }
  }

  tags = {
    Project     = "securepipe"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
