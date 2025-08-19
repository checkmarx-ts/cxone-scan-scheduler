# Release Notes

## v1.5
* Support for manual projects improved.  If you have a manual project with a configured PAT, repository URL, and branch then the scheduler
can kick off a scan.  (If the PAT is expired, the scan will fail.)
* Support for additional engines:
  * containers
  * 2ms
  * scorecard
* Added throttling to API calls while compiling the schedule and invoking scans.


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
