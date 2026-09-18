[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('(?i)^[a-f0-9]{64}$')]
    [string]$ExpectedSha256,

    [ValidateScript({
        $_.Scheme -eq 'https' -and
        $_.Host -eq 'github.com' -and
        $_.AbsolutePath -match '^/msys2/msys2-installer/releases/(download|latest/download)/'
    })]
    [Uri]$InstallerUri = 'https://github.com/msys2/msys2-installer/releases/latest/download/msys2-x86_64-latest.exe',

    [ValidateNotNullOrEmpty()]
    [string]$InstallRoot = 'C:\msys64'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$installRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$bashPath = Join-Path $installRoot 'usr\bin\bash.exe'
$dllDirectory = Join-Path $installRoot 'mingw64\bin'
$installerPath = $null

function Set-WeasyPrintDllDirectory {
    param([Parameter(Mandatory)][string]$Directory)

    $existing = [Environment]::GetEnvironmentVariable(
        'WEASYPRINT_DLL_DIRECTORIES',
        [EnvironmentVariableTarget]::User
    )
    $directories = @($existing -split ';' | Where-Object { $_ })
    if ($directories -notcontains $Directory) {
        $directories += $Directory
    }
    $value = $directories -join ';'
    [Environment]::SetEnvironmentVariable(
        'WEASYPRINT_DLL_DIRECTORIES',
        $value,
        [EnvironmentVariableTarget]::User
    )
    $env:WEASYPRINT_DLL_DIRECTORIES = $value
    Write-Host "WEASYPRINT_DLL_DIRECTORIES=$value"
    Write-Host 'Open a new terminal before running Python outside this session.'
}

try {
    if (-not (Test-Path -LiteralPath $bashPath -PathType Leaf)) {
        if (Test-Path -LiteralPath $installRoot) {
            throw "MSYS2 install root exists but bash.exe is missing: $bashPath"
        }

        if (-not $PSCmdlet.ShouldProcess($InstallerUri, "Download, verify, and install MSYS2 at $installRoot")) {
            return
        }

        $temporaryFile = New-TemporaryFile
        $installerPath = "$($temporaryFile.FullName).exe"
        Remove-Item -LiteralPath $temporaryFile.FullName -Force
        Invoke-WebRequest -Uri $InstallerUri -OutFile $installerPath
        $actualSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash
        if ($actualSha256 -ne $ExpectedSha256.ToUpperInvariant()) {
            throw "MSYS2 installer SHA-256 mismatch. Expected $ExpectedSha256; got $actualSha256."
        }

        Write-Host "Verified MSYS2 installer SHA-256: $actualSha256"
        $installer = Start-Process -FilePath $installerPath -ArgumentList @(
            'install', '--root', $installRoot, '--confirm-command', '--accept-messages'
        ) -Wait -PassThru -NoNewWindow
        if ($installer.ExitCode -ne 0) {
            throw "MSYS2 installer failed with exit code $($installer.ExitCode)."
        }
    }

    if (-not (Test-Path -LiteralPath $bashPath -PathType Leaf)) {
        throw "MSYS2 bash.exe was not found after installation: $bashPath"
    }

    if ($PSCmdlet.ShouldProcess($installRoot, 'Install mingw-w64-x86_64-pango with pacman')) {
        & $bashPath -lc 'pacman --noconfirm --needed -S mingw-w64-x86_64-pango'
        if ($LASTEXITCODE -ne 0) {
            throw "pacman failed with exit code $LASTEXITCODE."
        }
    }

    if (-not (Test-Path -LiteralPath $dllDirectory -PathType Container)) {
        throw "WeasyPrint DLL directory was not created: $dllDirectory"
    }

    if ($PSCmdlet.ShouldProcess('User environment', "Set WEASYPRINT_DLL_DIRECTORIES to include $dllDirectory")) {
        Set-WeasyPrintDllDirectory -Directory $dllDirectory
    }

    Write-Host 'MSYS2 GPG signature verification remains a manual human step.'
    Write-Host 'Obtain the SHA-256 from an official MSYS2 release checksum or signed source before running this script.'
}
finally {
    if ($installerPath -and (Test-Path -LiteralPath $installerPath)) {
        Remove-Item -LiteralPath $installerPath -Force
    }
}