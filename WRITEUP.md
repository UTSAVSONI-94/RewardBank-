# WRITEUP.md — System Design & Engineering Writeup

### 1. What assumptions did you make, and why?

*I made the following assumptions:
1. Ledger entries are structly append only, already existing entries never modified, deleted on any circumstances. Reason:  If a parent reverse an approval , issuing a new compensation transaction would insure transparency and allow balance to be rederived and verified from scratch any time .
2. When offline device reconnects and reports session use from the past , server evaluates coverage against current balance at exact time request arrives,rather than replaying past balances . Reason : Processing against the current balance keeps accounting , predicatable and simple .
3. Idempotency Handling (Any ussage session with identical app id , child id, start time ,end time)  is a duplicate of recent event. Reason: Generating a hash of these 4 parameters guarantess duplicate session submission return cached original data without double debiting minutes.
4. When a parent undoes a task approval after the child has already spent the reward minutes,the child's balance is allowed to drop below zero     into a negative state. Reason : A negative balance is the honest representation it automatically blocks further app usage until the child     completes new tasks to pay off the deficit.
   
5. Multi-Parent Family (Parents can manage any child within their family, while children can only view and manage their own account) 
 Reason : Real households often have multiple parents/guardians and multiple children. Role-Based Access Control enforces strict family boundary isolation and security.
---

### 2. A parent double-clicks the "Approve" button and your API receives the approval request twice, 200ms apart. What does your system do? Prove it with a test.

*When a parent double-clicks the approve button the server gets the first request and sees the task is marked as done. It updates tasks status to approved and add reward balance to in the ledger. But when 200ms later the second request hits ,system looks up the task again and see approved not (done) . Since our app only allows if is in done state , the second request fail validation. Server rejects with it with 400 bad request with message already approved task.                                           
How we prove it : I wrote a unit test called test_parent_double_click_approve_idempotent in tests/test_tasks.py that mimics double tap behaviour:
1. It creates a task worth 30 minutes and marks it as done.
2. It sends the first PATCH /tasks/{id}/approve request and asserts it succeeds with HTTP 200 OK.
3. It immediately sends a second PATCH /tasks/{id}/approve request for the same task ID and asserts it gets rejected with HTTP 400 Bad Request.
4. Finally, it checks the child's balance and ledger to confirm the balance is exactly 30 minutes (not 60) and there is only 1 transaction line in   the ledger.
*

---

### 3. Two usage sessions from two different apps are reported for the same child at the same time, and together they exceed the remaining balance. Walk through exactly what your system does, entry by entry in the ledger.

*Let's take a scenario where 2 tasks arrived at same time for ex youtube for 20 min and spotify for 15 min , our database handle requests one by one
to avoid conflicts and as of now we have balance = 25 min and if db process youtube first (balance > duration) , child will be allowed to complete youtube session and now updated balance(debit = 20) is 5 min so now request for spotify session is 15 min but our system calculates allowed time = min(duration,balance) which is 5 min here . So Child will be allowed to use 5 min and after 5 mins balance will updated to zero and both session completed this is here partial completion occurs due to low reward balance . *

---

### 4. Your undo-approval design: what happens if the balance would go negative? Why is your choice the right one for a parent-child product (not just technically convenient)?

*TODO: Add your answer here*

---

### 5. If you were told this must now handle 100,000 children with usage events streaming in constantly, what is the first thing in your current design that breaks, and how would you fix it?

*TODO: Add your answer here*

---

### 6. What did you deliberately not build, and how would you build it with one more week?

*TODO: Add your answer here*
