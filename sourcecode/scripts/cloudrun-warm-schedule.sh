#!/usr/bin/env bash
# 建立兩個 Cloud Scheduler job，讓 backend 只在平日 10:00-18:00（台北時間）常駐 1 個實例，
# 其餘時間縮回 0（不計費）。開始時間提早 5 分鐘，讓新實例先跑完模型預載。
#
# 用法：PROJECT_ID=xxx SERVICE=<_SERVICE_NAME>-backend ./scripts/cloudrun-warm-schedule.sh
# 前置：已啟用 Cloud Scheduler API；SCHEDULER_SA 需有 roles/run.developer，
# 且能以 Cloud Run 服務的執行身分部署（roles/iam.serviceAccountUser）。
set -euo pipefail

: "${PROJECT_ID:?請設定 PROJECT_ID}"
: "${SERVICE:?請設定 SERVICE（Cloud Run backend 服務名稱）}"
REGION="${REGION:-europe-west1}"
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-asia-east1}"
SCHEDULER_SA="${SCHEDULER_SA:?請設定 SCHEDULER_SA（Scheduler 使用的服務帳號 email）}"
TZ_NAME="${TZ_NAME:-Asia/Taipei}"

URL="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/services/${SERVICE}?updateMask=template.scaling.minInstanceCount"

create_job() { # 名稱 cron 最小實例數
  local name="$1" cron="$2" min="$3"
  gcloud scheduler jobs create http "$name" \
    --project="$PROJECT_ID" --location="$SCHEDULER_LOCATION" \
    --schedule="$cron" --time-zone="$TZ_NAME" \
    --http-method=PATCH --uri="$URL" \
    --headers="Content-Type=application/json" \
    --message-body="{\"template\":{\"scaling\":{\"minInstanceCount\":${min}}}}" \
    --oauth-service-account-email="$SCHEDULER_SA" \
    --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
}

create_job "${SERVICE}-warm-on"  "55 9 * * 1-5" 1
create_job "${SERVICE}-warm-off" "0 18 * * 1-5" 0
