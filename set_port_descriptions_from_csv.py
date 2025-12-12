import csv
from collections import defaultdict
from netmiko import ConnectHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
from dotenv import load_dotenv


# Name of the CSV file that contains:
# host,interface,description
CSV_FILE = "set_port_descriptions_from_csv.example.csv"


# Resolve the directory where this script lives
SCRIPT_DIR = Path(__file__).resolve().parent

# 1) Try .env in the same folder as the script
env_path = SCRIPT_DIR / ".env"

# 2) If not found, try parent folder (This is in case you have a .env in the parent folder you share with multiple other scripts)
if not env_path.exists():
    env_path = SCRIPT_DIR.parent / ".env"

# Load if found (silent if missing)
load_dotenv(env_path)


# Loads credentials from .env
USERNAME = os.environ.get("NET_USER")
PASSWORD = os.environ.get("NET_PASS")
SECRET   = os.environ.get("NET_SECRET")

# In case of failure
if not USERNAME or not PASSWORD:
    raise SystemExit("Missing NET_USER or NET_PASS. Create a .env file (see .env.example).")


# How many switches to work on in parallel
threads = 10

# Dictionary that will map:
#   host_ip -> list of (interface, description) for that host
#
# defaultdict(list) means:
# - If you access devices_interfaces[some_host] and it doesn't exist yet,
#   it automatically creates an empty list instead of raising a KeyError.
devices_interfaces = defaultdict(list)

# ---- 1) Load data from CSV ----
with open(CSV_FILE, newline="") as f:
    # DictReader reads each row into a dict using the header line as keys
    # e.g. row = {"host": "10.0.0.1", "interface": "Gi1/0/1", "description": "Test"}
    reader = csv.DictReader(f)
    for row in reader:
        # Extract and clean each field
        host = row["host"].strip()
        iface = row["interface"].strip()
        desc = row["description"].strip()

        # Skip any incomplete/bad rows
        if not host or not iface or not desc:
            continue

        # Append the (interface, description) pair to this host's list
        # After reading the whole CSV, devices_interfaces might look like:
        # {
        #   "10.0.0.1": [("Gi1/0/1", "Test1"), ("Gi1/0/2", "Test2")],
        #   "10.0.0.2": [("Gi1/0/3", "Test3")]
        # }
        devices_interfaces[host].append((iface, desc))

# If the CSV produced no usable rows, abort the script
if not devices_interfaces:
    raise SystemExit("No valid rows found in CSV. Check file contents.")


def configure_switch(host, entries):
    
    # Connect to one switch (identified by 'host'),
    # apply all interface descriptions given in 'entries',
    # then save the configuration.

    # entries is a list of (interface, description) tuples.
    # For example:
    # [("Gi1/0/1", "PC-01"), ("Gi1/0/2", "Printer-02")]
    
    print(f"\n=== Connecting to {host} ===")

    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": USERNAME,
        "password": PASSWORD,
        "secret": SECRET,
    }

    # lets 'finally' know whether a connection was created
    conn = None

    try:
        # Open SSH connection to the device
        conn = ConnectHandler(**device)

        # Only attempts enable when a secret exists
        if SECRET:
            conn.enable()

        # Build the list of config commands to send
        # For each (iface, desc), we add:
        #   interface Gi1/0/1
        #   description Something
        config_cmds = []
        for iface, desc in entries:
            config_cmds.append(f"interface {iface}")
            config_cmds.append(f"description {desc}")

        print(f">>> Applying configuration on {host}...")
        # Send all configuration lines in one batch
        # Netmiko handles entering/exiting config mode internally
        conn.send_config_set(config_cmds)

        print(f">>> Saving configuration on {host}...")
        # Save running-config to startup-config (write memory)
        conn.save_config()

        print(f">>> SUCCESS: {host}")
        # Return a tuple indicating success and which host was processed
        return True, host

    except Exception as e:
        # If anything goes wrong (SSH error, timeout, etc.), we land here
        print(f"XXX ERROR on {host}: {e}")
        # Return a tuple indicating failure and which host failed
        return False, host
    
    finally:
        # Always close the connection if it was opened
        if conn:
            conn.disconnect()


# ---- 2) Thread pool execution ----
# 'results' will collect (ok, host) for each switch.
#   ok   = True/False
#   host = IP/hostname
results = []

# Create a thread pool with 'threads' worker threads.
# Each worker can handle one switch at a time.
with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit one job per host. Each job runs configure_switch(host, entries).
    # 'futures' is a dict:
    #   future_object -> host
    futures = {
        executor.submit(configure_switch, host, entries): host
        for host, entries in devices_interfaces.items()
    }

    # as_completed(futures) yields futures as they finish (in completion order,
    # not submission order).
    for future in as_completed(futures):
        # Get the result from the future (this calls configure_switch's return)
        ok, host = future.result()
        # Store (ok, host) into the results list
        results.append((ok, host))


# ---- 3) Summary ----
# Extract successes and failures from results using list comprehensions.
successes = [host for ok, host in results if ok]
failures  = [host for ok, host in results if not ok]

print("\n========== SUMMARY ==========")
print(f"Total switches:  {len(results)}")
print(f"Successful:      {len(successes)}")
print(f"Failed:          {len(failures)}")

if failures:
    print("\nFailed hosts:")
    for h in failures:
        print(" -", h)

print("\nDone.")
