
# General Issues

This reference contains guidelines about when to warn the user of potential issues
with their configuration options.

## Proxy

If a proxy is configured, the user should be asked if they'd also like to deploy a custom CA (certificate authority) certificate.

## Short Scan Timings

If a crontab string defines any interval of less than 6 hours, the user should be warned that:

* The concurrent number of scans may hit the licensed maximum causing non-scheduled scans to wait
  for an available scan execution slot.

* If the number of concurrent scans meets or exceeds the licensed maximum number of scans for a long time period,
  the number of scans queued may lead to overall longer scan times.

* The maximum number of queued scans is 2000.  After the scan queue exceeds this count, scan submissions will be
  rejected in error.

## Short Schedule Update Timings

If a user configures the number of seconds between schedule updates as less than 8 hours, the user
should be warned that:

* The API I/O for updating the schedule is intensive and best kept to a minimum amount by keeping the
  interval at 8 hours or greater.

* The time it takes to compile the schedule increases as the number of projects increase.

## Secret Content

The user should be warned that the contents of the secret files should be only the secret values with no line
endings (CR/LF).  If error messages are emitted indicating login failures, view the hex dump of the secret
file to ensure the editor used to write the secret file is not silently appending a line terminator.
