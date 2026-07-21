[CmdletBinding(SupportsShouldProcess)]
param([string]$ClusterName = "fmcrp")

$repoRoot = Split-Path -Parent $PSScriptRoot
$kindExe = Join-Path $repoRoot "tools\kind.exe"
if (-not (Test-Path $kindExe)) { throw "No repository-local kind binary found." }
if ($PSCmdlet.ShouldProcess("kind cluster '$ClusterName'", "delete")) { & $kindExe delete cluster --name $ClusterName }
