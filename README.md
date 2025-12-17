# Network Automation – Set Cisco IOS Interface Descriptions from CSV

This repository contains a Python automation script that connects to multiple Cisco IOS switches in parallel and sets or removes interface descriptions based on a CSV file.

## Key Properties

- No credentials hardcoded (loaded from `.env`)
- Concurrent execution across switches (faster bulk changes)
- Per-switch grouped output (no interleaved thread prints)
- Post-change verification using `show interface <iface> description`
- Supports removing descriptions using a CSV sentinel value: `blank`

---

## What the Script Does

For each device listed in the CSV, the script:

1. Reads rows in the form: `host,interface,description`
2. Groups interface updates per host
3. Connects via SSH using Netmiko
4. Applies all interface description changes in one configuration batch
5. Saves the configuration (`write memory`)
6. Verifies results per interface and prints a per-host verification block
7. Prints a success/failure summary at the end

---

## Requirements

- Python **3.9+** recommended
- Network reachability to the switches (SSH)
- Cisco IOS devices supported by Netmiko (`cisco_ios`)

### Python Packages

- `netmiko`
- `python-dotenv`

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Project Files

- `set_port_descriptions_from_csv.py`
- `set_port_descriptions_from_csv.example.csv`
- `.env.example`
- `.gitignore`
- `requirements.txt`

---

## CSV Format

The CSV file **must** contain the following headers:

```csv
host,interface,description
```

Example:
```csv
10.0.0.1,Gi1/0/1,PC-01
10.0.0.1,Gi1/0/2,Printer-02
10.0.0.2,Gi1/0/3,Phone-03
```

> The CSV included in this repository contains **example data only**.

### Removing an Interface Description

To remove an existing interface description, set the `description` field to:

```csv
10.0.0.1,Gi1/0/10,blank
```

- `blank` is **case-insensitive** (`blank`, `BLANK`, `Blank`)
- This results in the command:
  ```
  no description
  ```

> Empty description fields are ignored by design.

---

## Environment Variables

Create a local `.env` file with the following values:

```env
NET_USER=your_username
NET_PASS=your_password
NET_SECRET=your_enable_secret   # optional
```

A template is provided as `.env.example`.

### `.env` Lookup Order

The script searches for `.env` in:
1. The same directory as the script
2. The parent directory (useful for shared multi-script setups)

---

## How to Run

1. Populate `set_port_descriptions_from_csv.csv` with your targets
2. Create a `.env` file with credentials
3. Run the script:

```bash
python set_port_descriptions_from_csv.py
```

---

## Output / Verification

For each switch, the script prints a verification block similar to:

```text
>>> Verifying interface descriptions on <host>:
Gi1/0/1  up  up  PC-01
Gi1/0/2  up  up  Printer-02
```

Then, for successful hosts:

```text
>>> SUCCESS: <host>
```

Finally, a summary is printed:

- Total switches processed
- Successful count
- Failed count
- Failed host list (if any)

---

## Notes

- Test on a small number of devices before large deployments
- Interface names must match the device OS format
- Verification relies on `show interface <iface> description`
