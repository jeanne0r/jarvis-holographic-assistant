# PREPARED ONLY, NOT a proven isolation boundary until negative probes pass.
# Rules target only the NEW account. No global policy, public opening or sshd change.
param([switch]$Approved,[ValidateSet('Apply','Remove')][string]$Action='Apply')
$ErrorActionPreference='Stop'
if(-not $Approved){throw 'Separate scoped firewall approval required'}
if($env:COMPUTERNAME -ne 'GAMER'){throw 'Approved GAMER machine only'}
$names=@('JarvisHermesLab-v4-egress','JarvisHermesLab-v6-egress')
$sid=(Get-LocalUser -Name hermeslab).SID.Value
if($Action -eq 'Remove') {
 foreach($name in $names) {
  $rule=Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue
  if($rule) {
   $filter=$rule | Get-NetFirewallSecurityFilter
   if($rule.Group -ne 'JarvisHermesLab-phase4' -or $filter.LocalUser -notmatch ([regex]::Escape($sid)+'[;) ]')){throw 'Unknown rule scope: do not remove'}
   $rule | Remove-NetFirewallRule
  }
 }
 return
}
foreach($name in $names){if(Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue){throw 'Existing rule preserved; inspect first'}}
$sid=(Get-LocalUser -Name hermeslab).SID.Value
$sddl='D:(A;;CC;;;'+$sid+')'
New-NetFirewallRule -Name $names[0] -Group 'JarvisHermesLab-phase4' -DisplayName $names[0] -Direction Outbound -Action Block -Profile Any -LocalUser $sddl -RemoteAddress @('0.0.0.0-126.255.255.255','128.0.0.0-255.255.255.255') | Out-Null
New-NetFirewallRule -Name $names[1] -Group 'JarvisHermesLab-phase4' -DisplayName $names[1] -Direction Outbound -Action Block -Profile Any -LocalUser $sddl -RemoteAddress @('::/1','8000::/1') | Out-Null
# Bind APIs/tunnels to IPv4 loopback. Windows local IPv6 loopback is also accessible.
# Test external IPv6 separately, plus SSH tunnel, MCP and model relay before any agent run.
# If user scoping/IPv6/loopback differs on this Windows build, STOP; never broaden rules.
