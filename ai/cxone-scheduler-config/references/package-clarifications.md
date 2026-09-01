# Package Clarifications

* The repository URL for `cxone-scan-scheduler` is `https://github.com/checkmarx-ts/cxone-scan-scheduler`.
* The version of `cxone-scan-scheduler` for which this skill applies comes from `appVersion` in the Helm chart
  packaged with this skill.
* A released version has a version stamp in the form of `v<MAJOR>.<MINOR>`.
* A pre-release version appends the prerelease information to the release version.
* Release artifacts are located at `https://github.com/checkmarx-ts/cxone-scan-scheduler/releases/tag/<appVersion>`.
* Container images can be found at `https://github.com/checkmarx-ts/cxone-scan-scheduler/pkgs/container/cxone%2Fscan-scheduler`
* The container image can be obtained with the command `docker pull ghcr.io/checkmarx-ts/cxone/scan-scheduler:<appVersion>`
  where `<appVersion>` is found in the Helm chart packaged with this skill.  Using `latest` will get the latest
  released version which may differ from the version in this skill.  Use the version in this skill unless the
  user specifically asks for `latest`.

