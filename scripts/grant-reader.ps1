# Run once after building the local MySQL schema.
$ErrorActionPreference = 'Stop'
$instance = Join-Path $env:LOCALAPPDATA 'JobBankMySQL\instance'
$base = ((Select-String -LiteralPath (Join-Path $instance 'my.ini') -Pattern '^basedir=(.+)$').Matches[0].Groups[1].Value).Trim('"')
$rootCredential = Import-Clixml (Join-Path $instance 'root.xml')
$saved = $env:MYSQL_PWD
try {
    $env:MYSQL_PWD = $rootCredential.GetNetworkCredential().Password
    & (Join-Path $base 'bin\mysql.exe') --no-defaults --host=127.0.0.1 --port=3307 --user=root --ssl-mode=REQUIRED --execute="GRANT REFERENCES ON jobbank.* TO 'jobbank_loader'@'localhost'; GRANT SELECT ON jobbank.powerbi_postings TO 'jobbank_reader'@'localhost';"
    if ($LASTEXITCODE -ne 0) { throw 'Grant failed. Build the MySQL schema first.' }
} finally { $env:MYSQL_PWD = $saved }
