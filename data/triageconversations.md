Monday, 3 Feb, 1:58 PM

Krithika Menon:
SIT deployment window opens in two minutes. Coordinators, confirm your app is ready to go when I open the floor.

Pema Sherpa:
Payment is ready. Ticket REL-11020, artifact payment-2.14-sit.ear.

Divya Prakash:
Billing is ready. REL-11021, billing-3.02-sit.ear.

Ayesha Khan:
CustomerService is ready. REL-11022, customerservice-1.09-sit.ear.

Krithika Menon:
2:00 PM. Window is open. Go ahead in the order posted.

Karthick Raja:
Starting Payment deployment to SIT now.

Karthick Raja:
Deployment job reported success. Health check green.

Pema Sherpa:
Business tester says the new discount validation rule isn't showing up though. Karthick, can you check?

Karthick Raja:
Checking. Health page green, job green, but let me check the actual served version first instead of assuming.

Karthick Raja:
Served version is 2.13, not 2.14. Something's off.

Pema Sherpa:
What does the ticket say the target environment was?

Karthick Raja:
REL-11020 just says "SIT" with no host group or pool specified. I deployed to the usual SIT pool for Payment, the one we always use.

Pema Sherpa:
There are two SIT pools for Payment right now because of the pool migration last month. The ticket should have named the specific one.

Karthick Raja:
That would explain it. I deployed to the old pool by habit.

Krithika Menon:
Update the ticket with the specific pool name going forward, not just "SIT". Karthick, redeploy to the correct pool now that we know which one.

Karthick Raja:
Redeployed to sit-pool-2. Served version now shows 2.14. Discount rule is visible.

Pema Sherpa:
Confirmed on our side too. Payment SIT deployment closed out.

Farah Sheikh:
Heads up on Billing - XLR shows the release train isn't configured yet for billing-3.02 in SIT. This is a newer app onboarding, so the train setup request is still pending with platform team.

Divya Prakash:
That's going to block us for today's window. Krithika, can we get an exception?

Krithika Menon:
For SIT specifically, since this is a same-day blocker and Ansible is available, use Ansible for this one deployment instead of waiting on the XLR train. Don't make this the standing process though - the train still needs to get configured properly.

Farah Sheikh:
Understood. Deploying billing-3.02-sit.ear via Ansible now.

Farah Sheikh:
Done. Health check green, served version confirmed 3.02.

Divya Prakash:
Billing SIT closed.

Ayesha Khan:
CustomerService still pending, we're next in the queue.

Ayesha Khan:
Deployment complete. Health check is failing though - repeated timeout errors in the logs trying to reach the database layer.

Suresh Iyer:
Looking at the logs now.

Suresh Iyer:
It's Cassandra. SSLHandshakeException, PKIX path building failed, unable to find valid certification path.

Suresh Iyer:
This release also bumped the Cassandra driver from 4.15 to 4.17. I haven't checked whether the truststore got updated as part of the same release.

Krithika Menon:
Don't redeploy yet - get the NoSQL team engaged on the connectivity issue directly instead of guessing at the driver angle.

Ayesha Khan:
Paged the NoSQL on-call.

Ayesha Khan:
NoSQL team confirmed the truststore on this SIT node was never rotated to include the new CA the 4.17 driver expects. They're pushing the updated truststore now.

Suresh Iyer:
Confirmed - health check passes once the truststore push completed. No redeploy needed, connectivity issue only.

Ayesha Khan:
CustomerService SIT closed. That's everyone for today's window.

Krithika Menon:
Good work all. Window closed 2:41 PM. See everyone at PT window Thursday.

---

Thursday, 6 Feb, 3:58 PM

Krithika Menon:
PT window opens in two minutes. Same three apps today. Confirm readiness.

Pema Sherpa:
Payment ready.

Divya Prakash:
Billing ready.

Ayesha Khan:
CustomerService ready.

Krithika Menon:
4:00 PM, window open.

Pema Sherpa:
Payment deployment to PT complete, health check green.

Karthick Raja:
Business tester flagged the same discount rule isn't visible in PT now either.

Karthick Raja:
Checked served version first this time - it's correct, 2.14 as expected. So it's not a version mismatch like SIT was.

Pema Sherpa:
Ticket says restart required?

Karthick Raja:
No restart step listed on REL-11023 at all. Let me check the runbook.

Karthick Raja:
Runbook says this application requires a JVM restart for validation-rule changes specifically, it doesn't take effect on hot deploy alone. That step was missing from the ticket.

Krithika Menon:
Add the JVM restart step to the release ticket template for Payment permanently, not just this one ticket. Karthick, go ahead and restart now to unblock today.

Karthick Raja:
Restarted. Discount rule now visible. Payment PT closed.

Farah Sheikh:
Billing deployment to PT is stuck. Job accepted but hasn't moved in over ten minutes, no error in the log.

Wei Zhang:
Same here from the network side, nothing unusual, LB isn't seeing any new connection attempts from the deploy agent at all.

Farah Sheikh:
CD tool dashboard is showing errors across the board, not just our job. Every team's queue looks frozen.

Krithika Menon:
Sounds like a platform outage rather than anything specific to Billing. Farah, can you confirm with the platform team directly?

Farah Sheikh:
Confirmed, platform status page just posted an outage notice for the CD tool. ETA 30 minutes.

Krithika Menon:
We wait. No point debugging Billing specifically while the whole platform is down. Divya, hold the ticket status as pending-platform, not failed.

Farah Sheikh:
Platform back up. Resuming the Billing job now.

Farah Sheikh:
Completed. Health green, served version confirmed.

Divya Prakash:
Billing PT closed, 45 minutes later than planned but no application-side issue.

Ayesha Khan:
CustomerService deployment to PT reports success but health check is failing again, different error this time - connection refused to the search dependency.

Suresh Iyer:
That's Solr, not Cassandra this time.

Suresh Iyer:
Confirmed, Solr connection is refused outright, not a cert issue.

Ayesha Khan:
Engaging the search/app experts team.

Ayesha Khan:
They found the Solr node group for PT was mid-restart from an earlier unrelated maintenance and just hadn't come back healthy yet. It's up now.

Suresh Iyer:
Health check passes now. No application code involved either time today - two different downstream dependencies, same underlying pattern of "check what's actually unreachable before assuming the deploy is bad."

Krithika Menon:
Good instinct. CustomerService PT closed. Window closed 5:12 PM.

---

Saturday, 8 Feb, 11:58 PM — Monthly Prod release

Krithika Menon:
Prod release window opening. This is the big one, please stay heads-down tonight. Coordinators confirm snapshot sign-off before anyone deploys anything.

Pema Sherpa:
Payment snapshot confirmed by release leads - REL-11020, artifact payment-2.14-prod.ear, approved build PAY-2140.

Divya Prakash:
Billing snapshot confirmed - REL-11021, artifact billing-3.02-prod.ear, approved build BILL-3020.

Ayesha Khan:
CustomerService snapshot confirmed - REL-11022, artifact customerservice-1.09-prod.ear, approved build CS-1090.

Krithika Menon:
Midnight. Go in posted order. DML apps first per the deployment order rule, then EAR, ten minute gap for gossip to complete before anyone deploys EAR on top.

Karthick Raja:
Payment has no DML this cycle, straight to EAR. Deploying now.

Karthick Raja:
Deployed. Health green. Served version 2.14 confirmed directly, not just health page. Discount rule visible. Payment Prod closed, 12:14 AM.

Naveen Reddy:
Billing has DML this cycle. Running DML now.

Naveen Reddy:
DML complete. Starting the ten minute gossip wait before EAR.

Naveen Reddy:
Ten minutes up. Deploying billing-3.02-prod.ear now.

Naveen Reddy:
Health green, served version 3.02 confirmed. Billing Prod closed, 12:41 AM.

Ayesha Khan:
CustomerService, no DML, deploying EAR now.

Ayesha Khan:
Deployment reports success but the business validation is showing the pre-release balance calculation still, not the corrected one.

Suresh Iyer:
Served version check first - it's 1.09, correct, matches the ticket. So the artifact is right this time.

Suresh Iyer:
Direct API call shows the corrected calculation. It's the customer-facing path specifically that's stale, not the backend.

Krithika Menon:
Sounds like a cache issue, not a deployment issue. Don't touch the deployment again.

Suresh Iyer:
Confirmed - distributed cache for that calculation wasn't invalidated by this release. Invalidating manually now.

Suresh Iyer:
Customer-facing path now shows the corrected value. CustomerService Prod closed, 1:20 AM.

Krithika Menon:
All three closed. Nothing further tonight. Good release, thank you all for staying on it this late.

---

Monday, 3 Mar, 1:59 PM

Krithika Menon:
SIT window open in a minute. Two new apps joining the channel this cycle - Tarun for OrderService, Ola for Offers.

Tarun Malhotra:
OrderService ready, REL-11540, orderservice-1.02-sit.ear.

Ola Ibrahim:
Offers ready, REL-11541, offers-4.10-sit.ear.

Krithika Menon:
2:00 PM, window open.

Tarun Malhotra:
OrderService deployment to SIT is stuck in XLR, accepted but not progressing, no error.

Farah Sheikh:
Checking XLR - OrderService doesn't have a release train configured for SIT yet. This is a first deployment for this app through our pipeline.

Priya Das:
That's going to block the whole window if we wait on train setup.

Krithika Menon:
Same call as Billing last month - for the environment that's time-sensitive, use Ansible as a one-off. Which environment is time sensitive today?

Priya Das:
Today it's SIT, we have QA blocked on it.

Farah Sheikh:
Deploying via Ansible for SIT only. Train setup request filed for OrderService, all non-urgent environments will wait for the proper train.

Farah Sheikh:
Complete. Health green. OrderService SIT closed via Ansible workaround.

Ola Ibrahim:
Offers SIT deployment also stuck, same symptom - no release train for this app in SIT either.

Priya Das:
Offers isn't time sensitive today, PT isn't scheduled until Thursday and nothing's blocked waiting on Offers SIT specifically.

Krithika Menon:
Then let's not repeat the Ansible workaround here - wait for the release train to be set up properly and deploy Offers once it exists, for all non-PT environments.

Priya Das:
Understood, holding Offers SIT until the train is ready. Will update once platform confirms.

Priya Das:
Platform confirmed the release train is live for Offers as of an hour ago.

Ola Ibrahim:
Deploying Offers to SIT through XLR normally now.

Ola Ibrahim:
Complete. Health green, served version confirmed. Offers SIT closed.

Krithika Menon:
Window closed 2:52 PM.

---

Thursday, 6 Mar, 3:59 PM

Krithika Menon:
PT window open in a minute.

Tarun Malhotra:
OrderService deployment jobs have failed three times in a row now, all retries, same target group.

Naveen Reddy:
Checking the CD tool inventory for that target group.

Naveen Reddy:
Found it - there's a decommissioned server still tagged as part of the active target group. Every attempt is trying to reach a host that doesn't exist anymore.

Krithika Menon:
Get the inventory corrected before retrying again, don't just keep retrying the same broken target list.

Naveen Reddy:
Inventory updated, decommissioned host removed from the target group.

Tarun Malhotra:
Redeployed. Success, health green. OrderService PT closed.

Ola Ibrahim:
Offers deployment to PT is behaving strangely - the application looks like it's pointed at the wrong environment's downstream dependencies.

Wei Zhang:
What symptoms specifically?

Ola Ibrahim:
It's trying to reach a database endpoint that looks like a lower-lane hostname, not the PT one we expect.

Wei Zhang:
Checking config for this deployment.

Wei Zhang:
Found it. Production and lower-lane configuration values got interchanged somewhere in this release's config bundle - PT is holding a lower-lane database endpoint and vice versa on another setting.

Krithika Menon:
Get the correct environment-specific config restored properly, through the approved config process, don't hand-edit it live.

Wei Zhang:
Config corrected and redeployed through the normal process. Offers PT closed, endpoints verified correct for this environment.

Karthick Raja:
Payment PT deployment failed at the DML step specifically, application step never even started.

Karthick Raja:
Looking at the DML failure now.

Karthick Raja:
The lower-lane DML script had a production-specific entry hardcoded in it - a value that doesn't exist in this environment at all.

Krithika Menon:
That needs a code fix, not a config fix - the DML itself is wrong for this environment.

Karthick Raja:
Code fix prepared for the DML values, redeploying.

Karthick Raja:
DML succeeded this time, EAR deployed after the gap. Payment PT closed.

Ayesha Khan:
CustomerService is showing something odd - some requests behave like they're hitting the old version, others are fine, even though every JVM reports the new build deployed.

Wei Zhang:
That's inconsistent enough to smell like routing, not a bad deploy. Checking traffic routing config now.

Wei Zhang:
Confirmed - traffic routing was sending a portion of requests to a JVM outside the intended target set for this release. Not every request, which is why it looked intermittent.

Krithika Menon:
Don't redeploy, all JVMs already report the correct version - fix the routing itself.

Wei Zhang:
Routing corrected, all traffic now reaching the intended JVMs. CustomerService PT closed, verified consistent behavior across repeated checks.

Krithika Menon:
Window closed 5:38 PM, later than usual today, thank you all.

---

Saturday, 8 Mar, 11:59 PM — Monthly Prod release

Krithika Menon:
Prod window opening. Snapshot confirmations please.

Pema Sherpa:
Payment confirmed, REL-11550, artifact payment-2.15-prod.ear.

Divya Prakash:
Billing confirmed, REL-11551, artifact billing-3.03-prod.ear.

Priya Das:
Offers confirmed, REL-11552, artifact offers-4.11-prod.ear.

Krithika Menon:
Midnight, go ahead.

Karthick Raja:
Payment deployed. Health green, served version confirmed. Payment Prod closed.

Divya Prakash:
Billing deployment jobs are retrying repeatedly, stuck on the same step every time.

Naveen Reddy:
Checking - there's an earlier temp-file cleanup step in this job that never completed successfully. Every retry is failing its precondition check because of that leftover state.

Krithika Menon:
Get that resolved directly rather than letting it keep retrying blind.

Naveen Reddy:
Engaged the platform team on the cleanup step directly.

Naveen Reddy:
Resolved, cleanup completed manually. Retried the deployment.

Naveen Reddy:
Success this time. Billing Prod closed.

Ola Ibrahim:
Offers deployment log shows zero net new changes, but there's definitely a real change in this release, I can see it in the diff myself.

Priya Das:
Confirmed the change is genuinely in the approved branch, this isn't a false alarm on our end.

Krithika Menon:
Sounds like the platform's own change-detection is the problem here, not our artifact. Don't keep re-running the same tooling expecting a different result.

Ola Ibrahim:
Deploying manually via Ansible instead of the standard pipeline for this one.

Ola Ibrahim:
Complete, health green, served version confirmed correct. Offers Prod closed. Filed a defect against the change-detection step for follow-up.

Krithika Menon:
All closed, 1:45 AM. Good release.

---

Monday, 7 Apr, 1:58 PM

Krithika Menon:
SIT window in two minutes.

Ayesha Khan:
CustomerService ready.

Divya Prakash:
Billing ready but heads up, our usual validation lead for sign-off is out sick today, may cause a delay later.

Krithika Menon:
Noted, we'll deal with that when we get there. 2:00, window open.

Ayesha Khan:
CustomerService deployment complete, health check failing.

Suresh Iyer:
Server needed a restart after this morning's patching activity, that's all - not related to the deployment itself.

Suresh Iyer:
Start-stop cluster task performed. Health check passes now. CustomerService SIT closed.

Divya Prakash:
Billing deployed fine, health green, but we're stuck on validation sign-off now - our usual approver is unavailable and validation can't be marked complete without them.

Krithika Menon:
Page them directly rather than just waiting, this is time sensitive.

Divya Prakash:
Paged. Waiting for response.

Divya Prakash:
They responded and completed sign-off remotely. Billing SIT closed, about forty minutes later than planned.

Krithika Menon:
Good, that's everyone. Window closed 2:47 PM.

---

Thursday, 10 Apr, 3:58 PM

Krithika Menon:
PT window in two minutes.

Pema Sherpa:
Payment ready.

Tarun Malhotra:
OrderService ready.

Krithika Menon:
4:00, window open.

Karthick Raja:
Payment deployment successful, but functional validation is taking much longer than planned.

Ritika Bose:
We're missing test data for two of the planned scenarios, can't complete full coverage in the window.

Krithika Menon:
Don't claim full coverage if it wasn't actually run. Document exactly which scenarios you could validate and proceed with minimal coverage, flag the gap clearly in the ticket.

Ritika Bose:
Documented. Ran the three scenarios we had data for, all passed. Flagged the two untested scenarios explicitly in REL-11780 rather than marking them passed.

Krithika Menon:
That's the right way to handle it. Payment PT closed with a documented coverage gap.

Tarun Malhotra:
OrderService deployment is waiting - we depend on the Payment order-status API for this release and Payment's deployment for that specific piece isn't done yet on their side.

Pema Sherpa:
That's actually a separate deploy from what Karthick just finished, different component.

Krithika Menon:
Pause OrderService here until the dependency is confirmed complete, don't deploy against an incomplete dependency and redo it later.

Pema Sherpa:
Confirmed the dependent Payment component is now deployed and healthy.

Tarun Malhotra:
Proceeding with OrderService now that the dependency is ready.

Tarun Malhotra:
Complete, health green. OrderService PT closed.

Krithika Menon:
Window closed 5:05 PM.

---

Friday, 11 Apr, 10:20 AM

Ayesha Khan:
Not a deployment window but wanted to flag something for tonight's Prod release - people have been posting status in three different places today, the release channel, email, and direct pings. I've seen two different numbers for the same ticket in the last hour.

Krithika Menon:
Agreed, that's going to cause exactly the kind of confusion we don't want during Prod. Effective immediately - status updates go in this channel only, nowhere else, for the rest of this release cycle.

Krithika Menon:
Posting the current consolidated status now so everyone starts from the same picture: Payment, Billing, CustomerService all confirmed ready for tonight. OrderService and Offers confirmed ready as of this morning.

Divya Prakash:
Understood, will stop the side emails.

---

Saturday, 12 Apr, 11:58 PM — Monthly Prod release

Krithika Menon:
Prod window opening. As discussed, all status in this channel only tonight.

Pema Sherpa:
Payment confirmed, REL-11790, payment-2.16-prod.ear.

Divya Prakash:
Billing confirmed, REL-11791, billing-3.04-prod.ear.

Ayesha Khan:
CustomerService confirmed, REL-11792, customerservice-1.10-prod.ear.

Krithika Menon:
Midnight, go ahead in order.

Karthick Raja:
Payment deployed, health green, served version confirmed. Payment Prod closed.

Naveen Reddy:
Billing DML running now.

Naveen Reddy:
DML complete, starting ten minute gossip wait.

Naveen Reddy:
Deploying EAR now.

Naveen Reddy:
Health green, served version confirmed. Billing Prod closed.

Ayesha Khan:
CustomerService deployment reports success but the wrong release lead handed off to Suresh this shift and the runbook status wasn't updated before the handoff.

Suresh Iyer:
I don't actually know what was already checked and what wasn't from the previous shift's notes, the ticket just says "in progress" with no detail.

Krithika Menon:
Don't guess and don't redo steps blindly - ask the outgoing lead directly what was completed.

Ayesha Khan:
Reached the previous lead, they confirmed served version was already checked and correct, only the functional validation step was still pending.

Suresh Iyer:
Running functional validation now that we know where we actually left off.

Suresh Iyer:
Passed. CustomerService Prod closed.

Krithika Menon:
Updating the runbook requirement - every handoff between release leads must include current status in the runbook itself, not verbally only. That's the second time this cycle we've had to reconstruct status after the fact.

Krithika Menon:
All closed, 1:02 AM. That's the last release of this cycle, thank you everyone for a clean run tonight.
