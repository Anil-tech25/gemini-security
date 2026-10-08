\# Results



\## Experiment 1: SQL injection code review



\*\*Model:\*\* gemini-3.8-flash



\*\*Prompt:\*\*

```

Review this Python code for security problems and suggest a fix:



import sqlite3

def get\_user(username):

&#x20;   conn = sqlite3.connect("users.db")

&#x20;   query = "SELECT \* FROM users WHERE name = '" + username + "'"

&#x20;   return conn.execute(query).fetchall()

```



\*\*My expectation (before running):\*\* Gemini will find SQL injection and suggest parameterized queries.



\*\*Gemini's response:\*\*



(paste the whole response here, starting at "### Security Issues Identified" and ending at "...manages the lifecycle of the connection.")



\*\*My assessment:\*\*

\- \*\*Right:\*\* Correctly found SQL injection (CWE-89). The payload `' OR '1'='1` is a real attack that would return all users. Parameterized queries (`?`) are the correct fix and match the OWASP guidance.

\- \*\*Right:\*\* Correctly noticed the database connection is never closed.

\- \*\*Wrong:\*\* Gemini said `with sqlite3.connect(...)` makes sure the connection closes. This is false. The Python sqlite3 documentation says the connection's context manager only commits or rolls back the transaction. It does not close the connection. So Gemini's "fixed" code still has the leak it warned about.

\- \*\*How I checked:\*\* Read the official Python sqlite3 documentation on using the connection as a context manager.

\- \*\*Correct fix:\*\* use `contextlib.closing()` or call `conn.close()`.



## prompt2.txt (2026-10-05 17:02)
**Model:** gemini-3.8-flash

**Prompt:** What does Windows Event ID 4625 mean, and when should a SOC analyst worry about it?

**Response:**

### What is Windows Event ID 4625?

**Event ID 4625** documents a **failed logon attempt** on a Windows system. It is generated on the computer where the logon attempt occurred (e.g., on a Domain Controller for domain accounts, or locally on an endpoint for local accounts).

While this is one of the most common events in any Windows environment, it is also a fundamental telemetry source for detecting unauthorized access attempts.

---

### Critical Fields to Look at in Event 4625

To understand *why* and *how* the failure happened, an analyst must look at three specific fields:

1. **Sub Status Code (The "Why"):**
   * `0xC000006A`: Correct username, **wrong password**.
   * `0xC0000064`: The **username does not exist**.
   * `0xC0000072`: The account is currently **disabled**.
   * `0xC0000234`: The account is **locked out** (often the result of a brute-force attack).
   * `0xC000006F`: Logon attempt outside of authorized hours.

2. **Logon Type (The "How"):**
   * **Type 2 (Interactive):** Someone is physically at the keyboard (or using a VM console).
   * **Type 3 (Network):** Connection via network (SMB/file share, IIS, etc.).
   * **Type 10 (RemoteInteractive):** Remote Desktop (RDP). Very common vector for attackers.

3. **Network Information (The "Where"):**
   * **Workstation Name** and **Source Network Address (IP):** Identifies where the attempt originated.

---

### When Should a SOC Analyst Worry?

Because benign users mistype passwords daily, individual 4625 events are almost always noise. A SOC analyst should escalate or investigate when they see the following patterns:

#### 1. High-Velocity Failures Against a Single Account (Brute Force)
* **The Scenario:** Hundreds or thousands of 4625s for one username in a short timeframe.
* **Threat:** An attacker is attempting a dictionary or brute-force attack to guess a specific user's password.

#### 2. Low-and-Slow Failures Across Many Accounts (Password Spraying)
* **The Scenario:** One or two failed logons across dozens or hundreds of *different* usernames coming from the same source IP over a prolonged period (e.g., trying `Spring2024!` on every user).
* **Threat:** Attackers deliberately avoid triggering account lockout thresholds by spraying one common password across the entire organization.

#### 3. High Volume of `0xC0000064` (User Does Not Exist)
* **The Scenario:** Repeated failures where the username is not in Active Directory, especially default names like `admin`, `root`, `test`, `guest`, or `sqlservice`.
* **Threat:** **Username enumeration** or automated external scanners targeting your network.

#### 4. The "Golden Rule": Failures Followed by a Success (4625 $\rightarrow$ 4624)
* **The Scenario:** Multiple 4625 events for an account, followed immediately by an **Event ID 4624 (Successful Logon)** from the same source IP.
* **Threat:** **A successful breach.** The attacker’s brute-force attempt worked, and they now have valid credentials. *This is an immediate, high-priority incident.*

#### 5. Privileged or Sensitive Account Targets
* **The Scenario:** Failures targeting Domain Admins, Enterprise Admins, VIPs, or Break-Glass accounts.
* **Threat:** Targeted attack aimed at gaining full administrative control.

#### 6. Anomalous Source Locations
* **External/Public IPs:** 4625s originating from external, unmanaged IPs directly hitting internal servers or edge systems (like exposed RDP or Citrix).
* **East-West Anomalies:** A standard workstation suddenly attempting network logons (Logon Type 3) to 50 other internal workstations within minutes (lateral movement/reconnaissance).

---

### When is it usually a False Positive (Benign)?

Before sounding the alarm, analysts should rule out common operational issues:
* **Expired Credentials / Cached Credentials:** A user changed their Active Directory password, but their mobile device, mapped network drive, or saved browser credentials keep trying the old password.
* **Misconfigured Service Accounts:** An IT admin changed a service account password, but forgot to update a scheduled task or a Windows Service running on a specific host (often causes a flood of 4625s).
* **Single typos:** 1 to 3 failed logons followed by a successful logon during normal business hours is almost always a human mistyping their password.
