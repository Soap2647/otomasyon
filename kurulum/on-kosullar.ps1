# One-time prerequisites for the nightly job. Run after approval (Administrator not required for winget pin).
# 1) gitleaks: secret scan before every wip push (without it, git pushes are skipped)
winget install --id Gitleaks.Gitleaks -e --silent --accept-source-agreements --accept-package-agreements
# 2) pin tools the user updates by hand
foreach ($id in 'OpenJS.NodeJS', 'Python.Python.3.12', 'Python.PythonInstallManager', 'Python.Launcher') {
  winget pin add --id $id --blocking --accept-source-agreements
}
winget pin list
