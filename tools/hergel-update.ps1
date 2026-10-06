param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
try {
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $launcherProcess = Get-Process -Id ([int]$request.pid) -ErrorAction SilentlyContinue
    if ($launcherProcess) { Wait-Process -Id ([int]$request.pid) -Timeout 120 -ErrorAction Stop }
    $hash = (Get-FileHash -LiteralPath $request.installer -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $request.sha256) { throw 'El instalador no supera la verificacion de integridad.' }
    $arguments = @('/SILENT', '/SP-', '/NORESTART', '/NOCLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS', ('/DIR="' + $request.install_dir + '"'))
    $setup = Start-Process -FilePath $request.installer -ArgumentList $arguments -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw ('No se pudo completar la actualizacion. Codigo: ' + $setup.ExitCode) }
    $application = Join-Path $request.install_dir 'HergelLauncher.exe'
    Start-Process -FilePath $application
    Remove-Item -LiteralPath $RequestPath -ErrorAction SilentlyContinue
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(('No se pudo actualizar Hergel Launcher. ' + $_.Exception.Message), 'Hergel Launcher', 'OK', 'Error') | Out-Null
    if ($request -and $request.install_dir) {
        $previous = Join-Path $request.install_dir 'HergelLauncher.exe'
        if (Test-Path -LiteralPath $previous) { Start-Process -FilePath $previous }
    }
    exit 1
}
