Write-Host "Iniciando Auto Shop..."

docker-compose up -d db | Out-Null
docker build -q -t auto-shop-system:latest . | Out-Null

kubectl apply -f k8s/ | Out-Null
kubectl apply -f k8s/services | Out-Null

Start-Process powershell -WindowStyle Hidden -ArgumentList "kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 8080:80"

Write-Host "Sistema rodando em http://api.autoshop.com:8080"
Write-Host "Para a documentacao das APIs, acesse: http://api.autoshop.com:8080/docs"

[void][System.Console]::ReadKey($true)