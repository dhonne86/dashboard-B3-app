@echo off
setlocal

set "SERVICE=dashboard-b3"
set "REGION=southamerica-east1"

if "%PROJECT_ID%"=="" (
  echo Defina PROJECT_ID antes de rodar. Exemplo:
  echo set PROJECT_ID=meu-projeto-google
  exit /b 1
)

if "%BRAPI_TOKEN%"=="" (
  echo Defina BRAPI_TOKEN antes de rodar.
  exit /b 1
)

if "%DASHBOARD_PASSWORD%"=="" (
  echo Defina DASHBOARD_PASSWORD antes de rodar.
  exit /b 1
)

gcloud config set project "%PROJECT_ID%"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud builds submit --tag "gcr.io/%PROJECT_ID%/%SERVICE%"
gcloud run deploy "%SERVICE%" ^
  --image "gcr.io/%PROJECT_ID%/%SERVICE%" ^
  --region "%REGION%" ^
  --platform managed ^
  --allow-unauthenticated ^
  --set-env-vars "BRAPI_TOKEN=%BRAPI_TOKEN%,DASHBOARD_USER=admin,DASHBOARD_PASSWORD=%DASHBOARD_PASSWORD%,DEBUG=0"

endlocal
