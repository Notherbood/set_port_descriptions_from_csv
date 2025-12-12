# Network Automation – Interface Descriptions from CSV

This project is a Python network automation script that connects to multiple Cisco IOS switches in parallel and applies interface descriptions based on a CSV input file.

It is designed as a **safe, reusable automation pattern**:
- No credentials are hardcoded
- Secrets are loaded from environment variables
- Device actions are performed concurrently for efficiency
- Input data is separated from code

---

## What the Script Does

- Reads a CSV file containing:
  - device hostname or IP
  - interface name
  - interface description
- Groups interface changes per device
- Connects to each device using Netmiko (SSH)
- Applies all interface descriptions in a single config session
- Saves the configuration
- Prints a success/failure summary at the end

---

## Technologies Used

- Python 3
- Netmiko
- ThreadPoolExecutor (concurrency)
- python-dotenv (environment variables)
- CSV-based input

---

## Project Files

- set_port_descriptions_from_csv.py
- set_port_descriptions_from_csv.example.csv
- .env.example
- .gitignore
- requirements.txt

---

## CSV Format

The CSV file must contain the following headers:

```csv
host,interface,description
10.0.0.1,Gi1/0/1,PC
10.0.0.1,Gi1/0/2,Printer
10.0.0.2,Gi1/0/1,Phone
```
- The CSV included in this repository uses example data

---

## Environment Variables

Create a `.env` file locally with:

- NET_USER=your_username
- NET_PASS=your_password
- NET_SECRET=your_enable_secret # optional, if required

A template is provided in `.env.example`.

---

## How To Run

1. Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
3. Create and .env file or modify the provided with credentials
4. Update the CSV file with the target devices
5. Run the script
    ```bash
    python set_port_descriptions_from_csv.py
