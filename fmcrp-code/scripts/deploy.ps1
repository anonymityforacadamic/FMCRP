[CmdletBinding()]
param([string]$ClusterName = "fmcrp")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $repoRoot "tools"
$kindExe = Join-Path $toolsDir "kind.exe"
$kubectlExe = Join-Path $toolsDir "kubectl.exe"
if (-not ((Test-Path $kindExe) -and (Test-Path $kubectlExe))) { throw "Run .\scripts\bootstrap.ps1 first." }
$env:KUBECONFIG = Join-Path $repoRoot ".kubeconfig"

Push-Location $repoRoot
try {
    docker build -t fmcrp-controller:0.1.0 -f Dockerfile.controller .
    docker build -t fmcrp-target:0.1.0 ./function
    & $kindExe load docker-image fmcrp-controller:0.1.0 fmcrp-target:0.1.0 --name $ClusterName
    & $kubectlExe apply -f deploy/namespace.yaml
    & $kubectlExe apply -f deploy/controller.yaml
    & $kubectlExe apply -f deploy/function.yaml
    & $kubectlExe rollout status deployment/fmcrp-controller -n fmcrp --timeout=3m
    & $kubectlExe wait --for=condition=Ready ksvc/fmcrp-target -n fmcrp --timeout=5m
} finally { Pop-Location }
Write-Host "FMCRP controller and Knative target are ready. Run .\scripts\e2e.ps1."
