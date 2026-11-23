[CmdletBinding()]
param([string]$ServerHome)
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'JobBankMySQL'
$instance = Join-Path $root 'instance'
$port = 3307
$config = Join-Path $instance 'my.ini'
if (!$ServerHome) {
    if (Test-Path $config) {
        $ServerHome = ((Select-String -LiteralPath $config -Pattern '^basedir=(.+)$').Matches[0].Groups[1].Value).Trim('"')
    } else {
        $ServerHome = Join-Path $root 'server\mysql-8.4.11-winx64'
    }
}
$exe = Join-Path $ServerHome 'bin\mysqld.exe'
if (!(Test-Path $exe)) { throw 'Supply -ServerHome with the path of your extracted Oracle MySQL 8.4 Windows ZIP.' }
if (!(Test-Path $instance)) { New-Item -ItemType Directory -Path $instance | Out-Null }
$lock = [System.IO.File]::Open((Join-Path $instance 'startup.lock'),'OpenOrCreate','ReadWrite','None')
try {
    $pidfile = Join-Path $instance 'server.pid'
    if (Test-Path $pidfile) {
        $running = Get-Process -Id ([int](Get-Content $pidfile)) -ErrorAction SilentlyContinue
        if ($running -and $running.Path -eq (Resolve-Path $exe).Path) {
            Write-Output "MySQL is running on 127.0.0.1:$port."
            return
        }
    }
    $client = New-Object Net.Sockets.TcpClient
    try { $client.Connect('127.0.0.1',$port) } catch [Net.Sockets.SocketException] {} finally { $occupied = $client.Connected; $client.Dispose() }
    if ($occupied) { throw "Another application is listening on port $port." }
    $data = Join-Path $instance 'data'
    $log = Join-Path $instance 'mysql.err'
    $bootstrap = Join-Path $instance 'first-start.sql'
    if (!(Test-Path $config)) {
        $ini = @('[mysqld]', ('basedir="'+$ServerHome.Replace('\','/')+'"'), ('datadir="'+$data.Replace('\','/')+'"'),
            ('log-error="'+$log.Replace('\','/')+'"'), ('pid-file="'+$pidfile.Replace('\','/')+'"'),
            "port=$port", 'bind-address=127.0.0.1', 'mysqlx=0','require_secure_transport=ON',
            'character-set-server=utf8mb4','collation-server=utf8mb4_0900_bin','innodb_buffer_pool_size=256M')
        [System.IO.File]::WriteAllLines($config, $ini, [Text.UTF8Encoding]::new($false))
    }
    if (!(Test-Path (Join-Path $instance 'initialized'))) {
        if (!(Test-Path $data)) {
            & $exe "--defaults-file=$config" --initialize-insecure
            if ($LASTEXITCODE -ne 0) { throw "Initialization failed. See $log" }
        } elseif (!(Test-Path $bootstrap)) {
            throw "Partial initialization in $instance. Inspect the local error log before retrying."
        }
        if (!(Test-Path $bootstrap)) {
            $statements = @()
            foreach ($name in @('root','jobbank_loader','jobbank_reader')) {
                $bytes = New-Object byte[] 32
                $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
                try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
                $password = [Convert]::ToBase64String($bytes)
                $secure = ConvertTo-SecureString $password -AsPlainText -Force
                [PSCredential]::new($name,$secure) | Export-Clixml (Join-Path $instance "$name.xml")
                if ($name -eq 'root') {
                    $statements += "ALTER USER 'root'@'localhost' IDENTIFIED BY '$password';"
                } else {
                    $statements += "CREATE USER IF NOT EXISTS '$name'@'localhost' IDENTIFIED BY '$password';"
                }
            }
            $statements += 'CREATE DATABASE IF NOT EXISTS jobbank CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;'
            $statements += "GRANT SELECT, INSERT, DELETE, CREATE, DROP, CREATE VIEW, SHOW VIEW ON jobbank.* TO 'jobbank_loader'@'localhost';"
            [System.IO.File]::WriteAllLines($bootstrap,$statements,[Text.UTF8Encoding]::new($false))
        }
    }
    $arguments = @('--defaults-file="'+$config+'"')
    if (Test-Path $bootstrap) { $arguments += '--init-file="'+$bootstrap+'"' }
    $process = Start-Process $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru
    $admin = Join-Path $ServerHome 'bin\mysql.exe'
    $cred = Import-Clixml (Join-Path $instance 'root.xml')
    $saved = $env:MYSQL_PWD
    try {
        $env:MYSQL_PWD = $cred.GetNetworkCredential().Password
        $ready = $false
        for ($attempt=0; $attempt -lt 50; $attempt++) {
            if ($process.HasExited) { throw "Startup failed. See $log" }
            & $admin --no-defaults --host=127.0.0.1 "--port=$port" --user=root --ssl-mode=REQUIRED --connect-timeout=1 --batch --skip-column-names --execute="SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='jobbank'" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ready=$true; break }
            Start-Sleep -Milliseconds 400
        }
        if (!$ready) { throw "Server readiness check failed. See $log" }
        if (Test-Path $bootstrap) {
            # A table-scoped grant is issued by grant-reader.ps1 once the report view exists.
            [IO.File]::WriteAllText((Join-Path $instance 'initialized'),'ready')
            Remove-Item -LiteralPath $bootstrap
        }
    } finally { $env:MYSQL_PWD = $saved }
    Write-Output "MySQL is running on 127.0.0.1:$port."
} finally { $lock.Dispose() }
