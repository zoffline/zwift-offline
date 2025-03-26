$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$hosts = get-content $hostsPath
$hosts | Foreach {if ($_ -match '^\s*([^#].*?\d{1,3}.*?zwift.*)') 
                  {"# " + $matches[1]} else {$_}} |
         Out-File $hostsPath -enc ascii