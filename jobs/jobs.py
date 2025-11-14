from django.conf import settings
import requests
from django.shortcuts import redirect
from django.core.mail import EmailMultiAlternatives
from datetime import datetime
from templates.mailContents import reminderMessageBody,apprvalReminderMessageBody,dailyReminderMessageBody,dailyReminderMessageBodyForHr



def dailymail():
    # full_url = "https://tsm.icpro.in/timeline/dailyRemainderEmail"
    full_url = "https://127.0.0.0:8000/timeline/dailyRemainderEmail"
    r = requests.get(full_url, verify=False)

    if r.status_code == 200:
        response = r.json()
        subject = f"Reminder: Timesheet Not Yet Filled for {response['yesterdayDate']}"
        from_email = "icproprojects@gmail.com"
        text_content = "This is an important reminder regarding your timesheet."

        for obj in response.get('yesterdayNotFilledUsers', []):
            if not obj.get('is_filled', False):  # Add this condition if backend includes fill status
                html_content = dailyReminderMessageBody(obj["first_name"], response["yesterdayDate"])
                msg = EmailMultiAlternatives(subject, text_content, from_email, [obj["email"]]) #,cc=[obj["_reportingto"]]
                msg.attach_alternative(html_content, "text/html")
                # msg.send()


def schedule_api():
    full_url = "https://127.0.0.0:8000/timeline/emailsend"
    r = requests.get(full_url, verify=False)

    if r.status_code == 200:
        response = r.json()
        year = response['year']
        week = response['week']
        from_date = response['week_start_date']
        to_date = response['week_end_date']
        weekDay = response['weekDay']

        subject = f"Reminder: Timesheet Not Submitted for Week {week} of {year}"
        from_email = "icproprojects@gmail.com"
        text_content = "This is a reminder to complete and submit your timesheet."

        current_hour = datetime.now().hour
    
        for user in response.get('result', []):
            html_content = reminderMessageBody(
                employee_name=user["first_name"],
                year=year,
                week=week,
                from_date=from_date,
                to_date=to_date
            )

            recipients = [user["email"]]
            cc = [user["_reportingto"]] if current_hour == 12 else []

            msg = EmailMultiAlternatives(subject, text_content, from_email, recipients, cc=cc)
            msg.attach_alternative(html_content, "text/html")
            # msg.send()


def HRmail():
    full_url = f"http://127.0.0.0:8000/timeline/emailsend"
    r = requests.get(full_url,verify=False)
    if r.status_code == 200:
        response = r.json()
        subject = 'Timesheet not yet submitted for the week' + response['week'] + ' of ' + response['year']
        from_email =  "icproprojects@gmail.com"
        text_content = "This is an important message."
        for item in response['weeklySummaryMailDetails']:
            html_content = dailyReminderMessageBodyForHr(item["first_name"],response["week"],response['week_start_date'],response['week_end_date'],response["unFilledEmployeeNames"])
            msg = EmailMultiAlternatives(subject, text_content, from_email, item['email'])
            msg.attach_alternative(html_content, "text/html")
            # msg.send()



def approvalRemindermail():
    full_url = f"https://127.0.0.0:8000/timeline/weeklyApprovalMail"
    r = requests.get(full_url,verify=False)
    if r.status_code == 200:
        response = r.json()
        subject = 'Reminder: Timesheet not yet approved for the week ' + response["week"] + ' of ' + response['year']
        from_email =  "icproprojects@gmail.com"
        text_content = "This is an important message."
        year,week,fromDate,toDate =  response['year'],response["week"],response["week_start_date"],response["week_end_date"]
        current_dateTime = datetime.now()
        for obj in response['result']:
            html_content = apprvalReminderMessageBody(obj["_reporterName"],obj["first_name"],year,week,fromDate,toDate)
            if current_dateTime.hour == 13:
                msg = EmailMultiAlternatives(subject, text_content, from_email, [obj["_reportingto"]],cc=["hr@icpro.in"])
            else:
                msg = EmailMultiAlternatives(subject, text_content, from_email, [obj["_reportingto"]])
            msg.attach_alternative(html_content, "text/html")
            # msg.send()
