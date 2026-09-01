# README.md Clarifications

* Ignore missing image locations in the `README.md` file.  The images
  are for human reference when viewing the repository home page.

* For the purposes of the skill, re-route URLs for the helm chart to the direct URL
  for this release.  The URL for the latest version is in the `README.md` as
  `https://github.com/checkmarx-ts/cxone-scan-scheduler/releases/latest/download/cxone-scan-scheduler_helm.tgz`
  which is correct for the `latest` version.  Unless the user specifically asks for the latest
  version, use the URL for the direct release tag:
  `https://github.com/checkmarx-ts/cxone-scan-scheduler/releases/download/<appVersion>` where `<appVersion>`
  comes from the Helm chart packaged in this skill.

