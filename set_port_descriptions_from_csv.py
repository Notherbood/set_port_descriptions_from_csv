import csv
from collections import defaultdict
from netmiko import ConnectHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
from dotenv import load_dotenv


# Name of the CSV file that contains:
# host,interface,description
CSV_FILE = "set_port_descriptions_from_csv.csv"

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
    raise SystemExit("Missing NET_USER or NET_PASS. Create a .env file")

# How many switches to work on in parallel
threads = 10

# Dictionary that will map:
#   host_ip -> list of (interface, description) for that host
#
# defaultdict(list) means:
# - If you access devices_interfaces[some_host] and it doesn't exist yet,
#   it automatically creates an empty list instead of raising a KeyError.
# This is so devices_interfaces[host].append((iface, desc))
#   Look for key host
#   If it doesn’t exist → create []
#   Append (iface, desc) to that list
# This removes the need for the next line
#    if host not in devices_interfaces:
#        devices_interfaces[host] = []


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
    # Connects to a single switch, applies all interface descriptions for that
    # switch, saves the configuration, and verifies the result.
    # This function runs inside a thread.
    # It returns a single text block to be printed by the main thread.
    
    # Netmiko device definition for this switch
    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": USERNAME,
        "password": PASSWORD,
        "secret": SECRET,
    }

   # Initialize connection variable so `finally` can safely close it
    conn = None

    try:
        # Open SSH connection to the device
        conn = ConnectHandler(**device)

        # Only attempts enable when a secret exists
        if SECRET:
            conn.enable()

        # Build configuration commands
        #
        # entries example:
        #   [("Gi1/0/1", "PC-01"), ("Gi1/0/2", "Printer-02")]
        #
        # Resulting command list:
        #   interface Gi1/0/1
        #   description PC-01
        #   interface Gi1/0/2
        #   description Printer-02
        
        config_cmds = []
        for iface, desc in entries:
            config_cmds.append(f"interface {iface}")

    # If CSV says "blank" (case-insensitive), remove the description
            if desc.strip().lower() == "blank":
                config_cmds.append("no description")
            else:
                config_cmds.append(f"description {desc}")

        # Push all configuration in one batch
        # Netmiko handles entering/exiting config mode internally
        conn.send_config_set(config_cmds)
        # Netmiko internally does
        # conf t
        # interface Gi1/0/1
        # description Test1

        # Save running-config to startup-config (write memory)
        conn.save_config()

        # Build ONE output block
        out_lines = []
        out_lines.append(f">>> Verifying interface descriptions on {host}:")

        for iface, _ in entries:
            # Run verification command per interface
            output = conn.send_command(
                f"show interface {iface} description",
                use_textfsm=False
            ).strip()

            # Drop header lines and blanks, keep only the real interface line(s)
            for line in output.splitlines():
                line_stripped = line.strip()

                # Skip empty lines
                if not line_stripped:
                    continue

                # Skip the header line (starts with "Interface")
                if line_stripped.lower().startswith("interface"):
                    continue

                # Keep only the actual interface description line
                out_lines.append(line)

        # Join all verification lines into one printable block
        verify_block = "\n".join(out_lines)                

        # Success return:
        #   - True  → switch succeeded
        #   - host  → which switch this refers to
        #   - text  → full verification output
        return True, host, verify_block
    
    except Exception as e:
        # Failure return (error text instead of printed output)
        return False, host, f"XXX ERROR on {host}: {e}"
    
    finally:
        # Always close the connection if it was opened
        if conn:
            conn.disconnect()


# ---- 2) Thread pool execution ----
# results structure:
#   {
#     "10.0.0.1": (True,  "<verification text>"),
#     "10.0.0.2": (False, "<error text>")
#   }
results = {}

with ThreadPoolExecutor(max_workers=threads) as executor:
    # Submit one task per switch
    # Each task runs configure_switch(host, entries)
    futures = {
        executor.submit(configure_switch, host, entries): host
        for host, entries in devices_interfaces.items()
    }
    # as_completed() yields futures as they finish (order is non-deterministic)
    for future in as_completed(futures):
        # Unpack the returned tuple from configure_switch()
        ok, host, text = future.result()
        # Store result keyed by host for later ordered printing
        results[host] = (ok, text)

# ---- 3) Print grouped output ----
for host in sorted(results):
    ok, text = results[host]

    # Print the full verification or error block
    print(text)

    # Print success line only for successful hosts
    if ok:
        print(f">>> SUCCESS: {host}")
    print()  # Blank line between hosts

# ---- 4) Summary ----
# Extract hostnames based on success/failure
successes = [h for h, (ok, _) in results.items() if ok]
failures  = [h for h, (ok, _) in results.items() if not ok]

print("\n========== SUMMARY ==========")
print(f"Total switches:  {len(results)}")
print(f"Successful:      {len(successes)}")
print(f"Failed:          {len(failures)}")

if failures:
    print("\nFailed hosts:")
    for h in failures:
        print(" -", h)

print("\nDone.")
