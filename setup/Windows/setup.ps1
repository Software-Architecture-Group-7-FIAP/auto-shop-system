Write-Host "Iniciando Auto Shop..." -ForegroundColor Yellow

docker compose --progress=quiet up -d db --quiet-pull 2>&1 > $null
docker build -q -t auto-shop-system:latest . 2>&1 > $null

kubectl apply -f k8s/ 2>&1 > $null
kubectl apply -f k8s/services 2>&1 > $null

Start-Process powershell -WindowStyle Hidden -ArgumentList "kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 8080:80"

Write-Host "Sistema rodando em " -ForegroundColor Yellow -NoNewline
Write-Host "http://api.autoshop.com:8080" -ForegroundColor Green

Write-Host "Para a documentacao das APIs, acesse: " -ForegroundColor Yellow -NoNewline
Write-Host "http://api.autoshop.com:8080/docs" -ForegroundColor Green

[void][System.Console]::ReadKey($true)