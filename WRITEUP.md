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

*TODO: Add your answer here*

---

### 3. Two usage sessions from two different apps are reported for the same child at the same time, and together they exceed the remaining balance. Walk through exactly what your system does, entry by entry in the ledger.

*TODO: Add your answer here*

---

### 4. Your undo-approval design: what happens if the balance would go negative? Why is your choice the right one for a parent-child product (not just technically convenient)?

*TODO: Add your answer here*

---

### 5. If you were told this must now handle 100,000 children with usage events streaming in constantly, what is the first thing in your current design that breaks, and how would you fix it?

*TODO: Add your answer here*

---

### 6. What did you deliberately not build, and how would you build it with one more week?

*TODO: Add your answer here*
