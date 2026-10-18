# Installeur de WaveDevSecOps pour Windows 10 et 11, sans droits administrateur (AD-15, AD-20).
#
# Commande unique (voir le README) :
#   [Net.ServicePointManager]::SecurityProtocol = 'Tls12'; $w = New-Object Net.WebClient; if ($env:HTTPS_PROXY) { $w.Proxy = New-Object Net.WebProxy($env:HTTPS_PROXY, $true); $w.Proxy.UseDefaultCredentials = $true }; iex ([Text.Encoding]::UTF8.GetString($w.DownloadData('https://raw.githubusercontent.com/Aliquanto3/wavedevsecops/main/install.ps1')).TrimStart([char]0xFEFF))
#
# Compatible Windows PowerShell 5.1. Aucune élévation : tout est écrit dans le profil de
# l'utilisateur. Relancé, il met l'application à jour et conserve progress.json.
#
# Réglages (variables d'environnement, toutes facultatives) :
#   WDS_DATA_DIR        dossier des données (par défaut %LOCALAPPDATA%\WaveDevSecOps, comme l'application)
#   WDS_INSTALL_METHOD  clone (défaut) ou zip
#   WDS_INSTALL_REF     branche ou étiquette à installer (défaut main)
#   HTTPS_PROXY         proxy d'entreprise ; pose aussi UV_SYSTEM_CERTS=true
# Réglages de test (aucun accès réseau, aucune installation réelle) :
#   WDS_INSTALL_SIMULATE=1, WDS_INSTALL_SIMULATE_GIT=<version|none>, WDS_INSTALL_SIMULATE_UV=<version|none>,
#   WDS_INSTALL_SIMULATE_FAIL=<étapes séparées par des virgules : download, portablegit, clone, sync>,
#   WDS_INSTALL_LIBONLY=1 (définit les fonctions sans rien lancer).

$script:SavedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Stop'
$script:InstallerVersion = 1
$script:RepoUrl = 'https://github.com/Aliquanto3/wavedevsecops.git'
$script:ZipUrlBase = 'https://github.com/Aliquanto3/wavedevsecops/archive'
$script:RawUrlBase = 'https://raw.githubusercontent.com/Aliquanto3/wavedevsecops'
$script:Simulate = ($env:WDS_INSTALL_SIMULATE -eq '1')
$script:CurrentStep = ''
$script:Proxy = $null
$script:SimLog = $null

# --- Messages -----------------------------------------------------------------------------

function Write-Step([string]$Text) {
    $script:CurrentStep = $Text
    Write-Host ''
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Info([string]$Text) { Write-Host "    $Text" }

class InstallError : System.Exception {
    [string]$Cause
    [string[]]$Settings
    [string]$Route
    InstallError([string]$cause, [string[]]$settings, [string]$route) : base($cause) {
        $this.Cause = $cause
        $this.Settings = $settings
        $this.Route = $route
    }
}

function New-InstallError([string]$Cause, [string[]]$Settings, [string]$Route) {
    return New-Object InstallError -ArgumentList $Cause, $Settings, $Route
}

function Format-InstallError($Err, [string]$Step) {
    $lines = @("L'installation s'est arrêtée à l'étape « $Step ».", "Cause : $($Err.Cause)")
    if ($Err.Settings -and $Err.Settings.Count -gt 0) {
        $lines += 'Variables à régler : ' + ($Err.Settings -join ' ; ')
    }
    if ($Err.Route) { $lines += "Voie de repli : $($Err.Route)" }
    $lines += 'Relancez la même commande : l''installeur reprend là où il s''est arrêté et ne casse rien.'
    return ($lines -join [Environment]::NewLine)
}

$script:NetworkSettings = @(
    'HTTPS_PROXY (par exemple http://proxy.entreprise:8080)',
    'NO_PROXY=127.0.0.1,localhost',
    'UV_SYSTEM_CERTS=true (certificats de l''entreprise)'
)
$script:RouteText = ('par clone (WDS_INSTALL_METHOD=clone, il faut git) ou par zip ' +
    '($env:WDS_INSTALL_METHOD = ''zip''), sans git. ' +
    'À défaut, téléchargez le zip de l''application depuis GitHub, dézippez-le dans le dossier « app » du dossier de données, puis lancez « uv sync » dedans.')

# --- Fonctions pures (testées) ------------------------------------------------------------

function Get-DataDir {
    if ($env:WDS_DATA_DIR -and $env:WDS_DATA_DIR.Trim()) { return $env:WDS_DATA_DIR.Trim() }
    $local = $env:LOCALAPPDATA
    if (-not $local) { $local = Join-Path $env:USERPROFILE 'AppData\Local' }
    return (Join-Path $local 'WaveDevSecOps')
}

function ConvertTo-VersionParts([string]$Text) {
    # Les composantes numériques de tête : « 2.43.0.windows.1 » donne 2, 43, 0.
    $m = [regex]::Match($Text, '^\s*v?(\d+(?:\.\d+)*)')
    if (-not $m.Success) { return @() }
    return @($m.Groups[1].Value.Split('.') | ForEach-Object { [int]$_ })
}

function Test-VersionAtLeast([string]$Version, [string]$Minimum) {
    $a = @(ConvertTo-VersionParts $Version)
    $b = @(ConvertTo-VersionParts $Minimum)
    if ($a.Count -eq 0) { return $false }
    $n = [Math]::Max($a.Count, $b.Count)
    for ($i = 0; $i -lt $n; $i++) {
        $x = if ($i -lt $a.Count) { $a[$i] } else { 0 }
        $y = if ($i -lt $b.Count) { $b[$i] } else { 0 }
        if ($x -ne $y) { return ($x -gt $y) }
    }
    return $true
}

function Read-ToolsRegistry([string]$Path) {
    # Lecteur minimal de tools.toml (pas de parseur TOML en PowerShell 5.1) : `[[tool]]`,
    # ses sous-tables `[tool.<nom>]`, valeurs textes entre guillemets et listes de textes.
    $tools = [ordered]@{}
    $current = $null
    $sub = $null
    foreach ($raw in [IO.File]::ReadAllLines($Path, [Text.Encoding]::UTF8)) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith('#')) { continue }
        if ($line -eq '[[tool]]') { $current = @{}; $sub = $null; continue }
        $header = [regex]::Match($line, '^\[tool\.([A-Za-z_]+)\]$')
        if ($header.Success) { $sub = $header.Groups[1].Value; continue }
        if ($null -eq $current) { continue }
        $kv = [regex]::Match($line, '^([A-Za-z_]+)\s*=\s*(.*)$')
        if (-not $kv.Success) { continue }
        $key = $kv.Groups[1].Value
        $rest = $kv.Groups[2].Value.Trim()
        $value = $null
        $str = [regex]::Match($rest, '^"([^"]*)"')
        $lit = [regex]::Match($rest, "^'([^']*)'")
        if ($str.Success) { $value = $str.Groups[1].Value }
        elseif ($lit.Success) { $value = $lit.Groups[1].Value }
        elseif ($rest.StartsWith('[')) {
            $value = @([regex]::Matches($rest, '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
        }
        else { continue }
        $name = if ($sub) { "${sub}_$key" } else { $key }
        $current[$name] = $value
        if ($key -eq 'id' -and -not $sub) { $tools[$value] = $current }
    }
    return $tools
}

function Get-ProvisionedVersion($Tool) {
    # Table `windows` si la version diffère selon le système, sinon la valeur unique.
    if ($Tool.ContainsKey('provisioned_version_windows')) { return $Tool['provisioned_version_windows'] }
    return $Tool['provisioned_version']
}

function Get-PortableGitUrl([string]$Version) {
    # 2.56.0.windows.2 : étiquette v2.56.0.windows.2, fichier PortableGit-2.56.0.2-64-bit.7z.exe.
    # 2.56.0.windows.1 : fichier PortableGit-2.56.0-64-bit.7z.exe.
    $m = [regex]::Match($Version, '^(\d+(?:\.\d+)*)\.windows\.(\d+)$')
    if (-not $m.Success) {
        throw (New-InstallError "Version de git illisible dans tools.toml : « $Version »." @() 'corrigez le registre tools.toml, ou installez git vous-même (version 2.38 ou plus).')
    }
    $file = if ([int]$m.Groups[2].Value -gt 1) { "$($m.Groups[1].Value).$($m.Groups[2].Value)" } else { $m.Groups[1].Value }
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { '64-bit' }
    return "https://github.com/git-for-windows/git/releases/download/v$Version/PortableGit-$file-$arch.7z.exe"
}

function New-InstallRecord($Previous, [hashtable]$Versions, [string]$Method, [string]$AppDir, [double]$DurationSeconds, [datetimeoffset]$Now) {
    # `installed_at` : date de la première installation (lue par progress.json) ; `updated_at` : dernière passe.
    $first = $Now.ToString('o')
    $count = 1
    if ($Previous -and $Previous.installed_at) { $first = [string]$Previous.installed_at }
    if ($Previous -and $Previous.run_count) { $count = [int]$Previous.run_count + 1 }
    return [ordered]@{
        schema_version = 1
        installed_at   = $first
        updated_at     = $Now.ToString('o')
        run_count      = $count
        duration_s     = [Math]::Round($DurationSeconds, 1)
        method         = $Method
        app_dir        = $AppDir
        versions       = $Versions
    }
}

function Write-JsonFile([string]$Path, $Object) {
    $json = $Object | ConvertTo-Json -Depth 6
    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $tmp = "$Path.tmp"
    [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Read-PreviousInstall([string]$DataDir) {
    $path = Join-Path $DataDir 'install.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    try { $data = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { return $null }   # illisible : on le réécrit
    if ($data.schema_version -and [int]$data.schema_version -gt 1) {
        throw (New-InstallError "install.json vient d'une version plus récente de l'application (schema_version $($data.schema_version))." @() 'mettez à jour l''installeur avec la commande du README à jour ; rien n''a été modifié.')
    }
    return $data
}

# --- Réseau, simulation -------------------------------------------------------------------

function Test-SimulatedFailure([string]$Step) {
    if (-not $script:Simulate -or -not $env:WDS_INSTALL_SIMULATE_FAIL) { return $false }
    return (@($env:WDS_INSTALL_SIMULATE_FAIL.Split(',') | ForEach-Object { $_.Trim() }) -contains $Step)
}

function Add-SimLog([string]$Text) {
    if ($script:SimLog) { Add-Content -LiteralPath $script:SimLog -Value $Text -Encoding UTF8 }
}

function Initialize-Network {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
    $script:Proxy = $null
    $proxy = $env:HTTPS_PROXY
    if (-not $proxy) { $proxy = $env:https_proxy }
    if ($proxy -and $proxy.Trim()) {
        $script:Proxy = $proxy.Trim()
        $env:UV_SYSTEM_CERTS = 'true'
        Write-Info "Proxy détecté : les téléchargements passent par lui, UV_SYSTEM_CERTS=true."
    }
}

function Save-File([string]$Url, [string]$Destination) {
    # Téléchargement vers un fichier .part, renommé à la fin : un échec ne laisse jamais un fichier tronqué.
    if (Test-Path -LiteralPath $Destination) {
        if ((Get-Item -LiteralPath $Destination).Length -gt 0) { Write-Info "Déjà téléchargé : $(Split-Path -Leaf $Destination)"; return }
    }
    $dir = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if ($script:Simulate) {
        Add-SimLog "download $Url"
        if (Test-SimulatedFailure 'download') {
            throw (New-InstallError "Le téléchargement de $Url a échoué (simulation)." $script:NetworkSettings $script:RouteText)
        }
        if ($Url.EndsWith('/tools.toml') -and $env:WDS_INSTALL_SIMULATE_TOOLS_TOML) {
            Copy-Item -LiteralPath $env:WDS_INSTALL_SIMULATE_TOOLS_TOML -Destination $Destination -Force
        }
        else { [IO.File]::WriteAllText($Destination, 'simulation') }
        return
    }
    $part = "$Destination.part"
    # Locale à la fonction : sous PowerShell 5.1, la barre de progression ralentit fortement Invoke-WebRequest.
    $ProgressPreference = 'SilentlyContinue'
    try {
        $request = @{ Uri = $Url; OutFile = $part; UseBasicParsing = $true }
        if ($script:Proxy) { $request["Proxy"] = $script:Proxy; $request["ProxyUseDefaultCredentials"] = $true }
        Invoke-WebRequest @request
        Move-Item -LiteralPath $part -Destination $Destination -Force
    }
    catch {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw (New-InstallError "Le téléchargement de $Url a échoué : $($_.Exception.Message)" $script:NetworkSettings $script:RouteText)
    }
}

function ConvertTo-ArgumentString([string[]]$Arguments) {
    return (($Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' ')
}

function Invoke-Native([string]$File, [string[]]$Arguments, [string]$WorkingDirectory) {
    # Lance un programme sans shell et rend son code de sortie (Start-Process évite les
    # erreurs « NativeCommandError » de PowerShell 5.1 quand un programme écrit sur stderr).
    $p = @{ FilePath = $File; ArgumentList = (ConvertTo-ArgumentString $Arguments); Wait = $true; PassThru = $true; NoNewWindow = $true }
    if ($WorkingDirectory) { $p['WorkingDirectory'] = $WorkingDirectory }
    $proc = Start-Process @p
    return $proc.ExitCode
}

function Get-ToolVersionText([string]$Exe, [string[]]$Arguments, [string]$Pattern) {
    try {
        $out = & $Exe @Arguments 2>$null | Out-String
        $m = [regex]::Match($out, $Pattern)
        if ($m.Success) { return $m.Groups[1].Value }
    }
    catch { }
    return $null
}

# --- Étapes -------------------------------------------------------------------------------

function Get-HostGit([string]$DataDir, [hashtable]$Tool) {
    # Rend @{ Path; Version; Source } du git utilisable, ou $null. Un git du poste suffisant
    # est gardé tel quel ; sinon un PortableGit déjà provisionné est réutilisé.
    $min = $Tool['min_version']
    if ($script:Simulate) {
        $v = $env:WDS_INSTALL_SIMULATE_GIT
        if ($v -and $v -ne 'none' -and (Test-VersionAtLeast $v $min)) { return @{ Path = 'git'; Version = $v; Source = 'host' } }
    }
    else {
        $cmd = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) {
            $v = Get-ToolVersionText $cmd.Source @('--version') 'git version (\d+(?:\.\d+)+)'
            if ($v -and (Test-VersionAtLeast $v $min)) { return @{ Path = $cmd.Source; Version = $v; Source = 'host' } }
        }
    }
    $provisioned = Join-Path $DataDir 'tools\git\cmd\git.exe'
    if (Test-Path -LiteralPath $provisioned) {
        $v = if ($script:Simulate) { Get-ProvisionedVersion $Tool } else { Get-ToolVersionText $provisioned @('--version') 'git version (\d+(?:\.\d+)+)' }
        if ($v -and (Test-VersionAtLeast $v $min)) { return @{ Path = $provisioned; Version = $v; Source = 'provisioned' } }
    }
    return $null
}

function Install-PortableGit([string]$DataDir, [hashtable]$Tool) {
    $version = Get-ProvisionedVersion $Tool
    $url = Get-PortableGitUrl $version
    $target = Join-Path $DataDir 'tools\git'
    $archive = Join-Path $DataDir ('cache\downloads\' + (Split-Path -Leaf $url))
    Write-Info "git absent ou antérieur à $($Tool['min_version']) : PortableGit $version (sans droits administrateur)."
    Save-File $url $archive
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }   # extraction partielle d'une passe précédente
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    if ($script:Simulate) {
        Add-SimLog "portablegit -y -gm2 -InstallPath=$target"
        if (Test-SimulatedFailure 'portablegit') {
            throw (New-InstallError 'L''extraction de PortableGit a échoué (simulation).' @('WDS_DATA_DIR (dossier accessible en écriture, hors antivirus restrictif)') $script:RouteText)
        }
        New-Item -ItemType Directory -Path (Join-Path $target 'cmd') -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $target 'cmd\git.exe'), 'simulation')
    }
    else {
        $code = Invoke-Native $archive @('-y', '-gm2', "-InstallPath=$target") $null
        if ($code -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $target 'cmd\git.exe'))) {
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue   # archive peut-être corrompue : retéléchargée
            throw (New-InstallError "L'extraction de PortableGit a échoué (code $code)." @('WDS_DATA_DIR (dossier accessible en écriture)', 'exclusion de l''antivirus pour ce dossier') $script:RouteText)
        }
    }
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    return @{ Path = (Join-Path $target 'cmd\git.exe'); Version = $version; Source = 'provisioned' }
}

function Get-HostUv([hashtable]$Tool) {
    $min = $Tool['min_version']
    if ($script:Simulate) {
        $v = $env:WDS_INSTALL_SIMULATE_UV
        if ($v -and $v -ne 'none' -and (Test-VersionAtLeast $v $min)) { return @{ Path = 'uv'; Version = $v } }
        return $null
    }
    $candidates = @()
    $cmd = Get-Command uv -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += (Join-Path (Get-UvInstallDir) 'uv.exe')
    foreach ($c in $candidates) {
        if (-not (Test-Path -LiteralPath $c)) { continue }
        $v = Get-ToolVersionText $c @('--version') 'uv (\d+(?:\.\d+)+)'
        if ($v -and (Test-VersionAtLeast $v $min)) { return @{ Path = $c; Version = $v } }
    }
    return $null
}

function Get-UvInstallDir {
    if ($env:UV_INSTALL_DIR) { return $env:UV_INSTALL_DIR }
    return (Join-Path $env:USERPROFILE '.local\bin')
}

function ConvertTo-PsLiteral([string]$Text) { return "'" + ($Text -replace "'", "''") + "'" }

function Get-UvInstallerCommand([string]$ScriptPath, [string]$Proxy) {
    # L'installeur d'astral est lu puis passé à iex, comme sa commande officielle : pas de
    # -File, donc pas de blocage par une politique d'exécution imposée par GPO. Le proxy est
    # posé par défaut pour WebClient et Invoke-WebRequest, quel que soit l'outil qu'il utilise.
    $lines = @(
        "`$ErrorActionPreference = 'Stop'",
        "`$ProgressPreference = 'SilentlyContinue'",
        'try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }'
    )
    if ($Proxy) {
        $lines += "`$wdsProxy = New-Object Net.WebProxy($(ConvertTo-PsLiteral $Proxy), `$true)"
        $lines += '$wdsProxy.UseDefaultCredentials = $true'
        $lines += '[Net.WebRequest]::DefaultWebProxy = $wdsProxy'
    }
    $lines += "Invoke-Expression ([IO.File]::ReadAllText($(ConvertTo-PsLiteral $ScriptPath), [Text.Encoding]::UTF8))"
    return ($lines -join [Environment]::NewLine)
}

function Install-Uv([string]$DataDir, [hashtable]$Tool) {
    $version = Get-ProvisionedVersion $Tool
    $url = "https://astral.sh/uv/$version/install.ps1"
    $script = Join-Path $DataDir "cache\downloads\uv-$version-install.ps1"
    Write-Info "uv absent ou antérieur à $($Tool['min_version']) : installation de uv $version dans le profil."
    Save-File $url $script
    if ($script:Simulate) {
        Add-SimLog "uv-install $version"
        return @{ Path = 'uv'; Version = $version }
    }
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes((Get-UvInstallerCommand $script $script:Proxy)))
    $code = Invoke-Native 'powershell.exe' @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) $null
    $exe = Join-Path (Get-UvInstallDir) 'uv.exe'
    if ($code -ne 0 -or -not (Test-Path -LiteralPath $exe)) {
        Remove-Item -LiteralPath $script -Force -ErrorAction SilentlyContinue
        $cause = "L'installation de uv a échoué (code $code) ; la cause est affichée juste au-dessus par l'installeur d'astral. " +
            'Causes fréquentes : proxy non renseigné, certificats de l''entreprise, antivirus, ou mode de langage restreint de PowerShell (AppLocker).'
        $route = 'installez uv vous-même (https://docs.astral.sh/uv/, version ' + $Tool['min_version'] + ' ou plus, dans le PATH), puis relancez la commande. ' + $script:RouteText
        throw (New-InstallError $cause ($script:NetworkSettings + @('UV_INSTALL_DIR (dossier de uv.exe, par défaut %USERPROFILE%\.local\bin)')) $route)
    }
    return @{ Path = $exe; Version = (Get-ToolVersionText $exe @('--version') 'uv (\d+(?:\.\d+)+)') }
}

function Assert-AppDirReplaceable([string]$AppDir) {
    # Un dossier « app » existant n'est remplacé que s'il est vide ou contient l'application
    # (pyproject.toml ou .git) : un WDS_DATA_DIR mal placé ne doit pas effacer un dossier de l'utilisateur.
    if (-not (Test-Path -LiteralPath $AppDir)) { return }
    if (Test-Path -LiteralPath (Join-Path $AppDir 'pyproject.toml')) { return }
    if (Test-Path -LiteralPath (Join-Path $AppDir '.git')) { return }
    if (@(Get-ChildItem -LiteralPath $AppDir -Force).Count -eq 0) { return }
    throw (New-InstallError "Le dossier « $AppDir » existe et ne contient pas l'application : il n'est pas modifié." @('WDS_DATA_DIR (dossier réservé à WaveDevSecOps)') 'choisissez un autre WDS_DATA_DIR, ou videz ce dossier « app » vous-même, puis relancez la commande.')
}

function Install-AppByClone([string]$DataDir, [string]$AppDir, [string]$GitExe, [string]$Ref) {
    $sslArgs = @()
    if ($script:Proxy) { $sslArgs = @('-c', 'http.sslBackend=schannel') }   # certificats de l'entreprise, magasin Windows
    Assert-AppDirReplaceable $AppDir
    if ($script:Simulate) {
        if (Test-SimulatedFailure 'clone') {
            throw (New-InstallError 'Le clone de l''application a échoué (simulation).' $script:NetworkSettings $script:RouteText)
        }
        if (Test-Path -LiteralPath (Join-Path $AppDir '.git')) {
            Add-SimLog "update-clone $AppDir"
        }
        else {
            Add-SimLog "clone -c core.autocrlf=false $script:RepoUrl -> $AppDir"
            New-Item -ItemType Directory -Path (Join-Path $AppDir '.git') -Force | Out-Null
        }
        return 'simulation0000000000000000000000000000000000'
    }
    if (Test-Path -LiteralPath (Join-Path $AppDir '.git')) {
        # Mise à jour : récupération puis alignement sur la branche (n'échoue pas sur des fichiers modifiés).
        $c1 = Invoke-Native $GitExe ($sslArgs + @('-c', 'core.autocrlf=false', '-C', $AppDir, 'fetch', '--depth', '1', 'origin', $Ref)) $null
        $c2 = if ($c1 -eq 0) { Invoke-Native $GitExe @('-c', 'core.autocrlf=false', '-C', $AppDir, 'reset', '--hard', 'FETCH_HEAD') $null } else { $c1 }
        if ($c1 -ne 0 -or $c2 -ne 0) {
            throw (New-InstallError "La mise à jour git de l'application a échoué (code $c1/$c2)." $script:NetworkSettings $script:RouteText)
        }
    }
    else {
        $partial = "$AppDir.partial"
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Recurse -Force }   # clone interrompu
        if (Test-Path -LiteralPath $AppDir) { Remove-Item -LiteralPath $AppDir -Recurse -Force }    # reste d'une voie zip
        $code = Invoke-Native $GitExe ($sslArgs + @('-c', 'core.autocrlf=false', 'clone', '--depth', '1', '--branch', $Ref, $script:RepoUrl, $partial)) $null
        if ($code -ne 0) {
            Remove-Item -LiteralPath $partial -Recurse -Force -ErrorAction SilentlyContinue
            throw (New-InstallError "Le clone de $script:RepoUrl a échoué (code $code)." $script:NetworkSettings $script:RouteText)
        }
        Move-Item -LiteralPath $partial -Destination $AppDir
    }
    $rev = Get-ToolVersionText $GitExe @('-C', $AppDir, 'rev-parse', 'HEAD') '([0-9a-f]{40})'
    return $rev
}

function Install-AppByZip([string]$DataDir, [string]$AppDir, [string]$Ref) {
    Assert-AppDirReplaceable $AppDir
    $url = "$script:ZipUrlBase/$Ref.zip"
    $zip = Join-Path $DataDir "cache\downloads\wavedevsecops-$($Ref -replace '[\\/]', '_').zip"
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue   # un zip de branche change : toujours frais
    Save-File $url $zip
    $staging = "$AppDir.new"
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    if ($script:Simulate) {
        Add-SimLog "zip-extract $url -> $AppDir"
        [IO.File]::WriteAllText((Join-Path $staging 'pyproject.toml'), 'simulation')
    }
    else {
        $ProgressPreference = 'SilentlyContinue'
        try {
            Expand-Archive -LiteralPath $zip -DestinationPath $staging -Force
            $inner = @(Get-ChildItem -LiteralPath $staging -Directory)
            if ($inner.Count -eq 1 -and -not (Test-Path -LiteralPath (Join-Path $staging 'pyproject.toml'))) {
                # Le zip GitHub contient un seul dossier « wavedevsecops-<ref> » : on le remonte.
                $tmp = "$staging.inner"
                Move-Item -LiteralPath $inner[0].FullName -Destination $tmp
                Remove-Item -LiteralPath $staging -Recurse -Force
                Move-Item -LiteralPath $tmp -Destination $staging
            }
        }
        catch {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
            throw (New-InstallError "Le zip n'a pas pu être extrait : $($_.Exception.Message)" @('WDS_DATA_DIR (dossier accessible en écriture)') $script:RouteText)
        }
        if (-not (Test-Path -LiteralPath (Join-Path $staging 'pyproject.toml'))) {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
            throw (New-InstallError 'Le zip ne contient pas l''application attendue (pyproject.toml absent).' @('WDS_INSTALL_REF') $script:RouteText)
        }
    }
    # Remplacement : l'ancienne version est mise de côté puis supprimée, jamais effacée avant que la nouvelle soit prête.
    $old = "$AppDir.old"
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force }
    if (Test-Path -LiteralPath $AppDir) { Move-Item -LiteralPath $AppDir -Destination $old }
    Move-Item -LiteralPath $staging -Destination $AppDir
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue }
    return $null
}

function Invoke-UvSync([string]$UvExe, [string]$AppDir) {
    if ($script:Simulate) {
        Add-SimLog "uv sync --frozen in $AppDir"
        if (Test-SimulatedFailure 'sync') {
            throw (New-InstallError '« uv sync » a échoué (simulation).' $script:NetworkSettings $script:RouteText)
        }
        return
    }
    $code = Invoke-Native $UvExe @('sync', '--frozen') $AppDir
    if ($code -ne 0) {
        throw (New-InstallError "« uv sync » a échoué (code $code) : les dépendances Python n'ont pas pu être installées." $script:NetworkSettings $script:RouteText)
    }
}

function Get-RegistryPath([string]$DataDir, [string]$Ref) {
    if ($PSScriptRoot) {
        $local = Join-Path $PSScriptRoot 'tools.toml'
        if (Test-Path -LiteralPath $local) { return $local }
    }
    $cached = Join-Path $DataDir 'cache\tools.toml'
    if (Test-Path -LiteralPath $cached) { Remove-Item -LiteralPath $cached -Force }
    Save-File "$script:RawUrlBase/$Ref/tools.toml" $cached
    return $cached
}

# --- Parcours principal -------------------------------------------------------------------

function Invoke-Install {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $dataDir = Get-DataDir
    $method = if ($env:WDS_INSTALL_METHOD) { $env:WDS_INSTALL_METHOD.Trim().ToLowerInvariant() } else { 'clone' }
    if ($method -notin @('clone', 'zip')) {
        throw (New-InstallError "WDS_INSTALL_METHOD vaut « $method » : seules les valeurs clone et zip existent." @('WDS_INSTALL_METHOD=clone ou zip') '')
    }
    $ref = if ($env:WDS_INSTALL_REF) { $env:WDS_INSTALL_REF.Trim() } else { 'main' }
    $appDir = Join-Path $dataDir 'app'

    Write-Step 'Préparation'
    foreach ($d in @($dataDir, (Join-Path $dataDir 'tools'), (Join-Path $dataDir 'cache'))) {
        if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
    }
    if ($script:Simulate) { $script:SimLog = Join-Path $dataDir 'install.simulation.log' }
    $previous = Read-PreviousInstall $dataDir
    $progress = Join-Path $dataDir 'progress.json'
    if ($previous) { Write-Info 'Installation existante : mise à jour (progress.json est conservé).' }
    Write-Info "Dossier des données : $dataDir"
    Initialize-Network

    Write-Step 'Registre des outils (tools.toml)'
    $registry = Read-ToolsRegistry (Get-RegistryPath $dataDir $ref)
    foreach ($id in @('git', 'uv')) {
        if (-not $registry.Contains($id)) {
            throw (New-InstallError "tools.toml ne déclare pas l'outil « $id »." @() 'récupérez une version à jour de l''application (zip depuis GitHub).')
        }
    }

    $versions = [ordered]@{}
    $git = $null
    if ($method -eq 'clone') {
        Write-Step 'git'
        $git = Get-HostGit $dataDir $registry['git']
        if ($git) { Write-Info "git $($git.Version) gardé tel quel ($($git.Source))." }
        else { $git = Install-PortableGit $dataDir $registry['git'] }
        $versions['git'] = $git.Version
        $versions['git_source'] = $git.Source
    }
    else {
        # La voie zip n'a pas besoin de git pour l'installation ; git sera provisionné au besoin au prochain lancement par clone.
        $git = Get-HostGit $dataDir $registry['git']
        if ($git) { $versions['git'] = $git.Version; $versions['git_source'] = $git.Source }
    }

    Write-Step 'uv'
    $uv = Get-HostUv $registry['uv']
    if ($uv) { Write-Info "uv $($uv.Version) gardé tel quel." }
    else { $uv = Install-Uv $dataDir $registry['uv'] }
    $versions['uv'] = $uv.Version

    Write-Step "Application ($method)"
    if ($method -eq 'clone') {
        $rev = Install-AppByClone $dataDir $appDir $git.Path $ref
        $versions['app'] = "git:$ref@$rev"
    }
    else {
        Install-AppByZip $dataDir $appDir $ref | Out-Null
        $versions['app'] = "zip:$ref"
    }

    Write-Step 'Dépendances Python (uv sync)'
    Invoke-UvSync $uv.Path $appDir

    Write-Step 'Enregistrement'
    $watch.Stop()
    $record = New-InstallRecord $previous $versions $method $appDir $watch.Elapsed.TotalSeconds ([datetimeoffset]::Now)
    Write-JsonFile (Join-Path $dataDir 'install.json') $record
    Write-Info "install.json écrit dans $dataDir ($([Math]::Round($watch.Elapsed.TotalSeconds)) s)."
    if (Test-Path -LiteralPath $progress) { Write-Info 'progress.json conservé tel quel.' }

    Write-Host ''
    Write-Host 'Installation terminée.' -ForegroundColor Green
    Write-Host 'Lancer l''application :'
    Write-Host "    & `"$($uv.Path)`" run --project `"$appDir`" wavedevsecops"
    if ($script:Proxy) { Write-Host 'Derrière un proxy, gardez UV_SYSTEM_CERTS=true et NO_PROXY=127.0.0.1,localhost pour les prochains lancements.' }
}

function Start-Installer {
    try {
        Invoke-Install
    }
    catch {
        $err = $_.Exception
        if ($err -isnot [InstallError]) {
            $err = New-InstallError "Erreur inattendue : $($err.Message)" @() $script:RouteText
        }
        Write-Host ''
        Write-Host (Format-InstallError $err $script:CurrentStep) -ForegroundColor Red
        $global:LASTEXITCODE = 1
        # Lancé comme fichier, le code de sortie compte ; collé via iex, `exit` fermerait la console de l'utilisateur.
        if ($PSCommandPath) { exit 1 }
    }
    finally {
        # Collé via iex, le script s'exécute dans la portée de la console : on lui rend sa préférence.
        if (-not $PSCommandPath) { $script:ErrorActionPreference = $script:SavedErrorActionPreference }
    }
}

if ($env:WDS_INSTALL_LIBONLY -ne '1') { Start-Installer }
