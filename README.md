# Checkmarx One Scan Scheduler

This provides a method of scheduling scans in Checkmarx One.  Some
highlights of how it works:

* Runs in a container that builds the scan schedule on startup.
* Works for single- or multi-tenant Checkmarx One.
* Scans can be scheduled per project using one or more of the
following methods:
    * A tag applied to the project with scan details.
    * By the project's group membership.
    * An optional default scan schedule that is applied to projects
    that are not scheduled through one any other schedule criteria.
* Scan schedules are updated periodically to adjust schedules
based on changes in projects that would affect schedule assignments.

## Scheduling Project Scanning

Scheduling scans for a project require the project has a configured way to clone code from the repository to be scanned.
If the repository is private, a supported set of credentials must also be configured so that the code for scanning can be
cloned.

The following methods can be used to schedule a scan:

* The project is tagged with a `schedule` tag that specifies the schedule scan parameters.
* A project is assigned to one or more groups with a configured group schedule.
* A default schedule is defined and the project is not configured for a scheduled scan via any other method.


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

If the branch is not provided and no primary branch has been set, the scan will not be scheduled.

#### Element: `<engines>`

The value for `<engines>` can be one of the following:


* `all` to scan with all engines
* Empty, which implies `all`
* A single engine name, which is currently one of the following:
    * `sast`
    * `sca`
    * `kics`
    * `apisec`
* A comma-separated list of two or more of the single engine names.

Duplicated or invalid engine names are ignored.  If no valid set of
engine names can be determined, `all` is assumed.

### Scheduling via Assigned Groups

Using environment variables, `<schedule>` values can be assigned to
projects by matching the project's group assignment.  See [Environment Variables](#environment-variables) for information about the group 
scheduling environment variables.

Projects can be assigned to zero or more groups.  If a project is not
assigned to a group, a schedule will only be executed if the project
has a `schedule` tag of a default schedule has been defined.  
Group schedules only execute using the project's
configured primary branch; if a project does not have a primary branch
configured, the scan is not scheduled.


### Schedule Execution Logic

The execution environment is intended to be ephemeral.  A shutdown
and restart will cause the system to re-initialize all schedules by
crawling the projects and assigning schedules based on all methods used
to determine a project's scan schedule.

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
project's primary branch, the sast engine, and a custom defined
scan policy name.

```
schedule:weekdays-midnight::sast
```

Schedule a daily scan at midnight limited to weekdays using the branch `master` with the sast and sca engines.

```
schedule:weekdays-midnight:master:sast,sca
```

## Scan Scheduler Configuration

The Scan Scheduler runs as a container.  At startup, it crawls the tenant's projects and creates the scan schedule.  It then 
checks periodically for any schedule changes and updates 
the scan schedules accordingly.

### Required Secrets

Docker secrets are used to securely store secrets needed during runtime.
The secrets are mounted in `/run/secrets/<secret-name>`.

The secrets required are:

* `cxone_tenant` - The name of the Checkmarx One tenant.
* `cxone_oauth_client_id` - The Checkmarx One OAuth client identifier.
* `cxone_oauth_client_secret` - The Checkmarx One OAuth client secret.

### OAuth Client

OAuth Clients can be created through Checkmarx One Identity and Access Management.  An OAuth client
should be created that is used only by the Scan Scheduler.

The built-in composite role `ast-scanner` can be assigned to the OAuth client and will work
for scenarios where schedules are determined by project tags.

If using the group scheduling configuration, an additional IAM Role `manage-groups` must
also be assigned to the OAuth client so that is can retrieve group names for matching
the configured group schedule assignments.  If not using group schedule assignments, the
OAuth client does not require this role.

A custom role with limited capabilities may be configured if desired.  The `ast-scanner`
role will allow the scan scheduler to see all projects, create
scheduled scan for all projects, and execute scans for all projects. 
This may not always be a desirable scenario.  To limit
the Scan Scheduler to limit project visibility via group membership
, create a custom composite role with the following minimum individual roles assigned:

|Role Type|Name|
|-|-|
|IAM|`manage-groups` (optional)|
|IAM|`user`|
|CxOne|`create-scan-if-in-group`|
|CxOne|`view-scans-if-in-group`|
|CxOne|`view-projects-if-in-group`|
|CxOne|`view-project-params-if-in-group`|

If the role permissions change for the OAuth client, restarting the Scan Scheduler is required.

### Environment Variables

The following runtime environment variables are required to configure the system.  

|Variable|Default|Description|
|-|-|-|
|`CXONE_REGION`|N/A| Required for use with multi-tenant Checkmarx One tenants.  The endpoint region used by your Checkmarx One tenant. For a list of valid region values, see [the regions section](#regions) below. This can be one of the following values: `US`, `US2`, `EU`, `EU2`, `ANZ`,`India`, or `Singapore`. If this is not supplied, the `SINGLE_TENANT_` variables must be defined.|
|`SINGLE_TENANT_AUTH`|N/A|The name of the single-tenant IAM endpoint host. (e.g. `myhost.cxone.cloud`)|
|`SINGLE_TENANT_API`|N/A|The name of the single-tenant API endpoint host. (e.g. `myhost.cxone.cloud`)|
|`DEFAULT_SCHEDULE`|N/A|This defines the default schedule to apply to projects that do not have `schedule` tags.  If not provided, projects that do not meet scheduling criteria via tags or group schedules will not be scanned with the scheduler. The value of this environment variable is a valid `<schedule>` string. |
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
POLICY_MYPOLICY=0 0 * * 1-5
```

Policy definition named `general-audit-policy` that scans every 30 minutes on weekdays.  It can be referenced with
the tag `schedule:general-audit-policy` or `schedule:general_audit_policy`.
```
POLICY_GENERAL_AUDIT_POLICY=0,30 * * * 1-5
```

## Execution

TODO: ghcr.io tag
TODO: Comments on integrating it with an enterprise service.

TODO: Running it locally for testing purposes.
docker run --rm -it -p 5678:5678 -v $(pwd)/run/secrets/:/run/secrets --env-file .env scheduler:latest -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:5678 scheduler.py


TODO: Developer debugging

docker run --rm -it -p 5678:5678 -v $(pwd)/run/secrets/:/run/secrets --env-file .env scheduler:latest -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:5678 scheduler.py


docker run --rm -it -p 5678:5678 -v $(pwd)/run/secrets/:/run/secrets --env-file .env scheduler:latest -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:5678 scheduler

TODO: Evaluate schedule


## Other Notes

### Scan Timing

It is possible to use a crontab string to schedule scans at a high repeat rate.
This is generally a bad idea as it will likely cause scans to queue while waiting for
available resources.  This can lead to experiencing longer scan times for
non-scheduled scans.


### Scheduling Controls via Group Membership

It is possible to assign group membership to the OAuth Client.  The the minimum roles
for a [custom composite role](#oauth-client) can be used in conjunction with group
membership for different ways of controlling how scans are scheduled.

By default, any project viewable with the role and group membership assigned to
the OAuth client can be [tagged](#scheduling-via-tags) and the tag will take
precedence over any other schedule assignment logic.

Projects assigned to the same groups as the OAuth Client will be visible
for evaluating scheduling.  The repository URL and primary branch along with
the project id are used to set the scan schedule.  The schedule can be assigned
using the groups where both the OAuth Client and the project are members in
addition to any other group for which the project is a member.  The OAuth Client
does not need to be a member of all the groups where the project is a member
to be able to schedule scans.

An example of how this might work is as follows:

Assume we have the following projects and group memberships:

* Project A: `/production`
* Project B: `/audit`
* Project C: `/production`, `/audit`

In this scenario, assume the OAuth client is a member of `/production`
but **is not** a member of `/audit`.  If the Scan Scheduler were configured
to assign a schedule to group `/audit`, here is the schedule that would
be created from the projects:

* Project A: No scheduled scan since Project A is not a member of `/audit`.
* Project B: No scheduled scan since the OAuth Client is not a member of `/audit` and can't see the project.
* Project C: A scan would be scheduled since:
    1. The project is a member of `/production` and the OAuth Client can see projects in the same group.
    2. The project is a member of `/audit` and there is a group configuration that matches `/audit`.

This method is primarily useful to automate the scheduling of scans for projects as part of
an onboarding process.  While it is possible to schedule scans with individual project tags,
there may be cases where using group membership is a simpler method of assigning
scan schedules.


