$certs = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*The Spike Cross Launcher*" }
if ($certs.Count -eq 0) {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=The Spike Cross Launcher, O=TheSpikeProject" -CertStoreLocation "Cert:\CurrentUser\My"
} else {
    $cert = $certs[0]
}

if (Test-Path "TheSpikeLauncher.exe") {
    Set-AuthenticodeSignature -FilePath "TheSpikeLauncher.exe" -Certificate $cert
    Write-Host "Signed root TheSpikeLauncher.exe"
}

if (Test-Path "dist\TheSpikeLauncher\TheSpikeLauncher.exe") {
    Set-AuthenticodeSignature -FilePath "dist\TheSpikeLauncher\TheSpikeLauncher.exe" -Certificate $cert
    Write-Host "Signed dist\TheSpikeLauncher\TheSpikeLauncher.exe"
}

Export-Certificate -Cert $cert -FilePath "TheSpikeLauncher.cer" -Force
Write-Host "Code signing completed successfully!"
