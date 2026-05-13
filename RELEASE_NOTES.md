# Release Notes

## v2.1
* Docker image upgraded to remediate CVE-2026-31431 (Copy Fail)
* The container now executes as a low-privileged user.
* As of the time of release, CVE-2026-43284 (Dirty Frag) is reported to affect Ubuntu 26.04 with no
  fix available.  The base docker image does not load the affected modules.  This is effectively equivalent to the
  "Manual mitigation" documented here: https://ubuntu.com/blog/dirty-frag-linux-vulnerability-fixes-available

## v2.0
* The memory footprint for the scheduler has been reduced significantly by removing the use of crond.
* The `hourly` and `daily` default schedules can now be overridden via configuration.
* The execution option `scanner` has been removed as it is no longer required for
executing scans.

## v1.8
* Implemented optional throttling by source fetch.
* Implemented optional check for scans occurring a previous number of hours.  If so, the scheduled scan is skipped.
* A Helm chart is now available as part of the release artifacts.  You can review the `values.yaml` file in the
templates directory for configuration guidance when using Helm.

## v1.7
* Fixed an issue causing the scheduler to not start due to a Checkmarx One breaking API change when retrieving groups.
* Fixed an issue causing code repository import projects to not be scheduled due to a Checkmarx One breaking API change
  when retrieving code repository details.

## v1.6
* Added better handling when the SCM credentials expire for a code repository import project.

## v1.5
* Support for manual projects improved.  If you have a manual project with a configured PAT, repository URL, and branch then the scheduler
can kick off a scan.  (If the PAT is expired, the scan will fail.)
* Support for additional engines:
  * containers
  * 2ms
  * scorecard
* Added throttling to API calls while invoking scans.
* Added resilience to common network failures.  Retry options can be configured to increase the number of retries before failure.

## v1.4
* Logic for selecting primary branch updated.  If only one protected branch is defined in the code repository
import configuration, it is used as the scan branch regardless of if it is considered a default branch by the SCM.

## v1.3

* Bugfixes
  * Some projects without tags that aren't eligible for scheduling were not displayed in the audit report.
  * It was possible to set the default schedule to use a policy that was not defined.
  * Schedule execution scripts that should have been removed when a schedule was deleted were not being removed.
  * Group scheduling was broken by a change to an undocumented API.  The published Access Management API is now used.
* Replace the local `cxone_api` module with the [cxone-async-api](https://github.com/checkmarx-ts/cxone-async-api) shared library.

## v1.2

* Support added for projects created by code repository integrations.
* Bug fixes.
* Documentation updates.

## v1.1

* Bug fix for auth token not refreshing properly.
* Added log output to indicate number of scheduled scans on start and schedule update.
* Added support for loading custom CA certificates at startup.

## v1.0

Initial release
