[CmdletBinding()]
param(
    [string]$ClusterName = "fmcrp",
    [string]$KnativeVersion = "knative-v1.22.1",
    [string]$KindVersion = "v0.32.0",
    [string]$KubectlVersion = "v1.36.2"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $repoRoot "tools"
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop (Linux containers) is required by kind but was not found on PATH."
}
docker version --format '{{.Server.Version}}' | Out-Null

$kindExe = Join-Path $toolsDir "kind.exe"
$kubectlExe = Join-Path $toolsDir "kubectl.exe"
$env:KUBECONFIG = Join-Path $repoRoot ".kubeconfig"
if (-not (Test-Path $kindExe)) {
    Invoke-WebRequest "https://kind.sigs.k8s.io/dl/$KindVersion/kind-windows-amd64" -OutFile $kindExe
}
if (-not (Test-Path $kubectlExe)) {
    Invoke-WebRequest "https://dl.k8s.io/release/$KubectlVersion/bin/windows/amd64/kubectl.exe" -OutFile $kubectlExe
    Invoke-WebRequest "https://dl.k8s.io/release/$KubectlVersion/bin/windows/amd64/kubectl.exe.sha256" -OutFile "$kubectlExe.sha256"
    $expectedHash = (Get-Content "$kubectlExe.sha256" -Raw).Trim().ToLower()
    $actualHash = (Get-FileHash $kubectlExe -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -ne $expectedHash) { Remove-Item -LiteralPath $kubectlExe -Force; throw "kubectl checksum verification failed." }
}

$clusterExists = ((& $kindExe get clusters) -contains $ClusterName)
if (-not $clusterExists) {
    & $kindExe create cluster --name $ClusterName --wait 5m --kubeconfig $env:KUBECONFIG
} else {
    & $kindExe export kubeconfig --name $ClusterName --kubeconfig $env:KUBECONFIG
}

& $kubectlExe apply -f "https://github.com/knative/serving/releases/download/$KnativeVersion/serving-crds.yaml"
& $kubectlExe apply -f "https://github.com/knative/serving/releases/download/$KnativeVersion/serving-core.yaml"
& $kubectlExe apply -f "https://github.com/knative-extensions/net-kourier/releases/download/$KnativeVersion/kourier.yaml"
& $kubectlExe patch configmap/config-network --namespace knative-serving --type merge --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'
& $kubectlExe wait --for=condition=Ready pod --all --namespace knative-serving --timeout=5m
& $kubectlExe wait --for=condition=Ready pod --all --namespace kourier-system --timeout=5m

Write-Host "Ready. Tool hashes:"
Get-FileHash $kindExe, $kubectlExe -Algorithm SHA256 | Format-Table -AutoSize
Write-Host "Run .\scripts\deploy.ps1 next. This session has KUBECONFIG set to $env:KUBECONFIG"
