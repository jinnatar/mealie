from apscheduler.schedulers.background import BackgroundScheduler
from db.database import db
from db.db_setup import create_session
from fastapi.logger import logger
from schema.user import GroupInDB
from services.backups.exports import auto_backup_job
from services.scheduler.global_scheduler import scheduler
from services.scheduler.scheduler_utils import Cron, cron_parser
from utils.post_webhooks import post_webhooks


# TODO Fix Scheduler
@scheduler.scheduled_job(trigger="interval", minutes=30)
def update_webhook_schedule():
    """
    A scheduled background job that runs every 30 minutes to
    poll the database for changes and reschedule the webhook time
    """
    session = create_session()
    all_groups: list[GroupInDB] = db.groups.get_all(session)

    for group in all_groups:

        time = cron_parser(group.webhook_time)
        job = JOB_STORE.get(group.name)

        scheduler.reschedule_job(
            job.scheduled_task.id,
            trigger="cron",
            hour=time.hours,
            minute=time.minutes,
        )

    session.close()
    logger.info(scheduler.print_jobs())


class ScheduledFunction:
    def __init__(
        self,
        scheduler: BackgroundScheduler,
        function,
        cron: Cron,
        name: str,
        args: list = None,
    ) -> None:
        self.scheduled_task = scheduler.add_job(
            function,
            trigger="cron",
            name=name,
            hour=cron.hours,
            minute=cron.minutes,
            max_instances=1,
            replace_existing=True,
            args=args,
        )

        logger.info("New Function Scheduled")
        logger.info(scheduler.print_jobs())


logger.info("----INIT SCHEDULE OBJECT-----")

JOB_STORE = {
    "backup_job": ScheduledFunction(
        scheduler, auto_backup_job, Cron(hours=00, minutes=00), "backups"
    ),
}


def init_webhook_schedule(scheduler, job_store: dict):
    session = create_session()
    all_groups: list[GroupInDB] = db.groups.get_all(session)

    for group in all_groups:
        cron = cron_parser(group.webhook_time)

        job_store.update(
            {
                group.name: ScheduledFunction(
                    scheduler,
                    post_webhooks,
                    cron=cron,
                    name=group.name,
                    args=[group.id],
                )
            }
        )

    session.close()
    logger.info("Init Webhook Schedule \n", scheduler.print_jobs())

    return job_store


JOB_STORE = init_webhook_schedule(scheduler=scheduler, job_store=JOB_STORE)


scheduler.start()
