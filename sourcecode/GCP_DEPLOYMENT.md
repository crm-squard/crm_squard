# GCP 部署與執行指南 (Google Cloud Platform Deployment Guide)

本專案支援以 Docker 容器化技術部署至 GCP（Google Cloud Platform）。
主要提供兩種執行方式：
1. **Cloud Run**（推薦：Serverless 無伺服器架構，自動擴充、用多少算多少）
2. **Compute Engine VM**（使用 Docker Compose 一鍵啟動前後端）

---

## 方式 A：部署至 Cloud Run (推薦 Serverless 部署)

### 前置準備
1. 安裝 [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)。
2. 在 Google Cloud Console 建立專案，並登入 `gcloud`：
   ```bash
   gcloud auth login
   gcloud config set project <YOUR_GCP_PROJECT_ID>
   ```
3. 啟用必要 API 服務：
   ```bash
   gcloud services enable run.googleapis.com \
                          artifactregistry.googleapis.com \
                          cloudbuild.googleapis.com
   ```

---

### 步驟 1：部署 Backend 至 Cloud Run

1. 切換至 `sourcecode/backend` 目錄並提交建置：
   ```bash
   cd sourcecode/backend
   
   # 建置並推送 Docker 鏡像
   gcloud builds submit --tag gcr.io/<YOUR_GCP_PROJECT_ID>/crm-backend:latest .
   
   # 部署至 Cloud Run
   gcloud run deploy crm-backend \
     --image gcr.io/<YOUR_GCP_PROJECT_ID>/crm-backend:latest \
     --region asia-east1 \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars RAG_ENGINE=gemini,GEMINI_API_KEY=<YOUR_GEMINI_API_KEY>
   ```
2. 部署完成後，CLI 會輸出 **Backend Service URL**（例如：`https://crm-backend-xyz-de.a.run.app`）。

---

### 步驟 2：部署 Frontend 至 Cloud Run

1. 將前端 `API_BASE_URL` 指定為步驟 1 取得的 Backend URL 並進行建置：
   ```bash
   cd sourcecode/frontend
   
   # 建置前端 Docker 鏡像（帶入 Backend URL）
   gcloud builds submit \
     --tag gcr.io/<YOUR_GCP_PROJECT_ID>/crm-frontend:latest \
     --substitutions _VITE_API_BASE_URL=https://crm-backend-xyz-de.a.run.app .
   
   # 部署前端至 Cloud Run
   gcloud run deploy crm-frontend \
     --image gcr.io/<YOUR_GCP_PROJECT_ID>/crm-frontend:latest \
     --region asia-east1 \
     --platform managed \
     --allow-unauthenticated \
     --port 80
   ```
2. 完成後打開產生的 **Frontend Service URL** 即可看到客服對話視窗。

---

### 自動化一鍵部署 (Cloud Build)

也可以直接在 `sourcecode/` 根目錄執行 Cloud Build：
```bash
cd sourcecode
gcloud builds submit --config=cloudbuild.yaml .
```

---

## 方式 B：部署至 Compute Engine (GCP VM + Docker Compose)

適合需要自建 VM 或保持服務持續運作的環境。

### 步驟
1. 在 GCP 建立一台 Compute Engine VM (例如 Ubuntu 22.04 LTS)。
2. 在 VM 防火牆開啟 HTTP (Port 80) 與 Port 8000。
3. 連線至 VM 並安裝 Docker / Docker Compose：
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-plugin
   ```
4. 將專案程式碼複製至 VM。
5. 設定 `.env` 檔案（填入 `GEMINI_API_KEY` 等資訊）。
6. 在 `sourcecode/` 目錄執行 Docker Compose：
   ```bash
   sudo docker compose up -d --build
   ```
7. 訪問 VM 的外網 IP 即可啟動並測試系統。

---

## 設定檔說明檔總覽

| 檔案路徑 | 說明 |
| :--- | :--- |
| [`backend/Dockerfile`](file:///c:/Source%20Code/crm_squard/sourcecode/backend/Dockerfile) | Backend Python 3.10 FastAPI 容器設定 |
| [`frontend/Dockerfile`](file:///c:/Source%20Code/crm_squard/sourcecode/frontend/Dockerfile) | Frontend Vite Node + Nginx 雙階段建置容器設定 |
| [`frontend/nginx.conf`](file:///c:/Source%20Code/crm_squard/sourcecode/frontend/nginx.conf) | Nginx 前端靜態資源與路由設定 |
| [`docker-compose.yml`](file:///c:/Source%20Code/crm_squard/sourcecode/docker-compose.yml) | Docker Compose 本地與 VM 一鍵啟動檔 |
| [`cloudbuild.yaml`](file:///c:/Source%20Code/crm_squard/sourcecode/cloudbuild.yaml) | Google Cloud Build CI/CD 自動建置指令檔 |
