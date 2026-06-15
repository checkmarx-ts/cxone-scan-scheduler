
* The `cxone-scan-scheduler` audit feature is not available with a Kubernetes deployment.

* The `cxone-scan-scheduler` helm chart deploys as a Kubernetes `Deployment`.

* The `cxone-scan-scheduler` is not deployed as a Kubernetes `CronJob` given not every user
  will deploy in Kubernetes.
