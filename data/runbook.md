# Release Deployment Runbook

This synthetic runbook is organized as engineering process documentation. It is intentionally free of manually maintained retrieval metadata.

## Scope and release preparation

Confirm the application, target environment, release window, release owner, participating teams, dependencies, deployment ticket, expected artifact and rollback decision points. Resolve ambiguity before execution rather than assuming the environment or artifact from a previous release.

## Deployment ticket and artifact validation

Confirm the release ticket identifies the exact environment, application, release version and approved artifact. Check that the artifact named in the request matches the artifact approved for the release. If the ticket contains contradictory environment or artifact values, stop and clarify the intended values before deployment.

## Deployment plan and job template

The ticket should state the planned deployment order and the approved job template. Where database changes and application artifacts are both required, follow the documented order exactly. A common sequence is DML first, a defined propagation interval, then the application artifact.

## Pre-deployment validation

Confirm required artifacts, credentials, certificates, secrets, access and dependency readiness. Validate server health, network reachability, DNS resolution, load-balancer membership, service dependencies and the baseline application health state before deployment begins.

## Release communication

Post the release commencement, target environment, application, release ticket and expected validation checkpoints in the designated release communication channel. Keep the current status in one place so later participants can distinguish current facts from older updates.

## Application deployment

Deploy the approved artifact using the approved job template for the target environment. Confirm the deployed version or checksum where the release process provides that information. A successful job result is not by itself proof that the expected artifact is serving traffic.

## Database and application deployment order

When both DML and application artifacts are required, execute the DML first when specified by the release. Wait for the documented propagation or gossip interval before deploying the application artifact. Never infer the order from memory when the ticket or runbook contains a different explicit sequence.

## Release train and job-template validation

Before starting a deployment, verify that the job template and expected release train configuration correspond to the target environment and application. An old or mismatched template can point the deployment at the wrong artifact or environment even when the release ticket looks correct.

## Post-deployment version validation

After deployment, compare the application version actually served by the target environment with the version expected by the release ticket. If they differ, investigate artifact selection, deployment target, lower-environment validation and release ordering before attempting another deployment.

## Changes not reflecting after deployment

If the release reports success but the latest change is not visible, check the deployed version first. Then compare the target environment in the release ticket, confirm the lower environment contained the latest approved changes before the cutoff, verify any required JVM restart step, verify deployment order, and check cache or routing behaviour.

## JVM restart requirements

If the release includes a server-level change or another documented condition that requires a restart, perform the approved restart procedure and record the result. If the restart was already completed, do not repeat it solely because a health check remains red; inspect the actual failure evidence.

## Application startup failure

For startup failures, preserve the observed error and compare the current configuration with the target environment baseline. Determine whether the failure relates to configuration, database connectivity, search dependency, messaging, DNS, certificates, routing or application initialization.

## Cassandra and database connectivity

For database connectivity failures, check the endpoint, credentials or secret reference, network path and certificate requirements against the target environment. Do not repeat deployment attempts until the observed connectivity problem has been understood.

## Solr and search dependency failures

For search dependency failures, validate the configured endpoint, authentication material, certificate and network path. Distinguish an unreachable service from an authentication or integration failure.

## Kafka and messaging dependency failures

For Kafka or message-bus problems, check bootstrap endpoint, certificate or secret references, topic availability, ACLs and consumer or producer errors. Record which authentication or authorization condition was observed before changing the deployment path.

## DNS and routing issues

If the application is healthy locally but the expected endpoint returns old or incorrect behaviour, compare DNS resolution, routing and load-balancer membership with the approved target. Correct the underlying target mapping before repeating application deployment.

## Certificate and secret rotation

For TLS or secret failures, verify certificate validity and chain, the target environment secret reference, rotation status and whether the application loaded the new secret. A stale secret reference can cause a release to appear unhealthy even when the application artifact is correct.

## Configuration consistency across environments

Compare environment-specific configuration with the approved baseline for the target environment. A lower-lane value copied into a higher environment can cause the application to start with incorrect endpoints or data settings. Correct the configuration through the approved process and validate the result.

## Partial cluster deployment

If some nodes show the new version and others show the previous version, identify which nodes were part of the target set and which were excluded or unavailable. Verify node health and eligibility before considering another deployment action.

## Cache-related stale behaviour

If a direct API path shows the new behaviour but a customer-facing path shows the old result, investigate cache freshness and invalidation. A correct deployment does not necessarily invalidate a distributed cache.

## Artifact checksum validation

If the release artifact checksum differs from the approved release record, verify which artifact is approved and why the artifact changed. Do not bypass the validation merely because the build is from the same branch.

## Release delay and test-data limitations

If validation is delayed because required test data is unavailable, document the limitation and run only the minimum validation that can be meaningfully completed. Do not claim a test passed when it could not actually be executed.

## Handoff and communication consistency

Keep current release status and important decisions in the central release communication channel. When a handoff omits a required runbook step, use the runbook as the source of truth and update the handoff material after the current issue is understood.

## Rollback decision

Rollback is a human-approved operational decision. Consider it only when the documented rollback condition is met or the forward recovery path cannot safely restore the expected service within the agreed constraints.

## Release closure

After validation passes, return traffic according to the approved process, recheck health, capture final evidence and close the release communication with the release ticket and final validation details.

# LLE Deployment Runbook (via XLR)

This section documents the Lower Life-cycle Environment (LLE — e.g. SIT, UAT, PT) deployment process
specifically, which differs from the Prod process above in two important ways: it is executed through
XLR only after the release leads have explicitly confirmed which code snapshot is approved for that
deployment window, and it runs only during a fixed hour of the day reserved for deployments, to avoid
destabilizing the environment for teams actively testing in it at other times. Each phase's process,
phase number and target environment are inferred automatically during ingestion from the heading and
enclosing section - see `src/rag/ingestion.py` - so this file stays plain, readable prose with no
inline annotations.

## Phase 1 – Planning


Confirm scope, target environment, affected components, the release window, participating stakeholders,
the escalation matrix and the release-in-charge for this window. Create the task ID, assign a task owner,
estimate duration, define milestones and dependencies, and record the rollback decision points before
work begins. Every task in the plan must be validated by its task owner and by the stakeholders
participating in that task — an unvalidated task plan is not ready for XLR. Separately, validate that all
required artifactories, credentials and access are confirmed by their respective stakeholders; a missing
credential discovered mid-deployment is a planning failure, not a deployment failure.

For an LLE deployment specifically, this phase also requires the release leads to confirm the exact code
snapshot that is approved to be deployed in this window. XLR should not be started against an
unconfirmed or assumed snapshot, even if a similar snapshot deployed cleanly in a previous window.

## Phase 2 – Pre-deployment


Broadcast release commencement — target environment, application, release ticket and expected validation
checkpoints — in the designated release communication channel before any deployment action begins. Then
execute pre-deployment steps: stop traffic to the target servers, validate server health, validate network
reachability, and validate load-balancer membership. LLE deployments run only within a specific hour of
the day set aside for deployments in that environment; starting outside that window risks disrupting
active testing by other teams sharing the environment, and should not proceed without explicit release-lead
sign-off to deviate from the window.

## Phase 3 – Deployment


Deploy the confirmed snapshot through XLR using start-stop, either across applications in sequence or in
parallel depending on the release plan. Confirm the deployed version or checksum where XLR provides that
information. A green XLR job status is not by itself proof that the confirmed snapshot is what actually
deployed — cross-check against the release-lead-approved snapshot from Phase 1.

## Phase 4 – Server restart


Bounce the servers affected by this deployment using the approved restart procedure, and record the
result. If a restart was already completed earlier in this same window, do not repeat it solely because a
later health check is red — inspect the actual failure evidence first (see Phase 5).

## Phase 5 – Health validation


Validate the application health check after the restart. A failed health check at this stage most
commonly traces to one of: the server needing an additional restart cycle after patching, an actual code
defect introduced by the deployed snapshot, or a downstream dependency (database, search, messaging)
being unreachable from this environment. Do not proceed to functional validation until health checks pass
or the failure is understood and explicitly accepted by the release lead.

## Phase 6 – Functional validation


Validate the deployed changes with functional testing against the confirmed snapshot's intended scope.
If required test data is unavailable, document the limitation explicitly and run only the minimum
validation that can be meaningfully completed — do not report a scenario as passed when it could not
actually be exercised.

## Phase 7 – Issue resolution / redeployment


If validation identifies issues, fix them and return to the appropriate earlier phase — typically Phase 3
(Deployment) once a corrected snapshot is available and re-confirmed by the release leads, rather than
assuming the original snapshot approval still applies to a changed artifact. Do not loop redeployment
attempts without identifying what changed between attempts.

## Phase 8 – Post-deployment


Once functional validation passes, execute post-deployment steps: return traffic to the deployed servers
and re-confirm health under live traffic.

## Phase 9 – Closure / communication


Post final closure status in the release communication channel: outcome, final validation evidence, the
confirmed snapshot that was deployed, and the release ticket reference. Ensure the handoff to the next
release lead (if the window is followed by another) is written into the runbook itself, not communicated
only verbally — an incomplete handoff is one of the recurring causes of coordination failures in later
releases (see known_issues_catalog.md, "Coordination and communication").
