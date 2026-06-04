#!/usr/bin/env bash
set -euo pipefail

EC2_REGION=${EC2_REGION:-ap-northeast-2}
INSTANCE_ID=${1:?usage: attach-instance-profile.sh INSTANCE_ID INSTANCE_PROFILE_NAME}
PROFILE_NAME=${2:?usage: attach-instance-profile.sh INSTANCE_ID INSTANCE_PROFILE_NAME}

ASSOCIATION_ID=$(aws ec2 describe-iam-instance-profile-associations \
  --region "$EC2_REGION" \
  --filters Name=instance-id,Values="$INSTANCE_ID" \
  --query 'IamInstanceProfileAssociations[0].AssociationId' \
  --output text)

if test "$ASSOCIATION_ID" = None; then
  aws ec2 associate-iam-instance-profile \
    --region "$EC2_REGION" \
    --instance-id "$INSTANCE_ID" \
    --iam-instance-profile Name="$PROFILE_NAME"
else
  aws ec2 replace-iam-instance-profile-association \
    --region "$EC2_REGION" \
    --association-id "$ASSOCIATION_ID" \
    --iam-instance-profile Name="$PROFILE_NAME"
fi

for attempt in $(seq 1 30); do
  STATE=$(aws ec2 describe-iam-instance-profile-associations \
    --region "$EC2_REGION" \
    --filters Name=instance-id,Values="$INSTANCE_ID" \
    --query 'IamInstanceProfileAssociations[0].State' \
    --output text)
  if test "$STATE" = associated; then
    aws ec2 describe-iam-instance-profile-associations \
      --region "$EC2_REGION" \
      --filters Name=instance-id,Values="$INSTANCE_ID" \
      --query 'IamInstanceProfileAssociations[0].{State:State,Profile:IamInstanceProfile.Arn}' \
      --output table
    exit 0
  fi
  sleep 2
done

echo "Timed out waiting for instance profile association" >&2
exit 1
