# REL-10245 — Payment release

Summary: Payment validation release for the production lane.

Environment: Prod
Approved build: PAY-8427
Artifact: pay-validation-8427.ear

Deployment Order:
DML PAY-DB-8427 first -> wait 10 minutes -> deploy EAR -> JVM restart -> validate.

Job Template: payment-prod-standard

Notes:
The change request says 1.19. A preparation note references 1.18. The release owner confirmed that 1.19 is the intended approved artifact, but the ticket was not updated when the earlier build was mentioned.

Current status: Deployment job reported success.

# REL-10246 — Customer profile release

Summary: CustomerProfile changes for SIT validation.

Environment: SIT
Approved build: CP-3108
Artifact: customer-profile-3108.ear

Deployment Order: deploy EAR -> validate.
Job Template: customer-profile-sit

Notes:
A linked task mentions UAT while this release record says SIT. The release coordinator asked for confirmation before using the UAT value from the task.

# REL-10247 — Payments release

Summary: Payments functional validation.

Environment: UAT
Artifact: payments-5512.ear

Deployment Order:
DML PAY-DB-5512 -> wait 10 minutes -> EAR -> validation.

Job Template: payments-uat-standard

Notes:
The approved build field is blank in this ticket even though the artifact field is populated. QA notes say the build was validated in SIT before the UAT window.

# REL-10248 — Cards release

Summary: Cards release with configuration-sensitive changes.

Environment: Prod
Approved build: CARD-7704
Artifact: cards-7704.ear

Deployment Order:
DML CARD-DB-7704 -> wait 10 minutes -> EAR -> restart if required -> validation.

Job Template: cards-prod-standard

Notes:
One copied ticket comment says QA. The release request and current validation note both refer to Prod. Secret reference must be checked against the Prod baseline.

# REL-10249 — Search release

Summary: Search integration changes.

Environment: Prod
Approved build: SRCH-1198
Artifact: search-1198.ear

Deployment Order: validate Solr connectivity -> EAR -> health validation.
Job Template: search-prod-standard

Notes:
The linked test note references UAT. The main request says Prod. Solr credentials were rotated recently.

# REL-10250 — Notifications release

Summary: Kafka consumer update.

Environment: QA
Approved build: NOTIF-4481
Artifact: notifications-4481.ear

Deployment Order: validate Kafka account/ACL -> EAR -> consumer validation.
Job Template: notifications-qa

Notes:
The ticket has no explicit topic name. A comment says the service account was created last week. Another comment says the ACL may not have been applied.

# REL-10251 — Fraud release

Summary: Fraud rules deployment.

Environment: Prod
Artifact: fraud-2288.ear

Deployment Order: DML FRAUD-DB-2288 -> wait 10 minutes -> EAR -> validation.
Job Template: fraud-prod-standard

Notes:
Approved build field is missing. The artifact name contains 2288. A release note refers to build 2287 as the previous candidate.

# REL-10252 — Accounts certificate update

Summary: Accounts service certificate rotation.

Environment: Prod
Approved build: ACCT-1450
Artifact: accounts-1450.ear

Deployment Order: validate new certificate -> EAR -> verify dependency calls.
Job Template: accounts-prod-standard

Notes:
A copied configuration note still references the previous secret name. The new certificate was issued this morning.

# REL-10253 — Offers release

Summary: Offer rule update.

Environment: Prod
Approved build: OFF-901
Artifact: offers-901.ear

Deployment Order: EAR -> cache validation -> functional validation.
Job Template: offers-prod-standard

Notes:
Direct API validation shows the new rule. Customer-facing validation still returns a previous value. The ticket does not say whether the distributed cache was invalidated.

# REL-10254 — Billing release

Summary: Billing deployment after maintenance.

Environment: Prod
Approved build: BILL-6201
Artifact: billing-6201.ear

Deployment Order: pre-deployment validation -> EAR -> validation.
Job Template: billing-prod-standard

Notes:
The deployment server was unavailable during a patch window. The execution plan field still contains the original morning window.

# REL-10255 — CustomerProfile JVM issue

Summary: CustomerProfile runtime compatibility check.

Environment: QA
Approved build: CP-3112
Artifact: customer-profile-3112.ear

Deployment Order: EAR -> restart if runtime change included -> validation.
Job Template: customer-profile-qa

Notes:
The server has both Java 17 and Java 11. A routing note says the application should use Java 17, but one older host entry still points to Java 11.

# REL-10256 — Data change ordering test

Summary: Payment database and application release.

Environment: SIT
Approved build: PAY-8440
Artifact: payment-8440.ear

Deployment Order: EAR -> DML -> immediate validation.
Job Template: payment-sit-standard

Notes:
The runbook used for other Payment releases normally performs DML first with a wait interval. This ticket may contain an incorrect order and has not been corrected yet.

# REL-10257 — Artifact mismatch investigation

Summary: Customer profile artifact verification.

Environment: SIT
Approved build: CP-3115
Artifact: customer-profile-3114.ear

Deployment Order: validate artifact -> EAR -> health validation.
Job Template: customer-profile-sit

Notes:
The build and artifact values do not match. The release requester says the intended build is 3115, but the attachment filename still contains 3114.

# REL-10258 — Kafka version migration research

Summary: Notifications library upgrade.

Environment: QA
Approved build: NOTIF-4500
Artifact: notifications-4500.ear

Deployment Order: validate compatibility assumptions -> EAR -> consumer validation.
Job Template: notifications-qa

Notes:
A dependency upgrade was included in the change. The team wants to understand whether the new Kafka client version changed authentication behaviour.

# REL-10259 — Search dependency change

Summary: Search dependency library update.

Environment: UAT
Approved build: SRCH-1210
Artifact: search-1210.ear

Deployment Order: validate dependency documentation -> EAR -> health validation.
Job Template: search-uat-standard

Notes:
The ticket asks for current vendor documentation because the dependency version changed from the version used in the last release.

# Artifact naming convention (reference)

Every application build is packaged once per target environment under the convention
`<app>-<version>-<env>.ear`, where `<env>` is one of `sit`, `pt`, or `prod` — for example
`billing-3.05-sit.ear`, `billing-3.05-pt.ear`, `billing-3.05-prod.ear` are three separate
packaged artifacts built from the same underlying `3.05` change, one per environment. A
`-prod` suffixed artifact must never be deployed to a lower environment, and a lower-environment
artifact must never be deployed to Prod, even when the version number matches — they are
different packages with different embedded configuration, and mixing them up is a recurring
human-error pattern across releases (see REL-12020 and REL-12030 below).

The same release ticket ID is reused as a build progresses from SIT through PT to Prod; the
ticket's environment field and artifact field are updated at each stage rather than opening a
new ticket per environment, so a ticket's full history shows every environment it has actually
been deployed to.

# REL-12001 — Payment SIT-only validation

Summary: Payment discount-rule change, SIT validation only, no further promotion planned this cycle.

Environment: SIT
Approved build: PAY-2141
Artifact: payment-2.14-sit.ear

Deployment Order: EAR -> validate.
Job Template: payment-sit-standard

Notes:
This ticket is scoped to SIT only. QA needs the change available for exploratory testing but it
is not on the current Prod release train. Do not promote this artifact to PT or Prod under this
ticket - a separate ticket will be opened if/when this change is approved for further promotion.

Current status: Deployed to SIT, closed at SIT stage.

# REL-12010 — Billing environment progression (clean)

Summary: Billing reconciliation fix, progressing through the full environment chain this cycle.

Environment history:
- SIT: Approved build BILL-3050, artifact billing-3.05-sit.ear. Deployed and validated.
- PT: Approved build BILL-3050, artifact billing-3.05-pt.ear. Deployed and validated.
- Prod: Approved build BILL-3050, artifact billing-3.05-prod.ear. Deployment pending, scheduled
  for the next monthly Prod window.

Deployment Order (each environment): DML BILL-DB-3050 -> wait 10 minutes -> EAR -> validation.
Job Template: billing-{env}-standard (environment-specific template, same pattern per stage).

Notes:
Each stage used its own correctly-suffixed artifact per the naming convention above. This ticket
is the reference example of a clean same-ticket, multi-environment progression - no artifact
mismatch at any stage.

# REL-12020 — CustomerService environment progression (artifact swap incident)

Summary: CustomerService balance-calculation fix, progressing from SIT to Prod.

Environment history:
- SIT: Approved build CS-1110, artifact customerservice-1.11-sit.ear. Deployed and validated.
- Prod: Approved build CS-1110, artifact customerservice-1.11-prod.ear approved for deployment.

Deployment Order: EAR -> validation.
Job Template: customerservice-prod-standard

Notes:
During the Prod deployment window, the deployment operator selected customerservice-1.11-sit.ear
from the artifact repository instead of the approved customerservice-1.11-prod.ear - both were
visible in the same folder with only the environment suffix differing. The SIT-suffixed artifact
carries SIT-only configuration (a lower-lane database endpoint and relaxed feature flags) and is
not safe to run in Prod. The deployment job itself reported success, since the artifact deployed
without error - the mismatch was only caught when the served-version checksum was compared
against the ticket's approved artifact hash and did not match. Corrected by redeploying the
proper customerservice-1.11-prod.ear artifact and re-validating.

Current status: Corrected and closed. Root cause: human error selecting the wrong
environment-suffixed artifact from a shared repository folder; both files were present at the
same time with visually similar names.

# REL-12030 — OrderService environment progression (premature prod artifact in SIT)

Summary: OrderService fulfillment-flow change, SIT validation ahead of a later Prod date.

Environment history:
- SIT: Approved build ORD-1020, artifact orderservice-1.02-sit.ear expected.
- Prod: Approved build ORD-1020, artifact orderservice-1.02-prod.ear, NOT yet approved for
  deployment - Prod date is a future release train, not this cycle.

Deployment Order: EAR -> validate.
Job Template: orderservice-sit-standard

Notes:
The operator deployed orderservice-1.02-prod.ear to SIT by mistake, instead of the intended
orderservice-1.02-sit.ear - the reverse direction of the REL-12020 incident. The prod-suffixed
artifact has Prod-only feature flags compiled in, so SIT testers briefly saw functionality that
was not supposed to be visible in SIT this cycle, and QA flagged unexpected behavior before the
cause was identified. Corrected by redeploying the correct orderservice-1.02-sit.ear artifact.
The Prod-suffixed artifact remains held for its actual, later approved Prod deployment date -
this incident did not consume or invalidate that approval.

Current status: Corrected in SIT. Prod deployment for this ticket remains scheduled separately
and was not affected.

# REL-12040 — Offers SIT-only, explicitly not promoting this cycle

Summary: Offers experimental discount-stacking logic, SIT exploratory testing only.

Environment: SIT
Approved build: OFF-902
Artifact: offers-4.10-sit.ear

Deployment Order: EAR -> cache validation -> functional validation.
Job Template: offers-sit-standard

Notes:
Marked explicitly as SIT-only in the release request; product has not signed off on this logic
for PT or Prod yet. Included here as a contrast case to REL-12010/REL-12020/REL-12030 - not every
ticket progresses through the full environment chain, and a ticket with no Prod artifact recorded
is not itself an error.

Current status: Deployed to SIT, closed at SIT stage, no further environment planned.
