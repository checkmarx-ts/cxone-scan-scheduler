# Scan Scheduler

A container that will monitor a CxOne tenant and schedule scans for projects tagged appropriately.


## Scheduling Project Scanning

Scheduling scans for a project require the project has a configured way to clone code from the repository to be scanned.
If the repository is private, a supported set of credentials must also be configured so that the code for scanning can be
cloned.

The following methods can be used to schedule a scan:

* The project is tagged with a `schedule` tag that specifies the schedule scan parameters.
* A project is assigned to one or more groups with a configured group schedule.
* A global default schedule is defined and the project is not configured for a scheduled scan via any other method.


### Scheduling via Tags

Scheduling a project for scanning requires adding a tag to the project in the form of:

```
schedule:<schedule>:<branch>:<engines>
```

Only one `schedule` tag may be added to a project.

#### Element: `<schedule>`

The `<schedule>` for scans can be one of the following values:

* `hourly`
* `daily`
* A custom configured [policy name](#policy-definitions).


#### Element: `<branch>`

The name of the branch to schedule.  If not provided, the primary branch selected in the project view is used.  Selection of the primary branch is shown in the image below:

![primary branch selection](images/primary-branch.png "Primary Branch Selection")

If the branch is not provided and no primary branch has been set, the scan will not execute.

#### Element: `<engines>`

The value for `<engines>` can be one of the following:


* `all` to scan with all engines
* Empty, which implies `all`
* A single engine name, which is currently one of the following:
    * `sast`
    * `sca`
    * `kics`
    * `api`
* A comma-separated list of two or more of the single engine names.

### Scheduling via Assigned Groups

Using environment variables, `<schedule>` values can be assigned to
projects by matching the project's group assignment.  See [Environment Variables](#environment-variables) for information about the group 
scheduling environment variables.

Projects can be assigned to zero or more groups.  If a project is not
assigned to a group, a schedule will only be executed if the project
has a `schedule` tag.  Group schedules only execute using the project's
configured primary branch; if a project does not have a primary branch
configured, the scan is not scheduled.


### Schedule Execution Logic

The execution environment is intended to be ephemeral.  A shutdown
and restart will cause the system to re-initialize all schedules by
crawling the projects and assigning schedules based on `schedule` tags
and any configured group schedules.

A project can have more than one scheduled time if it has a `schedule` tag
and/or has a schedule assigned based on membership in one or more groups.
The project's `schedule` tag will always take precedence over any
group schedule assignments.  If a project is assigned to more 
than one group matching a group schedule configuration, it will be scheduled with all group schedules.

At the scheduled time of a scan, the scan will execute unless another
scheduled scan is executing.  This will prevent overlapping schedules
starting multiple scans or long-running scans from being started before
the previously scheduled scan is completed.


### Example Tags

Schedule a daily scan of the `master` branch using all engines.

```
schedule:daily:master:all
```


Schedule a daily scan of the project's primary branch using all engines.

```
schedule:daily
```

Schedule a daily scan at midnight limited to weekdays using the 
project's primary branch and the sast engine.

```
schedule:* * * * 1-5::sast
```

Schedule a daily scan at midnight limited to weekdays using the branch `master` with the sast and sca engines.

```
schedule:* * * * 1-5:master:sast,sca
```

## Scan Scheduler Configuration

The Scan Scheduler runs as a container.  At startup, it crawls the tenant's projects and creates the scan schedule.  It then 
checks periodically for any schedule changes and updates 
the scan schedules accordingly.

### Required Secrets

Docker secrets are used to securely store secrets needed during runtime.
The secrets are mounted in `/run/secrets/<secret-name>`.

The secrets required are:

* `cxone_tenant` - The name of the CheckmarxOne tenant.
* `cxone_oauth_client_id` - The CheckmarxOne OAuth client identifier.
* `cxone_oauth_client_secret` - The CheckmarxOne OAuth client secret.

### OAuth Client

OAuth Clients can be created through CheckmarxOne Identity and Access Management.

TODO: What roles for scanning?

IAM Roles

`manage-groups` only required if doing group schedule mapping.


### Environment Variables

The following runtime environment variables are required to configure the system.  

|Variable|Default|Description|
|-|-|-|
|`CXONE_REGION`|US|The endpoint region used by your CheckmarxOne tenant. For a list of valid region values, see [the regions section](#regions) below.|
|`GLOBAL_DEFAULT_SCHEDULE`|N/A|This defines the default schedule to apply to projects that do not have `schedule` tags.  If not provided, projects that do not meet scheduling criteria via tags or group schedules will not be scanned with the scheduler. The value of this environment variable is a valid `<schedule>` string. |
|`GROUP_x`|N/A|`GROUP_` is considered a prefix with the remainder of the environment variable name being a key value.  The key value is used to match other environment variables having the same key value. The value for this environment variable is a group path in the form of `/value/value/...` matching a group defined in the Checkmarx One tenant. This environment variable can be defined to apply a schedule to projects assigned to the defined group without the need to assign a `schedule` tag to the project.
|`SCHEDULE_x`|N/A|`SCHEDULE_` is considered a prefix with the remainder of the environment variable name being a key value.  The key value is used to match other environment variables having the same key value.  The value of this environment variable is a valid `<schedule>` string.|
|`LOG_LEVEL`|INFO|The logging level to control how much logging is emitted.  Set to `DEBUG` for more verbose logging output.|
|`SSL_VERIFY`|`True`| Set to `False` to turn off SSL certificate validation.|
|`PROXY`| N/A | Set to the URL for an unauthenticated proxy. All http/s traffic will route through the specified proxy.|
|`UPDATE_DELAY_SECONDS`| 43200 | The number of seconds to delay between checking for updates in the schedule.|



### Policy Definitions

Policy definitions allow for scheduled times to be named with a custom name.  These are configured
as environment variables named `POLICY_<name>` where `name` will be matched with the schedule name
using the following criteria:

* Matches are case-insensitive.
* Separators such as underscore (`_`) and dashes (`-`) are considered equivalent.

The value assigned to the environment variable is a valid 
[crontab string](https://www.adminschoice.com/crontab-quick-reference). 

#### Examples of Policy Definitions

Policy definition named `mypolicy` that scans at midnight on weekdays.  It can be referenced with the tag `schedule:mypolicy`.
```
POLICY_MYPOLICY=* * * * 1-5
```

Policy definition named `general-audit-policy` that scans at midnight on weekdays.  It can be referenced with
the tag `schedule:general-audit-policy` or `schedule:general_audit_policy`.
```
POLICY_GENERAL_AUDIT_POLICY=* * * * 1-5
```


### Regions

Valid region values:

* US
* US2
* EU
* EU2
* ANZ
* India
* Singapore


## Best Practices

### Scan Timing

It is possible to use a crontab string to schedule scans at a high repeat rate.
This is generally a bad idea as it will likely cause scans to queue while waiting for
available resources.  This can lead to experiencing longer scan times for
non-scheduled scans.