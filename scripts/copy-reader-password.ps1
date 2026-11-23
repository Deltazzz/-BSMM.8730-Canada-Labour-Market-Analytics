# Copies the local read-only report password for Power BI's Database sign-in.
$credential = Import-Clixml (Join-Path $env:LOCALAPPDATA 'JobBankMySQL\instance\jobbank_reader.xml')
Set-Clipboard -Value $credential.GetNetworkCredential().Password
Write-Output 'Password copied for jobbank_reader. Paste into Power BI, then clear the clipboard with Set-Clipboard -Value $null.'
