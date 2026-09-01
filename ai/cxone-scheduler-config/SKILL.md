---
name: cxone-scheduler-config
description: An assistant for configuring and deploying the cxone-scan-scheduler.
---

# Purpose

This skill is to assist in the configuration and deployment of the Checkmarx One scan scheduler
(forthwith referenced as `cxone-scan-scheduler`).  It should be noted that the `cxone-scan-scheduler`
is an externally deployed scheduler that does not use the Checkmarx One native scan scheduling
capabilities.

## Initialization

* You are to ask the user which use-case applies to their chosen deployment method.

* Reference `references/README.md` for the documentation for `cxone-scan-scheduler`.  Also reference 
  `references/readme-clarifications.md` for clarification on readme

* Reference `references/RELEASE_NOTES.md` for documentation related to the changes between versions
  of `cxone-scan-scheduler`.
  
* Reference `references/package-clarifications.md` to understand the version and location of `cxone-scan-scheduler`.

* Reference `references/understanding-general-issues.md` to know when to issue warnings about potential
  misconfigurations.

## Use Case: Deployment as a Docker Container

In this use-case, the `cxone-scan-scheduler` is executed as a Docker container using `docker` or `docker-compose`.

In this use case:

* The final output is:
  * A file containing environment variables for use with `docker` execution.
  * A command line example of how to execute `cxone-scan-scheduler` using the `latest` container tag with `docker`

* The `docker` execution command is intended to only be an example.  The user is required to understand how
  to translate the command for their deployment case.

* The user is expected to understand how to translate the example execution command for use with `docker-compose`.

* The user is reminded that they must configure the execution of the container to automatically start when the
  container host system starts.  It is expected that the user will research the various methods of how to accomplish
  start of the container upon system startup.

* The user should be informed of the ability to execute the `cxone-scan-scheduler` to retrieve the audit output.

## Use Case: Development Execution

This use case is nearly identical to the use-case `Deployment as a Docker Container` except that:

* The intention is to execute the scheduler locally with the ability to attach a remote Python debugger.

* The output command is only for use with `docker`.

* The output command contains the parameters needed to enable attaching a Python debugger to the running
  container.

## Use Case: Deployment in Kubernetes

In this use-case, the `cxone-scan-scheduler` is executed as a Kubernetes `Deployment`. For this use case:

* The output of this use-case is:
  * The `helm` commands for installation or upgrade with `--set` configuration options in `references/helm/values.yaml`
    that correspond to environment variables explained in `references/README.md`.
  * The `kubectl` commands required to deploy elements that are referenced by the `helm` template (refer to `references/helm/*`).


For additional context, reference `references/clarification-kubernetes.md`.

## Final Output

* Before showing any outputs, you MUST validate that required configuration elements have been provided with
  configured values.

* At the final output, the user should be reminded to provide the required secrets (referenced in `references/README.md`).
  The user should also be reminded of the roles and authorizations that are required to be assigned to
  credentials such that the scheduler can interact with Checkmarx One.

* Explain that user-supplied scan policies can be executed by adding tags to projects.  Show
  some tag examples such as:

  * A tag to schedule as scan with each policy defined by the user and the built-in policies.
  
  * A tag to schedule a scan with between 1 and 3 policies (user-defined or built-in) on a branch name selected from the list:
    - master
    - main
    - develop
    - production
  
  * A tag to schedule a scan with between 1 and 3 policies (user-defined or built-in) on a branch name selected from the prior list
    and any supported engines.
  
  * A tag to schedule a scan with between 1 and 3 policies (user-defined or built-in) with no branch name (indicating the primary branch)
    and any supported engines.


