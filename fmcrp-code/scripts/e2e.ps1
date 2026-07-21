[CmdletBinding()]
param([int]$ControllerPort = 18080)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$kubectlExe = Join-Path $repoRoot "tools\kubectl.exe"
if (-not (Test-Path $kubectlExe)) { throw "Run .\scripts\bootstrap.ps1 and .\scripts\deploy.ps1 first." }
$env:KUBECONFIG = Join-Path $repoRoot ".kubeconfig"
$env:PYTHONPATH = Join-Path $repoRoot "src"

Push-Location $repoRoot
try {
    python -m unittest discover -s tests -v
    $forward = Start-Process -FilePath $kubectlExe -ArgumentList "port-forward -n fmcrp svc/fmcrp-controller ${ControllerPort}:8080" -WindowStyle Hidden -PassThru
    try {
        $deadline = (Get-Date).AddSeconds(30)
        do { Start-Sleep -Milliseconds 500; $ready = Test-NetConnection 127.0.0.1 -Port $ControllerPort -InformationLevel Quiet } while (-not $ready -and (Get-Date) -lt $deadline)
        if (-not $ready) { throw "Controller port-forward did not become ready." }
        $request = Get-Content examples/request.json -Raw | ConvertFrom-Json
        $decision = Invoke-RestMethod "http://127.0.0.1:$ControllerPort/schedule" -Method Post -ContentType "application/json" -Body ($request | ConvertTo-Json -Depth 8)
        if ($decision.Count -lt 1) { throw "The controller returned no scheduling decision." }
        $decision | ConvertTo-Json -Depth 8
    } finally {
        if (-not $forward.HasExited) { Stop-Process -Id $forward.Id -Force }
    }
    & $kubectlExe get ksvc fmcrp-target -n fmcrp
    & $kubectlExe run fmcrp-knative-smoke --rm -i --restart=Never -n fmcrp --image=curlimages/curl:8.12.1 -- curl -fsS http://fmcrp-target.fmcrp.svc.cluster.local
} finally { Pop-Location }
