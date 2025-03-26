$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$hosts = get-content $hostsPath
$hosts = $hosts | Foreach {if ($_ -match '^\s*#\s*(.*?\d{1,3}.*?zwift.*)')
                           {$matches[1]} else {$_}}
$hosts | Out-File $hostsPath -enc ascii