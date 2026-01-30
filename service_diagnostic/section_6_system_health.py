# %% [markdown]
# # Section 6: System Health
#
# Checks disk space, error logs, and service status.
# **Can run without hardware.**

# %%
import shutil
import time
from common import TestResult, TestStatus, run_shell, print_header, print_result

results = []

# %% [markdown]
# ### Test: Disk Space

# %%
def test_disk_space():
    start = time.time()

    try:
        total, used, free = shutil.disk_usage("/data")
        percent = (used / total) * 100

        data = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "percent_used": round(percent, 1)
        }

        if percent < 80:
            return TestResult("Disk Space", TestStatus.PASS,
                            f"{data['free_gb']}GB free ({percent:.1f}% used)",
                            data, time.time() - start)
        elif percent < 95:
            return TestResult("Disk Space", TestStatus.WARNING,
                            f"Running low ({percent:.1f}% used)",
                            data, time.time() - start)
        else:
            return TestResult("Disk Space", TestStatus.FAIL,
                            f"Critical ({percent:.1f}% used)",
                            data, time.time() - start)
    except Exception as e:
        return TestResult("Disk Space", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("DISK SPACE")
r = test_disk_space()
results.append(r)
print_result(r)

# %% [markdown]
# ### Test: Recent Error Logs

# %%
def test_error_logs():
    start = time.time()

    try:
        _, stdout, _ = run_shell(
            "journalctl --since '24 hours ago' -p err --no-pager | tail -20"
        )

        errors = [l for l in stdout.strip().split('\n') if l.strip()] if stdout.strip() else []
        count = len(errors)

        data = {"errors_24h": count, "recent": errors[-5:] if errors else []}

        if count == 0:
            return TestResult("Error Logs", TestStatus.PASS,
                            "No errors in 24h", data, time.time() - start)
        elif count < 10:
            return TestResult("Error Logs", TestStatus.WARNING,
                            f"{count} error(s) in 24h", data, time.time() - start)
        else:
            return TestResult("Error Logs", TestStatus.WARNING,
                            f"{count} errors in 24h (elevated)", data, time.time() - start)
    except Exception as e:
        return TestResult("Error Logs", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("ERROR LOGS (24h)")
r = test_error_logs()
results.append(r)
print_result(r)

# %% [markdown]
# ### Test: Services Status

# %%
def test_services():
    start = time.time()
    services = ["opentrons-robot-server", "opentrons-update-server"]
    status = {}
    all_ok = True

    try:
        for svc in services:
            _, stdout, _ = run_shell(f"systemctl is-active {svc}")
            active = stdout.strip() == "active"
            status[svc] = "active" if active else "inactive"
            if not active:
                all_ok = False

        if all_ok:
            return TestResult("Services", TestStatus.PASS,
                            "All running", status, time.time() - start)
        else:
            return TestResult("Services", TestStatus.WARNING,
                            "Some not running", status, time.time() - start)
    except Exception as e:
        return TestResult("Services", TestStatus.ERROR,
                         str(e), duration_seconds=time.time() - start)

print_header("SERVICES STATUS")
r = test_services()
results.append(r)
print_result(r)

# %% [markdown]
# ### Summary

# %%
print("\n" + "=" * 60)
print(" SYSTEM HEALTH RESULTS")
print("=" * 60)
for r in results:
    print_result(r)
