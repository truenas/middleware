from time import time, sleep

from middlewared.test.integration.utils import call


def test_get_boot_scrub(request):
    job_id = call("boot.scrub")
    stop_time = time() + 600
    while True:
        job = call("core.get_jobs", [["id", "=", job_id]], {"get": True})
        if job["state"] in ("RUNNING", "WAITING"):
            if stop_time <= time():
                assert False, "Job Timeout\n\n" + job
                break
            sleep(1)
        else:
            assert job["state"] == "SUCCESS", job
            break
