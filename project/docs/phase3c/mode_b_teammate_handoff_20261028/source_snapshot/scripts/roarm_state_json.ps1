# Firmware uses both T (message type) and t (wrist). PSCustomObject keys
# are case-insensitive in Windows PowerShell 5.1 and PowerShell 7.
function ConvertFrom-RoArmStateJson {
    param([string]$RawJson)
    if ($RawJson -cmatch '"message_type"\s*:') { return $null }
    $typeKeys = [regex]::Matches($RawJson, '"T"\s*:')
    if ($typeKeys.Count -ne 1) { return $null }
    $renamed = [regex]::Replace($RawJson, '"T"\s*:', '"message_type":')
    try { $parsed = ConvertFrom-Json -InputObject $renamed -ErrorAction Stop } catch { return $null }
    if ($parsed.message_type -is [string] -or $parsed.message_type -is [bool] -or
        $parsed.message_type -notin @(-15,1051)) { return $null }
    foreach ($field in @('b','s','e','t','r','g','x','y','z','tit')) {
        $keys = [regex]::Matches($RawJson, ('"' + $field + '"\s*:'))
        if ($keys.Count -ne 1) { return $null }
        $prop = $parsed.PSObject.Properties[$field]
        if ($null -eq $prop -or $null -eq $prop.Value -or $prop.Value -is [string] -or $prop.Value -is [bool]) { return $null }
        try { $number = [double]$prop.Value } catch { return $null }
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) { return $null }
    }
    return $parsed
}
