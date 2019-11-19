# Switch WinRM certificate
#
#   This script will take a certificate thumbprint as required input, search through the local certificate store looking for that thumbprint
#   If it finds it, it will switch the WinRM service over to using that certificate for HTTPS WinRM
#
#   WinRM HTTPS requires a local computer "Server Authentication" certificate with a CN matching the hostname, that is not expired, revoked, or self-signed to be installed.
#

# Get required certificate thumbprint
param ([Parameter(Mandatory=$true)][string]$thumbprint)

# Show privided thumbprint and trimmed thumbprint
# When passing thumbprint as input from the output in Ansible, brackets and u are pre-pended and post-pended to the thumbprint
write-output "Provided thumbprint: $thumbprint"
$thumbprint = $thumbprint.Trim()
$thumbprint = $thumbprint.TrimStart("[","u")
$thumbprint = $thumbprint.TrimEnd("]")
write-output "Trimmed thumbprint: $thumbprint"

# Log file for logging script output
$log_file = "C:\WinRM-SwitchCert.log"

# Write to log file function
Function write-log {
   Param ([string]$logstring)
   Add-content $log_file -value $logstring
   write-output $logstring
}

write-log "SSL certificate thumbprint provided: $thumbprint"

# Log name of HTTPS WinRM listener
$ListenerName = dir WSMan:\localhost\Listener | Where Keys -like *https* | select -expand Name
write-log "WinRM HTTPS listener name: $ListenerName"

$certpath = (get-childitem "WSMan:\localhost\Listener\$ListenerName" | Where Name -like "CertificateThumbprint").pspath 
#write-output $certpath

# Loop over existing thumbprints in local certificate store to check if the thumbprint exists
# If thumbprint found, switch WinRM to using it
write-log "Looping over existing thumbprints to see if thumbprint exists..."
$table = (Get-ChildItem Cert:\LocalMachine\my).Thumbprint
$found_cert = $false
$switched_cert = $false
foreach ($row in $table)
{
  write-log "Existing thumbprint: $row"
  If ($row -eq $thumbprint) {
    $found_cert = $true
    write-log "Thumbprint '$thumbprint' exists, switching WinRM to the new certificate"
    $ErrorActionPreference="SilentlyContinue"
    Stop-Transcript | out-null
    $ErrorActionPreference = "Continue"
    Start-Transcript -path $log_file -append
    try {
        Set-Item -Path "WSMan:\localhost\Listener\$listenername\CertificateThumbprint" -Value $thumbprint -Force | Tee-Object -FilePath $log_file -Append   
        $cmd = "winrm set winrm/config/service '@{CertificateThumbprint=`"$thumbprint`"}'"
        Invoke-Expression $cmd | Tee-Object -FilePath $log_file -Append
        $switched_cert = $true
        write-log "Successfully switched WinRM to new certificate thumbprint"
    } catch {
        $switched_cert = $false
        write-log "WinRM switch reported error, check log file entry"
    }
    Stop-Transcript
  }
}

# Did not find thumbprint in certificate store, report and exit
if ($found_cert -eq $false) {
    write-log "Thumbprint '$thumbprint' does not exist in certificate store! exiting script"
    exit 2
}

# Switching to thumbprint failed, check logs for errors
if ($switched_cert -eq $false) {
    write-log "WinRM switch failed and reported error, please see log file entry"
    exit 2
}

write-log "Done!"

exit 0
