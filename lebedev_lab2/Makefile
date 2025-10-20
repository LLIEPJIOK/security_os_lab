CERT_NAME ?= Lab2Cert
CERT_PATH ?= C:/Users/ld200/Lab2Cert.pfx
CERT_PWD ?= P@ssw0rd

export CERT_NAME
export CERT_PATH
export CERT_PWD

.PHONY: run
run:
	@go run main.go

.PHONY: cert
cert:
	@powershell -Command "New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=$(CERT_NAME)' -CertStoreLocation 'Cert:\\CurrentUser\\My' -KeyExportPolicy Exportable"
	@powershell -Command "$$cert = Get-ChildItem Cert:\\CurrentUser\\My | Where-Object { $$_.Subject -eq 'CN=$(CERT_NAME)' }; Export-PfxCertificate -Cert $$cert -FilePath '$(CERT_PATH)' -Password (ConvertTo-SecureString -String '$(CERT_PWD)' -Force -AsPlainText)"

.PHONY: remove_cert
remove_cert:
	@powershell -Command "Get-ChildItem Cert:\CurrentUser\My | Where-Object { $$_.Subject -eq 'CN=$(CERT_NAME)' } | ForEach-Object { Remove-Item -LiteralPath $$_.PSPath -Force; Write-Host 'Deleted:' $$_.Subject }"
	del "$(subst /,\,$(CERT_PATH))"

