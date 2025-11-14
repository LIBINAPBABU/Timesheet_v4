import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler import events
from apscheduler.util import utc
from .jobs import schedule_api,dailymail,approvalRemindermail,HRmail

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger('apscheduler').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

scheduler = None

def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} completed successfully.")

def start_scheduler():
    global scheduler

    try:
        if scheduler is None:
            logger.info("Starting scheduler in the master process")
            scheduler = BackgroundScheduler()
            scheduler.add_listener(job_listener, events.EVENT_JOB_EXECUTED | events.EVENT_JOB_ERROR)
            scheduler.start()
            logger.info("Scheduler started successfully.")
            
            job = scheduler.get_job('testScheduler')
            if job is None:
                logger.debug("No existing job found. Adding 'testScheduler'.")
                scheduler.add_job(
                    schedule_api,
                    trigger=CronTrigger(day_of_week="sat", hour="10,12", minute="30", second="00", timezone=utc),
                    id='testScheduler',
                    max_instances=1,
                    replace_existing=True,
                )
            else:
                logger.info(f"Job already exists: {job}")


            # # --------------------------------------------------------------------------------------
            # Schedule daily email job at 10 PM
            logger.debug("Scheduling daily email job at 11 PM.")
            scheduler.add_job(
                dailymail,
                trigger=CronTrigger(day_of_week="tue,wed,thu",hour="05", minute="00", second="00", timezone=utc),  # 10 AM every day
                id='dailyEmailJob',
                max_instances=1,
                replace_existing=True,
            )

            # Schedule Mail for list of employees to HR not submitted reminder email 
            logger.debug("Scheduling Not Submitted Email to HR.")
            scheduler.add_job(
                HRmail,
                trigger=CronTrigger(day_of_week="mon",hour="04", minute="30", second="00", timezone=utc),
                id='approvalReminderEmailJob',
                max_instances=1,
                replace_existing=True,
            )

            # Schedule approval reminder email job
            # logger.debug("Scheduling approval email reminder job.")
            # scheduler.add_job(
            #     approvalRemindermail,
            #     trigger=CronTrigger(day_of_week="mon,sat",hour="10,13", minute="30", second="00", timezone=utc),
            #     id='approvalReminderEmailJob',
            #     max_instances=1,
            #     replace_existing=True,
            # )
            # # --------------------------------------------------------------------------------------


        else:
            logger.info("Scheduler already running")
    except Exception as e:
        logger.error(f"Error starting the scheduler: {e}")

def testScheduler():
    logger.info("Running API Job")
    time.sleep(10)  # Simulate job duration
    logger.info("API Job completed")

# Start the scheduler only in the master process
# if __name__ == "__main__":
start_scheduler()